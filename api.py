"""
RunePilot FastAPI servisi.

Bu servis LoL Client (LCU API) ile konuşur ve masaüstü uygulamasına (PyQt) HTTP
üzerinden yardımcı olur.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from lcu import lcu_request

app = FastAPI()

STYLE_ID_BY_NAME: dict[str, int] = {
    "precision": 8000,
    "domination": 8100,
    "sorcery": 8200,
    "inspiration": 8300,
    "resolve": 8400,
}

CHAMP_SLUG_BY_ID: dict[int, str] = {}
CHAMP_NAME_BY_ID: dict[int, str] = {}
MAX_RUNE_PAGE_NAME_LEN = 16
LAST_BAN_SKIP: tuple[int, int] | None = None

def resource_path(relative_path: str) -> str:
    """PyInstaller ile paketlenmiş dosyalar için güvenli mutlak yol döndürür."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        # Use the directory of this file instead of CWD so double-click / different
        # launch contexts can still find bundled data like runes.json.
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

RUNES_FILE = resource_path("runes.json")

def load_runes() -> dict[str, Any]:
    """`runes.json` içeriğini okur; hata durumunda boş dict döndürür."""
    if not os.path.exists(RUNES_FILE):
        return {}
    try:
        with open(RUNES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

RUNES_DATA = load_runes()

def champion_slug_from_alias(alias: str) -> str:
    """
    Must match the slug format used when generating runes.json (see webscrapping.py).
    """
    alias = (alias or "").strip()
    special = {
        "MonkeyKing": "wukong",
        "FiddleSticks": "fiddlesticks",
    }
    if alias in special:
        return special[alias]
    return alias.lower()


def get_champion_slug_by_id(champ_id: int) -> str | None:
    """LCU verisinden champ_id için runes.json slug'ını çözer (cache'li)."""
    if champ_id in CHAMP_SLUG_BY_ID:
        return CHAMP_SLUG_BY_ID[champ_id]

    try:
        res = lcu_request("GET", "/lol-game-data/assets/v1/champion-summary.json")
        if res.status_code != 200:
            return None
        champs = res.json()
        if not isinstance(champs, list):
            return None

        for champ in champs:
            if not isinstance(champ, dict):
                continue
            cid = champ.get("id")
            try:
                cid_int = int(cid)
            except (TypeError, ValueError):
                continue

            name = champ.get("name") or champ.get("alias") or ""
            if name and cid_int not in CHAMP_NAME_BY_ID:
                CHAMP_NAME_BY_ID[cid_int] = str(name)

            alias = champ.get("alias") or champ.get("name") or ""
            slug = champion_slug_from_alias(str(alias))
            if slug:
                CHAMP_SLUG_BY_ID[cid_int] = slug

        return CHAMP_SLUG_BY_ID.get(champ_id)
    except Exception:
        return None


def get_champion_name_by_id(champ_id: int) -> str | None:
    """LCU verisinden champ_id için görünen şampiyon adını döndürür (cache'li)."""
    if champ_id in CHAMP_NAME_BY_ID:
        return CHAMP_NAME_BY_ID[champ_id]
    # Populate caches (slug+name) from the LCU champion summary.
    get_champion_slug_by_id(champ_id)
    return CHAMP_NAME_BY_ID.get(champ_id)


def build_rune_page_name(*, prefix: str, champion_name: str) -> str:
    """LoL client rune sayfası isim limitine göre güvenli bir isim üretir."""
    prefix = (prefix or "").strip() or "Auto"
    champ = (champion_name or "").strip() or "Champion"

    # Prefer a compact (no spaces/punctuation) champion name to fit the client limit.
    champ_compact = re.sub(r"[^0-9A-Za-z]", "", champ)
    champ_base = champ_compact or champ

    # Prefer "Prefix Champion" then "Prefix-Champion", then truncate champion name.
    candidate = f"{prefix} {champ_base}"
    if len(candidate) <= MAX_RUNE_PAGE_NAME_LEN:
        return candidate

    candidate = f"{prefix}-{champ_base}"
    if len(candidate) <= MAX_RUNE_PAGE_NAME_LEN:
        return candidate

    sep = " "
    max_champ_len = MAX_RUNE_PAGE_NAME_LEN - (len(prefix) + len(sep))
    if max_champ_len <= 0:
        return prefix[:MAX_RUNE_PAGE_NAME_LEN]
    champ_trunc = champ_base[:max_champ_len]
    return f"{prefix}{sep}{champ_trunc}"


def _safe_int_list(values) -> list[int]:
    """Liste içindeki değerleri int'e çevirir; çevrilemeyenleri atlar."""
    result: list[int] = []
    if not isinstance(values, list):
        return result
    for v in values:
        try:
            result.append(int(v))
        except (TypeError, ValueError):
            continue
    return result


def get_recommended_page_for_champion(champ_id: int) -> dict | None:
    """
    Supports 2 formats:
    1) { "123": {"primaryStyleId":..., "subStyleId":..., "selectedPerkIds":[...]}, ... }
    2) { "annie": {"rune_1": {"Domination":[...], "Sorcery":[...], "Shards":[...]}, ...}, ... }
    """
    # Format 1: direct champId -> payload
    direct = RUNES_DATA.get(str(champ_id))
    if isinstance(direct, dict) and "primaryStyleId" in direct and "subStyleId" in direct and "selectedPerkIds" in direct:
        try:
            primary_style_id = int(direct.get("primaryStyleId"))
            sub_style_id = int(direct.get("subStyleId"))
        except (TypeError, ValueError):
            return None

        selected = _safe_int_list(direct.get("selectedPerkIds"))
        if len(selected) != 9:
            return None

        return {"primaryStyleId": primary_style_id, "subStyleId": sub_style_id, "selectedPerkIds": selected}

    # Format 2: slug -> rune_1 -> tree lists
    slug = get_champion_slug_by_id(champ_id)
    if not slug:
        return None
    champ_blob = RUNES_DATA.get(slug)
    if not isinstance(champ_blob, dict):
        return None

    def _parse_win_rate(value) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        if not s:
            return None
        s = s.replace(",", ".")
        m = re.search(r"(\d+(?:\.\d+)?)", s)
        if not m:
            return None
        try:
            return float(m.group(1))
        except ValueError:
            return None

    rune_candidates: list[tuple[float, str, dict]] = []
    default_blob: dict | None = None
    fallback_blob: dict | None = None

    for k, v in champ_blob.items():
        if not (isinstance(k, str) and k.startswith("rune_") and isinstance(v, dict)):
            continue
        if fallback_blob is None:
            fallback_blob = v
        if k == "rune_1":
            default_blob = v

        win_rate = (
            v.get("Win Rate")
            or v.get("win_rate")
            or v.get("WinRate")
            or v.get("winRate")
            or v.get("WIN RATE")
        )
        parsed_wr = _parse_win_rate(win_rate)
        if parsed_wr is None:
            parsed_wr = -1.0
        rune_candidates.append((parsed_wr, k, v))

    if not rune_candidates:
        return None

    # Sort by winrate desc, then by rune_* key for stability.
    rune_candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)

    def _convert_blob_to_page(rune_blob: dict) -> dict | None:
        style_entries: list[tuple[str, int, int]] = []
        for k, v in rune_blob.items():
            if not isinstance(k, str):
                continue
            style_id = STYLE_ID_BY_NAME.get(k.strip().lower())
            if style_id is None:
                continue
            if not isinstance(v, list):
                continue
            style_entries.append((k, style_id, len(v)))

        if len(style_entries) < 2:
            return None

        primary_key = next((k for k, _sid, ln in style_entries if ln == 4), style_entries[0][0])
        secondary_key = next(
            (k for k, _sid, ln in style_entries if ln == 2 and k != primary_key),
            style_entries[1][0] if style_entries[1][0] != primary_key else style_entries[0][0],
        )

        primary_style_id = STYLE_ID_BY_NAME.get(primary_key.strip().lower())
        secondary_style_id = STYLE_ID_BY_NAME.get(secondary_key.strip().lower())
        if primary_style_id is None or secondary_style_id is None:
            return None

        primary_ids = _safe_int_list(rune_blob.get(primary_key))
        secondary_ids = _safe_int_list(rune_blob.get(secondary_key))

        shards_ids: list[int] = []
        for k, v in rune_blob.items():
            if isinstance(k, str) and k.strip().lower() == "shards":
                shards_ids = _safe_int_list(v)
                break

        selected = primary_ids[:4] + secondary_ids[:2] + shards_ids[:3]
        if len(selected) != 9:
            return None

        return {
            "primaryStyleId": primary_style_id,
            "subStyleId": secondary_style_id,
            "selectedPerkIds": selected,
        }

    # Try highest winrate first; if conversion fails, fall back to rune_1 then first available.
    for _wr, _name, blob in rune_candidates:
        page = _convert_blob_to_page(blob)
        if page:
            if _wr >= 0:
                print(f"[RUNES] Recommended rune selected: {slug}:{_name} winRate={_wr}")
            else:
                print(f"[RUNES] Recommended rune selected: {slug}:{_name}")
            return page

    if default_blob is not None:
        page = _convert_blob_to_page(default_blob)
        if page:
            return page

    if fallback_blob is not None:
        page = _convert_blob_to_page(fallback_blob)
        if page:
            return page

    return None

