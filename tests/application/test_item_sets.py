"""Temporary profiles and fake clients only; never contact Riot or write game state."""

import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from rune_pilot.application.game_query_service import QueryUnavailable
from rune_pilot.application.item_set_service import ItemSetConflict, ItemSetService, revision
from rune_pilot.composition.api_app import create_app
from rune_pilot.domain.item_sets import ItemSet, ItemSetCollection, direct_stats, league_set
from rune_pilot.infrastructure.config_repository import ConfigRepository

UID = "runepilot-11111111-1111-4111-8111-111111111111"


@pytest.fixture
def setup(tmp_path):
    data = Mock()
    data.catalog.return_value = (
        "16.22.1",
        {"Rengar": {"key": "107", "id": "Rengar", "name": "Rengar"}},
        {
            "3078": {
                "name": "Trinity Force",
                "localizedName": "Üçlü Kuvvet",
                "description": "<stats><attention>36</attention> Attack Damage<br><attention>30%</attention> Attack Speed<br>333 Health<br>15 Ability Haste</stats><passive>20 Move Speed</passive>",
                "gold": {"total": 3333, "purchasable": True},
                "maps": {"11": True},
                "tags": ["Damage"],
            },
            "9999": {
                "name": "Arena only",
                "gold": {"total": 1000, "purchasable": True},
                "maps": {"11": False},
            },
        },
    )
    data.champion_stats.return_value = {
        key: {"baseValue": value}
        for key, value in {
            "baseDamageModifiable": 68,
            "damagePerLevelModifiable": 3,
            "baseHPModifiable": 590,
            "hpPerLevelModifiable": 104,
            "baseArmorModifiable": 34,
            "armorPerLevelModifiable": 4.2,
            "baseMR": 32,
            "mrPerLevel": 2.05,
            "attackSpeedModifiable": 0.667,
            "attackSpeedPerLevelModifiable": 3,
            "attackSpeedRatioModifiable": 0.667,
        }.items()
    }
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"queue_name": "Ranked Solo/Duo", "unrelated": {"keep": True}}), encoding="utf-8"
    )
    store = ConfigRepository(str(path), fallback_paths=())
    client = Mock()
    collection = {
        "accountId": 222,
        "timestamp": 123,
        "itemSets": [
            {"uid": "existing-client-set", "title": "Keep", "blocks": [], "other": "preserved"}
        ],
    }

    def reply(value):
        return Mock(status_code=200, json=Mock(return_value=deepcopy(value)))

    client.current_summoner.side_effect = lambda: reply({"summonerId": 111})
    client.item_sets.side_effect = lambda sid: reply(collection)

    def replace(sid, payload):
        assert sid == 111
        collection.clear()
        collection.update(deepcopy(payload))
        return reply(None)

    client.replace_item_sets.side_effect = replace
    service = ItemSetService(data, store, client)
    item_set = ItemSet(
        uid=UID,
        title="Rengar Orman",
        champion_id=107,
        blocks=[{"name": "Ana eşyalar", "items": [{"id": 3078, "count": 1}]}],
    )
    return SimpleNamespace(
        service=service,
        data=data,
        store=store,
        client=client,
        collection=collection,
        item_set=item_set,
        path=path,
    )


def save_set(s):
    return s.service.save(
        ItemSetCollection(sets=[s.item_set]), revision(s.service.load().model_dump())
    )


def test_direct_stats_only_reads_explicit_complete_labels():
    stats = direct_stats(
        {
            "description": "<stats>36 Attack Damage<br>30% Attack Speed<br>333 Health<br>15 Ability Haste<br>20 Armor Penetration</stats><passive>100 Ability Power</passive>"
        }
    )
    assert stats.ad == 36 and stats.attack_speed == 0.3 and stats.haste == 15
    assert stats.ap == 0 and stats.armor == 0


def test_catalog_filters_map_and_champion_growth_uses_game_values(setup):
    s = setup
    assert [i.id for i in s.service.catalog().items] == [3078]
    stats = s.service.champion(107)
    assert stats.base.ad == 68 and stats.growth.ad == 3
    s.data.champion_stats.side_effect = ValueError("missing")
    with pytest.raises(QueryUnavailable):
        s.service.champion(107)


def test_local_save_preserves_other_settings_and_uses_revisions(setup):
    s = setup
    original = revision(s.service.load().model_dump())
    saved = save_set(s)
    assert saved.sets[0].title == "Rengar Orman"
    assert s.store.read()["unrelated"] == {"keep": True}
    with pytest.raises(ItemSetConflict):
        s.service.save(ItemSetCollection(), original)
    assert s.service.load() == saved
    s.client.replace_item_sets.assert_not_called()


