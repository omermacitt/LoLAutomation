"""RunePilot automation loop — background thread for lobby management, pick/ban, runes, spells, and skins."""

from __future__ import annotations

import threading
import time
from typing import Any

from rune_pilot.infrastructure.lcu_client import lcu_request
from rune_pilot.domain.champion_service import normalize_champion_id, normalize_spell_id
from rune_pilot.application.rune_service import (
    get_recommended_page_for_champion,
    build_rune_page_name,
)
from rune_pilot.application.champion_query import get_champion_name_by_id
from rune_pilot.shared.utils import safe_int_list
from rune_pilot.application.lobby_service import (
    do_ban,
    auto_pick_impl,
    extract_spell_pair,
    get_gameflow_phase_safe,
    ensure_lobby,
    ensure_matchmaking_searching,
)

# ---------------------------------------------------------------------------
# GLOBAL STATE
# ---------------------------------------------------------------------------
RUNNING = False
CURRENT_CONFIG: dict[str, Any] = {}
AUTOMATION_THREAD: threading.Thread | None = None
AUTOMATION_LOCK = threading.Lock()


def apply_runes_impl(session: dict[str, Any], cfg: dict[str, Any]) -> bool:
    """
    Applies the rune page for the currently selected champion.

    Priority:
    1) User-selected custom preset (if configured)
    2) Highest win-rate recommendation from runes.json
    """
    my_cell = session.get("localPlayerCellId")
    my_champ_id = 0
    for p in session.get("myTeam", []):
        if p.get("cellId") == my_cell:
            my_champ_id = p.get("championId", 0) or 0
            if my_champ_id == 0:
                my_champ_id = p.get("championPickIntent", 0) or 0
            break

    if my_champ_id == 0:
        return False

    try:
        champ_key = str(my_champ_id)

        selection = 0
        try:
            selection_map = cfg.get("rune_selection") or {}
            if isinstance(selection_map, dict):
                selection = int(selection_map.get(champ_key, 0) or 0)
        except (TypeError, ValueError):
            selection = 0
        if selection not in (0, 1, 2, 3):
            selection = 0

        page_data: dict | None = None
        used_custom = False
        used_slot: int | None = None

        if selection in (1, 2, 3):
            custom_runes = cfg.get("custom_runes") or {}
            champ_presets = custom_runes.get(champ_key) if isinstance(custom_runes, dict) else None
            champ_presets = champ_presets if isinstance(champ_presets, dict) else {}
            custom_page = champ_presets.get(str(selection))

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

                if candidate is not None and len(safe_int_list(candidate.get("selectedPerkIds"))) != 9:
                    candidate = None

                if candidate is None:
                    print(
                        f"[RUNES] Invalid custom rune preset slot={selection} championId={my_champ_id}, falling back to recommended"
                    )
                else:
                    page_data = candidate
                    used_custom = True
                    used_slot = selection
            else:
                print(
                    f"[RUNES] Custom rune preset not found slot={selection} championId={my_champ_id}, falling back to recommended"
                )

        if page_data is None:
            recommended = get_recommended_page_for_champion(my_champ_id)
            if not recommended:
                print(f"[RUNES] No recommended runes found for championId={my_champ_id}")
                return False
            page_data = {**recommended}
            used_custom = False

        champ_name = get_champion_name_by_id(my_champ_id) or str(my_champ_id)
        if used_custom and used_slot is not None:
            name_prefix = f"Custom {used_slot}"
        else:
            name_prefix = "Auto"
        desired_page_name = build_rune_page_name(prefix=name_prefix, champion_name=champ_name)
        page_data["name"] = desired_page_name

        try:
            primary_style_id = int(page_data.get("primaryStyleId"))
            sub_style_id = int(page_data.get("subStyleId"))
        except (TypeError, ValueError):
            print(f"[RUNES] Invalid style ids for championId={my_champ_id}: {page_data}")
            return False

        selected = safe_int_list(page_data.get("selectedPerkIds"))
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
            return page.get("isEditable") is not False

        def _is_deletable(page: dict) -> bool:
            if "isDeletable" not in page:
                return False
            return page.get("isDeletable") is True

        def _is_automation_page_name(name: str) -> bool:
            n = (name or "").strip()
            if not n:
                return False
            if n.startswith("Auto ") or n.startswith("Custom ") or n.startswith("Auto-") or n.startswith("Custom-"):
                return True
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
                if _put_page(target, name=desired_page_name):
                    return True

        print(f"[RUNES] Failed to create rune page: {create_res.status_code} {create_res.text}")
        return False

    except Exception as e:
        print(f"[RUNES] Error applying runes: {e}")
        return False


def automation_loop() -> None:
    """Background automation loop (thread target)."""
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
                        if apply_runes_impl(session, cfg):
                            cfg["runes_applied"] = True
                else:
                    cfg["runes_applied"] = False

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

                try:
                    if my_spell_champ_id:
                        base_skin_id = int(my_spell_champ_id) * 1000
                        desired_skin_id = base_skin_id

                        custom_skins = cfg.get("custom_skins")
                        if isinstance(custom_skins, dict):
                            role_skins = custom_skins.get(spell_role_key)
                            if isinstance(role_skins, dict):
                                raw = role_skins.get(str(my_spell_champ_id))
                                if raw is None:
                                    raw = role_skins.get(my_spell_champ_id)
                                try:
                                    desired_skin_id = int(raw)
                                except (TypeError, ValueError):
                                    desired_skin_id = base_skin_id

                        skin_key = f"{my_spell_champ_id}:{desired_skin_id}"
                        if cfg.get("skin_applied_key") != skin_key:
                            lcu_request(
                                "PATCH",
                                "/lol-champ-select/v1/session/my-selection",
                                {"selectedSkinId": int(desired_skin_id)},
                            )
                            cfg["skin_applied_key"] = skin_key
                    else:
                        cfg.pop("skin_applied_key", None)
                except Exception as e:
                    print(f"[SKIN] Failed to apply skin: {e}")
        except Exception as e:
            print(f"[AUTO] Loop error: {e}")
            time.sleep(1)

        time.sleep(1)