# -----------------------------------------------------------------------------
# GLOBAL STATE
# -----------------------------------------------------------------------------
RUNNING = False
CURRENT_CONFIG: dict[str, Any] = {}
AUTOMATION_THREAD: threading.Thread | None = None
AUTOMATION_LOCK = threading.Lock()

# -----------------------------------------------------------------------------
# MODELS
# -----------------------------------------------------------------------------
class AutomationConfig(BaseModel):
    """Masaüstü uygulamasından (GUI) gelen otomasyon ayarları."""
    primary_role: str | None = None
    secondary_role: str | None = None
    primary_summoner_spell: str | int | None = None
    secondary_summoner_spell: str | int | None = None
    role_summoner_spells: dict[str, dict[str, int | None]] = Field(default_factory=dict)
    # role -> champId(str) -> {"spell1Id": int|None, "spell2Id": int|None}
    custom_summoner_spells: dict[str, dict[str, dict[str, int | None]]] = Field(default_factory=dict)
    queue_id: int = 420
    role_champions: dict[str, list[int]] = Field(default_factory=dict)
    role_bans: dict[str, int] = Field(default_factory=dict)
    # role -> champId(str) -> rune page dict
    custom_runes: dict[str, dict[str, dict]] = Field(default_factory=dict)
    auto_queue: bool = True

# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
def is_banned(session: dict[str, Any], champ_id: int) -> bool:
    """Şampiyon seçim ekranında verilen champ_id için ban durumunu döndürür."""
    bans = session.get("bans") or {}
    if not isinstance(bans, dict):
        return False

    all_bans_raw = (bans.get("myTeamBans") or []) + (bans.get("theirTeamBans") or [])
    all_bans = set(_safe_int_list(all_bans_raw))
    try:
        champ_id_int = int(champ_id)
    except (TypeError, ValueError):
        return False
    return champ_id_int in all_bans


def is_picked(session: dict[str, Any], champ_id: int) -> bool:
    """Şampiyon seçim ekranında champ_id'nin picklenmiş olup olmadığını döndürür."""
    try:
        champ_id_int = int(champ_id)
    except (TypeError, ValueError):
        return False

    for team_key in ("myTeam", "theirTeam"):
        for player in session.get(team_key, []) or []:
            if not isinstance(player, dict):
                continue
            try:
                picked = int(player.get("championId") or 0)
            except (TypeError, ValueError):
                picked = 0
            if picked == champ_id_int and champ_id_int != 0:
                return True

    return False

def is_teammate_showing(session: dict[str, Any], champ_id: int) -> bool:
    """Takım arkadaşının champ_id'yi gösteriyor/niyet ediyor olup olmadığını kontrol eder."""
    try:
        cid = int(champ_id)
    except (TypeError, ValueError):
        return False

    for p in session.get("myTeam", []):
        if not isinstance(p, dict):
            continue
        try:
            shown = int(p.get("championId") or 0)
        except (TypeError, ValueError):
            shown = 0
        if shown == cid and cid != 0:
            return True

        try:
            intent = int(p.get("championPickIntent") or 0)
        except (TypeError, ValueError):
            intent = 0
        if intent == cid and cid != 0:
            return True

    return False

def do_ban(session: dict[str, Any], champ_id: int) -> None:
    """Oyuncunun ban aksiyonu açıksa, champ_id için ban atmayı dener."""
    global LAST_BAN_SKIP
    my_cell = session.get("localPlayerCellId")

    for group in session.get("actions", []) or []:
        if not isinstance(group, list):
            continue
        for action in group:
            if not isinstance(action, dict):
                continue
            if action.get("type") != "ban":
                continue
            if action.get("actorCellId") != my_cell:
                continue
            if action.get("completed"):
                continue

            action_id = action.get("id")
            if is_teammate_showing(session, champ_id):
                try:
                    key = (int(action_id), int(champ_id))
                except (TypeError, ValueError):
                    key = None

                if key is not None and LAST_BAN_SKIP != key:
                    champ_name = get_champion_name_by_id(int(champ_id)) or str(champ_id)
                    print(
                        f"[BAN] Skipping ban for {champ_name} ({champ_id}) because a teammate is showing it"
                    )
                    LAST_BAN_SKIP = key
                return

            LAST_BAN_SKIP = None
            try:
                lcu_request(
                    "PATCH",
                    f"/lol-champ-select/v1/session/actions/{action_id}",
                    {"championId": champ_id, "completed": True},
                )
            except Exception as e:
                print(f"[BAN] Failed to ban championId={champ_id}: {e}")
            return