def test_corrupt_profile_cannot_be_replaced_by_empty_defaults(setup):
    s = setup
    s.path.write_text("{broken", encoding="utf-8")
    with pytest.raises(QueryUnavailable):
        s.service.load()
    with pytest.raises(QueryUnavailable):
        s.service.save(ItemSetCollection(), revision({"sets": []}))
    assert s.path.read_text() == "{broken"


def test_export_preserves_existing_client_sets_and_has_no_local_slot_metadata(setup):
    s = setup
    save_set(s)
    token = s.service.client_state()["revision"]
    result = s.service.export(UID, token)
    assert result["set_count"] == 2
    assert s.collection["itemSets"][0]["other"] == "preserved"
    assert s.collection["itemSets"][1] == league_set(s.item_set)
    assert s.collection["itemSets"][1]["blocks"][0]["items"] == [{"id": "3078", "count": 1}]
    # Repeating a confirmed explicit export replaces the same UID, never duplicates it.
    s.service.export(UID, result["revision"])
    assert len(s.collection["itemSets"]) == 2


def test_external_set_change_or_account_change_aborts_export(setup):
    s = setup
    save_set(s)
    token = s.service.client_state()["revision"]
    s.collection["itemSets"].append({"uid": "new-external"})
    with pytest.raises(ItemSetConflict):
        s.service.export(UID, token)
    s.client.replace_item_sets.assert_not_called()
    token = s.service.client_state()["revision"]
    s.client.current_summoner.side_effect = [
        Mock(json=Mock(return_value={"summonerId": 111})),
        Mock(json=Mock(return_value={"summonerId": 999})),
    ]
    with pytest.raises(ItemSetConflict):
        s.service.export(UID, token)
    s.client.replace_item_sets.assert_not_called()


def test_invalid_items_and_mismatched_slots_rejected_without_writing(setup):
    s = setup
    s.item_set.blocks[0].slots = [None] * 6
    with pytest.raises(ValueError):
        save_set(s)
    assert "item_sets_v1" not in s.store.read()
    s.item_set.blocks[0].slots = None
    s.item_set.blocks[0].items[0].id = 9999
    with pytest.raises(ValueError):
        save_set(s)


def test_local_change_before_export_requires_reloading_without_game_write(setup):
    s = setup
    old = revision(s.service.load().model_dump())
    save_set(s)
    token = s.service.client_state()["revision"]
    with pytest.raises(ItemSetConflict):
        s.service.export(UID, token, old)
    s.client.replace_item_sets.assert_not_called()


def test_retired_items_can_be_repaired_one_set_at_a_time_without_export(setup):
    s = setup
    old = s.item_set.model_copy(deep=True)
    old.blocks[0].items[0].id = 2051
    second = old.model_copy(deep=True)
    second.uid = "runepilot-22222222-2222-4222-8222-222222222222"
    legacy = ItemSetCollection(sets=[old, second])
    s.store.update(lambda raw: raw.update(item_sets_v1=legacy.model_dump()))
    token = s.service.client_state()["revision"]
    with pytest.raises(ValueError):
        s.service.export(old.uid, token)
    s.client.replace_item_sets.assert_not_called()
    repaired = ItemSetCollection(sets=[s.item_set, second])
    s.service.save(repaired, revision(legacy.model_dump()))
    assert s.service.load() == repaired
    # The other retired set remains intact and can then be deleted separately.
    s.service.save(ItemSetCollection(sets=[s.item_set]), revision(repaired.model_dump()))
    assert len(s.service.load().sets) == 1
    s.client.replace_item_sets.assert_not_called()


def test_http_contracts_require_revision_and_never_export_on_local_save(setup):
    s = setup
    app = create_app()
    app.state.item_sets = s.service
    # Do not enter production lifespan; the test owns its injected temporary store.
    client = TestClient(app)
    initial = client.get("/item-sets")
    assert initial.status_code == 200 and initial.headers["etag"]
    body = {"sets": [s.item_set.model_dump()]}
    assert client.put("/item-sets", json=body).status_code == 428
    saved = client.put("/item-sets", json=body, headers={"If-Match": initial.headers["etag"]})
    assert saved.status_code == 200
    assert (
        client.put(
            "/item-sets", json=body, headers={"If-Match": initial.headers["etag"]}
        ).status_code
        == 412
    )
    assert client.get("/item-builder/champions/107").json()["growth"]["ad"] == 3
    assert client.get("/item-builder/champions/999").status_code == 404
    s.client.replace_item_sets.assert_not_called()
