"""Known champion portraits with bounded, instance-owned memory caches."""

from collections import OrderedDict
import threading
import time

from rune_pilot.application.ports.league_client import LeagueClient
from rune_pilot.application.game_query_service import QueryUnavailable
from rune_pilot.domain.champion_service import is_mode_champion_variant, normalize_champion_id

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_PORTRAIT_BYTES = 1_048_576
CACHE_SECONDS = 300
MAX_CACHED_PORTRAITS = 256


class ChampionPortraitQuery:
    def __init__(self, client: LeagueClient, *, clock=time.monotonic):
        self._client = client
        self._clock = clock
        self._lock = threading.RLock()
        self._paths: dict[int, str] = {}
        self._metadata_until = 0.0
        self._images: OrderedDict[int, tuple[float, bytes]] = OrderedDict()

    def portrait(self, champion_id: int) -> bytes | None:
        with self._lock:
            now = self._clock()
            cached = self._images.get(champion_id)
            if cached and cached[0] > now:
                self._images.move_to_end(champion_id)
                return cached[1]
            self._images.pop(champion_id, None)
            try:
                if now >= self._metadata_until:
                    response = self._client.champion_summary()
                    response.raise_for_status()
                    rows = response.json()
                    if not isinstance(rows, list) or not rows:
                        raise ValueError("Missing champion metadata")
                    paths = {}
                    for row in rows:
                        if not isinstance(row, dict) or is_mode_champion_variant(row):
                            continue
                        cid = normalize_champion_id(row.get("id"))
                        path = row.get("squarePortraitPath")
                        # Only an exact metadata-backed portrait path is accepted.
                        # Never accept a caller-supplied URL, path or a guessed ID.
                        if cid and path == f"/lol-game-data/assets/v1/champion-icons/{cid}.png":
                            paths[cid] = path
                    self._paths = paths
                    self._metadata_until = now + CACHE_SECONDS
                path = self._paths.get(champion_id)
                if path is None:
                    return None
                response = self._client.asset(path)
                if response.status_code != 200:
                    return None
                data = response.content
                if not data.startswith(PNG_SIGNATURE) or len(data) > MAX_PORTRAIT_BYTES:
                    return None
                self._images[champion_id] = (self._clock() + CACHE_SECONDS, data)
                while len(self._images) > MAX_CACHED_PORTRAITS:
                    self._images.popitem(last=False)
                return data
            except Exception as error:
                raise QueryUnavailable("Could not load champion portrait from League Client") from error