def normalize_champion_id(value: Any) -> int | None:
    """Kullanıcı/LCU inputunu pozitif champ_id değerine normalize eder."""
    try:
        cid = int(value)
    except (TypeError, ValueError):
        return None
    return cid if cid > 0 else None


def normalize_spell_id(value: Any) -> int | None:
    """Kullanıcı/LCU inputunu pozitif spell_id değerine normalize eder."""
    try:
        sid = int(value)
    except (TypeError, ValueError):
        return None
    return sid if sid > 0 else None


def extract_spell_pair(entry: Any) -> tuple[bool, int | None, bool, int | None]:
    """
    Summoner spell çiftini farklı formatlardan çözer.

    Dönüş: (has_spell1, spell1_id, has_spell2, spell2_id)
    """
    has_s1 = False
    has_s2 = False
    s1: int | None = None
    s2: int | None = None

    if isinstance(entry, dict):
        if "spell1Id" in entry or "spell1" in entry:
            has_s1 = True
        if "spell2Id" in entry or "spell2" in entry:
            has_s2 = True

        if "spell1Id" in entry:
            s1 = normalize_spell_id(entry.get("spell1Id"))
        elif "spell1" in entry:
            s1 = normalize_spell_id(entry.get("spell1"))

        if "spell2Id" in entry:
            s2 = normalize_spell_id(entry.get("spell2Id"))
        elif "spell2" in entry:
            s2 = normalize_spell_id(entry.get("spell2"))
    elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
        has_s1 = True
        has_s2 = True
        s1 = normalize_spell_id(entry[0])
        s2 = normalize_spell_id(entry[1])

    return has_s1, s1, has_s2, s2

def get_pickable_champion_ids() -> set[int] | None:
    """
    Returns the set of champion ids the player can currently pick in champ select.
    If the endpoint isn't available (not in champ select, etc.), returns None.
    """
    try:
        res = lcu_request("GET", "/lol-champ-select/v1/pickable-champion-ids")
        if res.status_code != 200:
            return None

        ids = res.json()
        if not isinstance(ids, list):
            return None

        pickable: set[int] = set()
        for cid in ids:
            try:
                cid_int = int(cid)
            except (TypeError, ValueError):
                continue
            if cid_int > 0:
                pickable.add(cid_int)
        return pickable
    except Exception as e:
        print(f"[AUTO-PICK] Error fetching pickable champion ids: {e}")
        return None

def auto_pick_impl(session: dict[str, Any], champion_ids: list[int]) -> dict[str, Any]:
    """
    Tercih listesinden ilk uygun şampiyonu picklemeyi dener.

    `champion_ids` sırası önemlidir; ilk uygun olan denenir.
    """
    valid_ids: list[int] = []
    for c in champion_ids:
        try:
            cid = int(c)
        except (TypeError, ValueError):
            continue
        if cid > 0:
            valid_ids.append(cid)

    if not valid_ids:
        return {"status": "no_preference"}

    pickable_ids = get_pickable_champion_ids()
    candidate_ids = valid_ids
    if pickable_ids is not None:
        candidate_ids = [cid for cid in candidate_ids if cid in pickable_ids]

    candidate_ids = [cid for cid in candidate_ids if not is_banned(session, cid) and not is_picked(session, cid)]

    if not candidate_ids:
        print(f"[AUTO-PICK] No pickable preferred champions. preferred={valid_ids}")
        return {"status": "all_unavailable", "attempted": valid_ids}

    my_cell = session.get("localPlayerCellId")
    action_id = None
    for group in session.get("actions", []):
        for action in group:
            if (
                action.get("type") == "pick"
                and action.get("actorCellId") == my_cell
                and not action.get("completed")
            ):
                action_id = action.get("id")
                break
        if action_id is not None:
            break

    if action_id is None:
        return {"status": "no_pick_available"}

    last_error = None
    for champ_to_pick in candidate_ids:
        print(f"[AUTO-PICK] Picking champion {champ_to_pick}")
        try:
            res = lcu_request(
                "PATCH",
                f"/lol-champ-select/v1/session/actions/{action_id}",
                {"championId": champ_to_pick, "completed": True},
            )
            if res.status_code in (200, 204):
                return {"status": "picked", "champion": champ_to_pick}

            last_error = {
                "champion": champ_to_pick,
                "status_code": res.status_code,
                "body": res.text,
            }
            print(f"[AUTO-PICK] Pick failed for {champ_to_pick}: {res.status_code} {res.text}")
        except Exception as e:
            last_error = {"champion": champ_to_pick, "error": str(e)}
            print(f"[AUTO-PICK] Pick error for {champ_to_pick}: {e}")

    return {"status": "pick_failed", "attempted": candidate_ids, "last_error": last_error}


