"""Item builder, atomic local saves and explicit account-bound League export."""

import hashlib
import json
import threading
from copy import deepcopy

from rune_pilot.application.game_query_service import QueryUnavailable
from rune_pilot.application.ports.config_store import ConfigStore
from rune_pilot.application.ports.item_data import ItemData
from rune_pilot.application.ports.league_client import LeagueClient
from rune_pilot.domain.item_sets import (
    BuilderChampion,
    BuilderItem,
    ChampionItemStats,
    ItemCatalog,
    ItemSetCollection,
    ItemStats,
    direct_stats,
    league_set,
)


class ItemSetConflict(Exception):
    pass


def revision(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return '"' + hashlib.sha256(encoded).hexdigest() + '"'


class ItemSetService:
    def __init__(self, data: ItemData, store: ConfigStore, client: LeagueClient):
        self._data = data
        self._store = store
        self._client = client
        self._export_lock = threading.Lock()

    def _catalog(self):
        try:
            return self._data.catalog()
        except Exception as error:
            raise QueryUnavailable("Item builder game data unavailable") from error

    def catalog(self) -> ItemCatalog:
        version, champions, items = self._catalog()
        return ItemCatalog(
            version=version,
            champions=sorted(
                [BuilderChampion(id=int(c["key"]), name=c["name"]) for c in champions.values()],
                key=lambda c: c.name,
            ),
            items=sorted(
                [
                    BuilderItem(
                        id=int(key),
                        name=item.get("localizedName", item["name"]),
                        price=item["gold"]["total"],
                        stats=direct_stats(item),
                        tags=item.get("tags", []),
                        description=item.get("plaintext", ""),
                    )
                    for key, item in items.items()
                    if item.get("maps", {}).get("11") and item.get("gold", {}).get("purchasable")
                ],
                key=lambda i: (i.price, i.name),
            ),
        )

    def champion(self, champion_id: int) -> ChampionItemStats:
        version, champions, _ = self._catalog()
        champion = next((c for c in champions.values() if int(c["key"]) == champion_id), None)
        if champion is None:
            raise ValueError("Unknown champion")
        try:
            raw = self._data.champion_stats(champion["id"], version)

            def number(name):
                value = raw[name]
                return float(value["baseValue"] if isinstance(value, dict) else value)

            return ChampionItemStats(
                champion_id=champion_id,
                version=version,
                base=ItemStats(
                    ad=number("baseDamageModifiable"),
                    hp=number("baseHPModifiable"),
                    armor=number("baseArmorModifiable"),
                    mr=number("baseMR"),
                    attack_speed=number("attackSpeedModifiable"),
                ),
                growth=ItemStats(
                    ad=number("damagePerLevelModifiable"),
                    hp=number("hpPerLevelModifiable"),
                    armor=number("armorPerLevelModifiable"),
                    mr=number("mrPerLevel"),
                    attack_speed=number("attackSpeedPerLevelModifiable"),
                ),
                attack_speed_ratio=number("attackSpeedRatioModifiable"),
            )
        except Exception as error:
            raise QueryUnavailable("Verified champion level statistics unavailable") from error

    def icon(self, item_id: int) -> bytes:
        catalog = self.catalog()
        if item_id not in {item.id for item in catalog.items}:
            raise ValueError("Unknown item")
        try:
            return self._data.icon(item_id, catalog.version)
        except Exception as error:
            raise QueryUnavailable("Item icon unavailable") from error

    def load(self) -> ItemSetCollection:
        try:
            return ItemSetCollection.model_validate(
                self._store.read(strict=True).get("item_sets_v1", {})
            )
        except Exception as error:
            raise QueryUnavailable("Saved item sets could not be loaded") from error

    def _validate(self, collection: ItemSetCollection):
        catalog = self.catalog()
        champions = {c.id for c in catalog.champions}
        items = {i.id for i in catalog.items}
        for item_set in collection.sets:
            if item_set.champion_id is not None and item_set.champion_id not in champions:
                raise ValueError("Unknown item-set champion")
            for block in item_set.blocks:
                if not block.name.strip() or any(item.id not in items for item in block.items):
                    raise ValueError("Item block has unavailable items or an empty name")
                if block.slots is not None:
                    expected_slots = sorted(i.id for i in block.items for _ in range(i.count))
                    actual_slots = sorted(i for i in block.slots if i is not None)
                    if actual_slots != expected_slots:
                        raise ValueError("Item slots do not match the block")

    def save(self, collection: ItemSetCollection, expected: str) -> ItemSetCollection:
        current = self.load()
        if revision(current.model_dump()) != expected:
            raise ItemSetConflict("Item sets changed in another window")
        previous = {s.uid: s for s in current.sets}
        # A patch can retire items. Keep unchanged historical sets so users can
        # repair/delete them individually; export always validates its full set.
        self._validate(
            ItemSetCollection(sets=[s for s in collection.sets if previous.get(s.uid) != s])
        )
        conflict = False

        def mutate(raw):
            nonlocal conflict
            current = ItemSetCollection.model_validate(raw.get("item_sets_v1", {}))
            if revision(current.model_dump()) != expected:
                conflict = True
                raise ItemSetConflict("Item sets changed in another window")
            raw["item_sets_v1"] = collection.model_dump()

        try:
            saved = self._store.update(mutate, strict=True)
        except Exception as error:
            raise QueryUnavailable("Item sets could not be saved safely") from error
        if conflict:
            raise ItemSetConflict("Item sets changed in another window")
        if not saved:
            raise QueryUnavailable("Item sets could not be saved")
        return collection

    def _client_state(self):
        try:
            account = self._client.current_summoner()
            account.raise_for_status()
            sid = int(account.json()["summonerId"])
            response = self._client.item_sets(sid)
            response.raise_for_status()
            raw = response.json()
            if not isinstance(raw, dict) or not isinstance(raw.get("itemSets"), list):
                raise ValueError("Invalid item sets collection")
            return sid, raw, revision([sid, raw])
        except Exception as error:
            raise QueryUnavailable("League item sets unavailable") from error

    def client_state(self) -> dict:
        _, raw, token = self._client_state()
        return {"revision": token, "set_count": len(raw["itemSets"])}

    def export(self, uid: str, expected: str, local_revision: str | None = None) -> dict:
        with self._export_lock:
            collection = self.load()
            if local_revision is not None and revision(collection.model_dump()) != local_revision:
                raise ItemSetConflict("Local item set changed before export")
            item_set = next((s for s in collection.sets if s.uid == uid), None)
            if item_set is None:
                raise ValueError("Save the item set before export")
            self._validate(ItemSetCollection(sets=[item_set]))
            sid, raw, token = self._client_state()
            if token != expected:
                raise ItemSetConflict("League account or item sets changed")
            payload = deepcopy(raw)
            payload["itemSets"] = [s for s in payload["itemSets"] if s.get("uid") != uid] + [
                league_set(item_set)
            ]
            try:
                # Bind the write to the same active login observed by the editor.
                if int(self._client.current_summoner().json()["summonerId"]) != sid:
                    raise ItemSetConflict("League account changed")
                response = self._client.replace_item_sets(sid, payload)
                response.raise_for_status()
                after_sid, after, after_token = self._client_state()
                found = next((s for s in after["itemSets"] if s.get("uid") == uid), None)
                if after_sid != sid or found != league_set(item_set):
                    raise ValueError("Item set export not confirmed")
                return {"revision": after_token, "set_count": len(after["itemSets"])}
            except ItemSetConflict:
                raise
            except Exception as error:
                raise QueryUnavailable("League export result could not be confirmed") from error
