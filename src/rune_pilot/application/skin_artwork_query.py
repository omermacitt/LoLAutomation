"""Resolve known skin artwork from League metadata, with bounded memory use."""

import re
import threading
import time
from collections import OrderedDict

from rune_pilot.application.game_query_service import QueryUnavailable
from rune_pilot.application.ports.league_client import LeagueClient
from rune_pilot.domain.champion_service import is_mode_champion_variant

CACHE_SECONDS = 300
MAX_IMAGE_BYTES = 3 * 1024 * 1024
MAX_CACHE_BYTES = 32 * 1024 * 1024
MAX_CACHED_IMAGES = 32
MAX_CACHED_CHAMPIONS = 32
_ASSET = re.compile(
    r"/lol-game-data/assets/ASSETS/Characters/(?:[a-z0-9_-]+/)+[a-z0-9_-]+\.(?:jpg|jpeg|png)",
    re.IGNORECASE,
)


class SkinArtworkQuery:
    def __init__(self, client: LeagueClient, *, clock=time.monotonic):
        self._client = client
        self._clock = clock
        self._lock = threading.RLock()
        self._metadata: OrderedDict[int, tuple[float, dict[int, str]]] = OrderedDict()
        self._images: OrderedDict[tuple[int, int], tuple[float, bytes, str]] = OrderedDict()
        self._bytes = 0

    def artwork(self, champion_id: int, skin_id: int) -> tuple[bytes, str] | None:
        if champion_id <= 0 or skin_id // 1000 != champion_id:
            return None
        key = (champion_id, skin_id)
        with self._lock:
            now = self._clock()
            cached = self._images.get(key)
            if cached and cached[0] > now:
                self._images.move_to_end(key)
                return cached[1], cached[2]
            if cached:
                self._bytes -= len(self._images.pop(key)[1])
            try:
                metadata = self._metadata.get(champion_id)
                if metadata is None or metadata[0] <= now:
                    response = self._client.champion_data(champion_id)
                    if response.status_code == 404:
                        return None
                    response.raise_for_status()
                    data = response.json()
                    if (
                        not isinstance(data, dict)
                        or data.get("id") != champion_id
                        or not isinstance(data.get("skins"), list)
                    ):
                        raise ValueError("Missing skin metadata")
                    if is_mode_champion_variant(data):
                        return None
                    paths = {}
                    for skin in data["skins"]:
                        if not isinstance(skin, dict):
                            continue
                        sid, path = skin.get("id"), skin.get("splashPath")
                        if (
                            isinstance(sid, int)
                            and sid // 1000 == champion_id
                            and isinstance(path, str)
                            and _ASSET.fullmatch(path)
                        ):
                            paths[sid] = path
                    metadata = (self._clock() + CACHE_SECONDS, paths)
                    self._metadata[champion_id] = metadata
                    while len(self._metadata) > MAX_CACHED_CHAMPIONS:
                        self._metadata.popitem(last=False)
                self._metadata.move_to_end(champion_id)
                path = metadata[1].get(skin_id)
                if path is None:
                    return None
                response = self._client.asset(path)
                if response.status_code != 200:
                    return None
                content = response.content
                media_type = (
                    "image/jpeg"
                    if content.startswith(b"\xff\xd8\xff")
                    else "image/png" if content.startswith(b"\x89PNG\r\n\x1a\n") else None
                )
                if not media_type or len(content) > MAX_IMAGE_BYTES:
                    return None
                self._images[key] = (self._clock() + CACHE_SECONDS, content, media_type)
                self._bytes += len(content)
                while len(self._images) > MAX_CACHED_IMAGES or self._bytes > MAX_CACHE_BYTES:
                    self._bytes -= len(self._images.popitem(last=False)[1][1])
                return content, media_type
            except Exception as error:
                raise QueryUnavailable("Could not load skin artwork from League Client") from error