def load_champions_map() -> dict[int, dict[str, Any]]:
    """
    LCU üzerinden oyuncunun sahip olduğu şampiyonları okur.

    Dönüş formatı: `{championId: {"id": int, "name": str, "alias": str}}`
    """
    try:
        res = lcu_request("GET", "/lol-champions/v1/owned-champions-minimal")
        if res.status_code != 200:
            return {}

        champs = res.json()
        if not isinstance(champs, list):
            return {}

        valid_champs: dict[int, dict[str, Any]] = {}
        for champ in champs:
            if not isinstance(champ, dict):
                continue

            cid = normalize_champion_id(champ.get("id"))
            if cid is None:
                continue

            ownership = champ.get("ownership") or {}
            if isinstance(ownership, dict) and ownership.get("owned") is False:
                continue

            valid_champs[cid] = {
                "id": cid,
                "name": str(champ.get("name") or "Unknown"),
                "alias": str(champ.get("alias") or ""),
            }

        return valid_champs
    except Exception as e:
        print(f"[API] Error loading owned champions: {e}")
        return {}

@app.get("/champions")
def get_champions():
    """UI için sahip olunan şampiyon listesini döndürür."""
    champs_map = load_champions_map()
    if not champs_map:
        return []
    return sorted(champs_map.values(), key=lambda x: x.get("name", ""))

@app.get("/health")
def health():
    """Basit health-check endpoint'i."""
    return {"status": "ok", "running": RUNNING}

def get_gameflow_phase_safe() -> str | None:
    """LCU gameflow-phase okur; hata durumunda `None` döndürür."""
    try:
        res = lcu_request("GET", "/lol-gameflow/v1/gameflow-phase")
        if res.status_code != 200:
            return None
        phase = res.json()
        if isinstance(phase, str):
            return phase
        return None
    except Exception:
        return None


def ensure_lobby(queue_id: int) -> bool:
    """
    Ensure a lobby exists with the given queue id.
    Returns True if a lobby exists/created successfully.
    """
    try:
        res = lcu_request("GET", "/lol-lobby/v2/lobby")
        if res.status_code == 200:
            lobby = res.json()
            current_queue = None
            try:
                current_queue = int((lobby.get("gameConfig") or {}).get("queueId"))
            except Exception:
                current_queue = None

            if current_queue == queue_id:
                return True

            # Wrong queue: leave and recreate.
            lcu_request("DELETE", "/lol-lobby/v2/lobby")
            time.sleep(0.5)
    except Exception:
        pass

    try:
        create_res = lcu_request("POST", "/lol-lobby/v2/lobby", {"queueId": int(queue_id)})
        if create_res.status_code in (200, 201, 204):
            print(f"[QUEUE] Lobby created queueId={queue_id}")
            return True
        print(f"[QUEUE] Failed to create lobby: {create_res.status_code} {create_res.text}")
    except Exception as e:
        print(f"[QUEUE] Error creating lobby: {e}")

    return False


def ensure_matchmaking_searching() -> None:
    """
    Start matchmaking search if it isn't already searching.
    """
    try:
        state_res = lcu_request("GET", "/lol-lobby/v2/lobby/matchmaking/search-state")
        if state_res.status_code == 200:
            state = state_res.json()
            if isinstance(state, dict) and state.get("searchState") == "Searching":
                return
    except Exception:
        # Some client versions may not expose the search-state endpoint.
        pass

    try:
        res = lcu_request("POST", "/lol-lobby/v2/lobby/matchmaking/search")
        if res.status_code in (200, 204):
            print("[QUEUE] Matchmaking search started")
            return
        print(f"[QUEUE] Failed to start search: {res.status_code} {res.text}")
    except Exception as e:
        print(f"[QUEUE] Error starting search: {e}")


