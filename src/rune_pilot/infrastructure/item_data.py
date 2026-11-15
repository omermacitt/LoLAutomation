"""Bounded requests to fixed game-data CDNs; no HTML scraping or credentials."""

import re
import threading
import time
from collections import OrderedDict

import requests


def classic_item_ids(map_data: dict) -> set[str]:
    """Resolve only CLASSIC's lists; map 11 also contains Swiftplay/URF shops."""
    mode = map_data.get("Maps/Shipping/Map11/Modes/CLASSIC", {})
    lists = mode.get("itemLists")
    if mode.get("__type") != "GameModeMapData" or not isinstance(lists, list) or not lists:
        raise ValueError("Classic item lists unavailable")
    ids = set()
    for reference in lists:
        entry = map_data.get(reference, {})
        paths = entry.get("mItems")
        if entry.get("__type") != "GameModeItemList" or not isinstance(paths, list):
            raise ValueError("Classic item list unavailable")
        for path in paths:
            if not isinstance(path, str) or not re.fullmatch(r"Items/[1-9]\d*", path):
                raise ValueError("Invalid classic item reference")
            ids.add(path.split("/")[1])
    if not ids:
        raise ValueError("Classic item list empty")
    return ids


class DragonItemData:
    def __init__(self):
        self._lock = threading.RLock()
        self._catalog = None
        self._expires = 0.0
        self._stats: OrderedDict = OrderedDict()
        self._icons: OrderedDict = OrderedDict()

    @staticmethod
    def _get(url: str, limit: int = 8 * 1024 * 1024) -> requests.Response:
        with requests.get(url, timeout=(5, 15), stream=True, allow_redirects=False) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("Unexpected static data response")
            parts = []
            size = 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > limit:
                    raise ValueError("Game data exceeds limit")
                parts.append(chunk)
            response._content = b"".join(parts)
            return response

    def catalog(self) -> tuple[str, dict, dict]:
        with self._lock:
            if self._catalog and self._expires > time.monotonic():
                return self._catalog
            realm = self._get("https://ddragon.leagueoflegends.com/realms/tr.json").json()
            version = realm["n"]["champion"]
            if not re.fullmatch(r"\d+\.\d+\.\d+", version) or realm["n"]["item"] != version:
                raise ValueError("Mismatched game data versions")
            root = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US"
            champions = self._get(root + "/champion.json").json()
            items = self._get(root + "/item.json").json()
            if champions["version"] != version or items["version"] != version:
                raise ValueError("Mismatched game data versions")
            localized = self._get(root.replace("en_US", "tr_TR") + "/item.json").json()
            if localized.get("version") != version:
                raise ValueError("Mismatched item localization")
            patch = ".".join(version.split(".")[:2])
            map_data = self._get(
                f"https://raw.communitydragon.org/{patch}/game/data/maps/shipping/map11/map11.bin.json",
                16 * 1024 * 1024,
            ).json()
            # Data Dragon's maps[11] also admits ARAM starters and Swiftplay
            # variants. The game's CLASSIC shop lists are the eligibility source.
            eligible = classic_item_ids(map_data)
            classic_items = {k: v for k, v in items["data"].items() if k in eligible}
            if not classic_items:
                raise ValueError("Classic item catalog unavailable")
            for key, item in classic_items.items():
                item["localizedName"] = localized["data"].get(key, {}).get("name", item["name"])
            self._catalog = (version, champions["data"], classic_items)
            self._expires = time.monotonic() + 3600
            return self._catalog

    def champion_stats(self, alias: str, version: str) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9]+", alias) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
            raise ValueError("Invalid champion data context")
        with self._lock:
            key = (version, alias)
            if key not in self._stats:
                patch = ".".join(version.split(".")[:2])
                data = self._get(
                    f"https://raw.communitydragon.org/{patch}/game/data/characters/{alias.lower()}/{alias.lower()}.bin.json"
                ).json()
                root = f"Characters/{alias}/CharacterRecords/Root"
                value = next((v for k, v in data.items() if k.lower() == root.lower()), None)
                if not isinstance(value, dict):
                    raise ValueError("Champion base statistics unavailable")
                self._stats[key] = value
                while len(self._stats) > 180:
                    self._stats.popitem(last=False)
            return self._stats[key]

    def icon(self, item_id: int, version: str) -> bytes:
        if item_id <= 0 or not re.fullmatch(r"\d+\.\d+\.\d+", version):
            raise ValueError("Invalid icon")
        key = (version, item_id)
        with self._lock:
            cached = self._icons.get(key)
        if cached is not None:
            return cached
        data = self._get(
            f"https://ddragon.leagueoflegends.com/cdn/{version}/img/item/{item_id}.png",
            256 * 1024,
        ).content
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Invalid item icon")
        with self._lock:
            self._icons[key] = data
            while len(self._icons) > 256:
                self._icons.popitem(last=False)
        return data