def apply_runes_impl(session: dict[str, Any], cfg: dict[str, Any], role_for_runes: str) -> bool:
    """
    Seçili şampiyon için rün sayfasını uygular.

    Öncelik: `cfg["custom_runes"]` -> `runes.json` önerisi.
    """
    my_cell = session.get("localPlayerCellId")
    my_champ_id = 0
    for p in session.get("myTeam", []):
        if p.get("cellId") == my_cell:
            my_champ_id = p.get("championId", 0)
            break
             
    if my_champ_id == 0:
        return False

    try:
        custom_runes = cfg.get("custom_runes") or {}
        role_pages = custom_runes.get(role_for_runes) if role_for_runes else None
        if not isinstance(role_pages, dict):
            role_pages = {}

        page_data: dict | None = None
        used_custom = False
        custom_page = role_pages.get(str(my_champ_id))
        if isinstance(custom_page, dict):
            candidate = {
                "primaryStyleId": custom_page.get("primaryStyleId"),
                "subStyleId": custom_page.get("subStyleId"),
                "selectedPerkIds": custom_page.get("selectedPerkIds"),
            }
            try:
                int(candidate.get("primaryStyleId"))
                int(candidate.get("subStyleId"))
            except (TypeError, ValueError):
                candidate = None

            if candidate is not None and len(_safe_int_list(candidate.get("selectedPerkIds"))) != 9:
                candidate = None

            if candidate is None:
                print(f"[RUNES] Invalid custom rune page for championId={my_champ_id}, falling back to recommended")
            else:
                page_data = candidate
                used_custom = True

        if page_data is None:
            recommended = get_recommended_page_for_champion(my_champ_id)
            if not recommended:
                print(f"[RUNES] No recommended runes found for championId={my_champ_id}")
                return False
            page_data = {**recommended}
            used_custom = False

        champ_name = get_champion_name_by_id(my_champ_id) or str(my_champ_id)
        name_prefix = "Custom" if used_custom else "Auto"
        desired_page_name = build_rune_page_name(prefix=name_prefix, champion_name=champ_name)
        page_data["name"] = desired_page_name

        try:
            primary_style_id = int(page_data.get("primaryStyleId"))
            sub_style_id = int(page_data.get("subStyleId"))
        except (TypeError, ValueError):
            print(f"[RUNES] Invalid style ids for championId={my_champ_id}: {page_data}")
            return False

        selected = _safe_int_list(page_data.get("selectedPerkIds"))
        if len(selected) != 9:
            print(f"[RUNES] Invalid selectedPerkIds for championId={my_champ_id}: {page_data.get('selectedPerkIds')}")
            return False

        res = lcu_request("GET", "/lol-perks/v1/pages")
        if res.status_code != 200:
            print(f"[RUNES] Failed to fetch rune pages: {res.status_code} {res.text}")
            return False
        pages = res.json()
        if not isinstance(pages, list):
            print(f"[RUNES] Unexpected /lol-perks/v1/pages response: {type(pages)}")
            return False

        def _page_id(page: dict) -> int | None:
            try:
                return int(page.get("id"))
            except (TypeError, ValueError):
                return None

        def _page_name(page: dict) -> str:
            return str(page.get("name") or "")

        def _is_editable(page: dict) -> bool:
            # LCU uses isEditable; default to True if missing.
            return page.get("isEditable") is not False

        def _is_deletable(page: dict) -> bool:
            # LCU uses isDeletable; default to False if missing.
            if "isDeletable" not in page:
                return False
            return page.get("isDeletable") is True

        def _is_automation_page_name(name: str) -> bool:
            n = (name or "").strip()
            if not n:
                return False
            if n.startswith("Auto ") or n.startswith("Custom ") or n.startswith("Auto-") or n.startswith("Custom-"):
                return True
            # Legacy names from earlier builds
            return n == "LoLAutomation" or n.startswith("LoLAutomation")

        def _put_page(page: dict, *, name: str) -> bool:
            pid = _page_id(page)
            if pid is None:
                return False
            payload = {
                "id": pid,
                "name": name,
                "primaryStyleId": primary_style_id,
                "subStyleId": sub_style_id,
                "selectedPerkIds": selected,
                "current": True,
            }
            put_res = lcu_request("PUT", f"/lol-perks/v1/pages/{pid}", payload)
            if put_res.status_code in (200, 201, 204):
                print(f"[RUNES] Updated rune page id={pid} name={name}")
                return True
            print(f"[RUNES] Failed to update rune page: {put_res.status_code} {put_res.text}")
            return False

        # 1) Update existing automation page (best case)
        for p in pages:
            if isinstance(p, dict) and _is_editable(p) and _is_automation_page_name(_page_name(p)):
                if _put_page(p, name=desired_page_name):
                    return True
                break

        # 2) Try creating a new automation page (only if there's space)
        create_payload = {
            "name": desired_page_name,
            "primaryStyleId": primary_style_id,
            "subStyleId": sub_style_id,
            "selectedPerkIds": selected,
            "current": True,
        }
        create_res = lcu_request("POST", "/lol-perks/v1/pages", create_payload)
        if create_res.status_code in (200, 201, 204):
            print(f"[RUNES] Created rune page {desired_page_name}")
            return True

        # If we hit the page limit, try cleaning up old automation pages then retry.
        if (
            create_res.status_code == 400
            and isinstance(create_res.text, str)
            and "max pages reached" in create_res.text.lower()
        ):
            deleted_any = False
            for p in pages:
                if not isinstance(p, dict):
                    continue
                if not _is_editable(p) or not _is_deletable(p):
                    continue
                name = _page_name(p)
                if not (
                    _is_automation_page_name(name)
                    or name.startswith("Auto-")
                    or name.startswith("Custom-")
                    or name.startswith("Auto ")
                    or name.startswith("Custom ")
                ):
                    continue
                if p.get("current") is True:
                    continue
                pid = _page_id(p)
                if pid is None:
                    continue
                del_res = lcu_request("DELETE", f"/lol-perks/v1/pages/{pid}")
                if del_res.status_code in (200, 204):
                    deleted_any = True

            if deleted_any:
                retry_res = lcu_request("POST", "/lol-perks/v1/pages", create_payload)
                if retry_res.status_code in (200, 201, 204):
                    print(f"[RUNES] Created rune page {desired_page_name} (after cleanup)")
                    return True

            # 3) As a last resort, overwrite the currently selected editable page.
            current_page = next(
                (p for p in pages if isinstance(p, dict) and _is_editable(p) and p.get("current") is True),
                None,
            )
            any_editable = next((p for p in pages if isinstance(p, dict) and _is_editable(p)), None)
            target = current_page or any_editable
            if target is not None:
                # Last resort: overwrite & rename an editable page.
                if _put_page(target, name=desired_page_name):
                    return True

        print(f"[RUNES] Failed to create rune page: {create_res.status_code} {create_res.text}")
        return False

    except Exception as e:
        print(f"[RUNES] Error applying runes: {e}")
        return False


def automation_loop() -> None:
    """Arka planda çalışan otomasyon döngüsü (thread target)."""
    global RUNNING, CURRENT_CONFIG
    print("[AUTO] Automation loop started")
    last_queue_action_ts = 0.0

    while RUNNING:
        try:
            cfg = CURRENT_CONFIG
            if not cfg:
                time.sleep(1)
                continue

            primary_role = cfg.get("primary_role")
            secondary_role = cfg.get("secondary_role")

            auto_queue = bool(cfg.get("auto_queue", True))
            queue_id = cfg.get("queue_id")
            try:
                queue_id_int = int(queue_id) if queue_id is not None else None
            except Exception:
                queue_id_int = None

            flow_phase = get_gameflow_phase_safe()
            if auto_queue and queue_id_int:
                # Only try to create lobby / start search in idle/lobby phases.
                if flow_phase in (None, "None", "Lobby"):
                    now = time.time()
                    if now - last_queue_action_ts > 5:
                        if ensure_lobby(queue_id_int):
                            # Position preferences require an active lobby.
                            if primary_role or secondary_role:
                                body_roles: dict[str, str] = {}
                                if primary_role:
                                    body_roles["firstPreference"] = str(primary_role).upper()
                                if secondary_role:
                                    body_roles["secondPreference"] = str(secondary_role).upper()
                                if body_roles:
                                    lcu_request(
                                        "PUT",
                                        "/lol-lobby/v2/lobby/members/localMember/position-preferences",
                                        body_roles,
                                    )

                            ensure_matchmaking_searching()

                        last_queue_action_ts = now
            else:
                # Keep old behavior: only set roles (if lobby exists) but don't start queue.
                if primary_role or secondary_role:
                    body_roles: dict[str, str] = {}
                    if primary_role:
                        body_roles["firstPreference"] = str(primary_role).upper()
                    if secondary_role:
                        body_roles["secondPreference"] = str(secondary_role).upper()
                    if body_roles:
                        lcu_request(
                            "PUT",
                            "/lol-lobby/v2/lobby/members/localMember/position-preferences",
                            body_roles,
                        )

            try:
                rc_res = lcu_request("GET", "/lol-matchmaking/v1/ready-check")
                if rc_res.status_code == 200:
                    rc_json = rc_res.json()
                    if rc_json.get("state") == "InProgress":
                        lcu_request("POST", "/lol-matchmaking/v1/ready-check/accept")
            except Exception:
                pass

            session = None
            res = lcu_request("GET", "/lol-champ-select/v1/session")
            if res.status_code == 200:
                try:
                    session = res.json()
                except Exception:
                    session = None

            if session:
                phase = session.get("timer", {}).get("phase", "")

                my_cell = session.get("localPlayerCellId")
                assigned_role = ""
                for p in session.get("myTeam", []):
                    if p.get("cellId") == my_cell:
                        assigned_role = p.get("assignedPosition", "").upper()
                        break

                role_bans = cfg.get("role_bans") or {}
                ban_id = normalize_champion_id(role_bans.get(assigned_role)) if assigned_role else None
                if ban_id is None and assigned_role == "":
                    p_role = str(cfg.get("primary_role", "")).upper()
                    ban_id = normalize_champion_id(role_bans.get(p_role))

                if ban_id is not None:
                    do_ban(session, ban_id)

                role_champs = cfg.get("role_champions", {})
                my_champs = role_champs.get(assigned_role, [])
                if not my_champs and assigned_role == "":
                    p_role = str(cfg.get("primary_role", "")).upper()
                    my_champs = role_champs.get(p_role, [])

                if my_champs:
                    auto_pick_impl(session, my_champs)

                if phase == "FINALIZATION":
                    if not cfg.get("runes_applied"):
                        role_for_runes = assigned_role or str(cfg.get("primary_role", "")).upper()
                        if apply_runes_impl(session, cfg, role_for_runes):
                            CURRENT_CONFIG["runes_applied"] = True
                else:
                    CURRENT_CONFIG["runes_applied"] = False

                spell_role_key = assigned_role or str(cfg.get("primary_role", "")).upper()

                role_spell_map = cfg.get("role_summoner_spells")
                role_entry = role_spell_map.get(spell_role_key) if isinstance(role_spell_map, dict) else None

                my_spell_champ_id = 0
                for p in session.get("myTeam", []):
                    if p.get("cellId") == my_cell:
                        my_spell_champ_id = normalize_champion_id(p.get("championId") or 0) or 0
                        if my_spell_champ_id == 0:
                            my_spell_champ_id = normalize_champion_id(p.get("championPickIntent") or 0) or 0
                        break

                custom_entry = None
                custom_spell_map = cfg.get("custom_summoner_spells")
                if my_spell_champ_id and isinstance(custom_spell_map, dict):
                    role_custom = custom_spell_map.get(spell_role_key)
                    if isinstance(role_custom, dict):
                        custom_entry = role_custom.get(str(my_spell_champ_id))
                        if custom_entry is None:
                            custom_entry = role_custom.get(my_spell_champ_id)

                has_s1, s1, has_s2, s2 = extract_spell_pair(custom_entry)
                r_has_s1, r_s1, r_has_s2, r_s2 = extract_spell_pair(role_entry)

                if not has_s1 and r_has_s1:
                    has_s1 = True
                    s1 = r_s1
                if not has_s2 and r_has_s2:
                    has_s2 = True
                    s2 = r_s2

                if not has_s1:
                    s1 = normalize_spell_id(cfg.get("primary_summoner_spell"))
                if not has_s2:
                    s2 = normalize_spell_id(cfg.get("secondary_summoner_spell"))

                if s1 or s2:
                    body = {}
                    if s1:
                        body["spell1Id"] = s1
                    if s2:
                        body["spell2Id"] = s2
                    if body:
                        lcu_request("PATCH", "/lol-champ-select/v1/session/my-selection", body)
        except Exception as e:
            print(f"[AUTO] Loop error: {e}")
            time.sleep(1)

        time.sleep(1)

# -----------------------------------------------------------------------------
# ENDPOINTS
# -----------------------------------------------------------------------------
@app.post("/start_automation")
def start_automation(config: AutomationConfig):
    """Otomasyonu başlatır veya çalışan konfigürasyonu günceller."""
    global RUNNING, CURRENT_CONFIG, AUTOMATION_THREAD
    with AUTOMATION_LOCK:
        CURRENT_CONFIG = config.model_dump()
        already_running = bool(RUNNING)
        RUNNING = True

        if AUTOMATION_THREAD is None or not AUTOMATION_THREAD.is_alive():
            AUTOMATION_THREAD = threading.Thread(target=automation_loop, daemon=True)
            AUTOMATION_THREAD.start()

    return {"status": "updated" if already_running else "started", "config": CURRENT_CONFIG}

@app.post("/stop_automation")
def stop_automation():
    """Otomasyonu durdurur (thread bir sonraki turda döngüden çıkar)."""
    global RUNNING
    with AUTOMATION_LOCK:
        RUNNING = False
    return {"status": "stopped"}
