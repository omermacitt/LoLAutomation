"""Resolve the rune page for the actual champion and role, then write it to the client."""

from collections.abc import Callable
from typing import Any

from rune_pilot.application.automation_state import AutomationProgress
from rune_pilot.application.champion_query import ChampionQuery
from rune_pilot.application.game_query_service import QueryUnavailable
from rune_pilot.application.ports.league_client import LeagueClient
from rune_pilot.application.rune_service import RuneService
from rune_pilot.application.selection_feedback import SelectionFeedback
from rune_pilot.domain import rune_pages
from rune_pilot.domain.automation_settings import AutomationSettings
from rune_pilot.domain.champ_select import assigned_role, local_champion, local_player
from rune_pilot.domain.champion_service import normalize_champion_id
from rune_pilot.domain.rune_editor import RunePage
from rune_pilot.domain.rune_rules import build_rune_page_name
from rune_pilot.shared.utils import safe_int_list

WRITE_OK = (200, 201, 204)


class InvalidRunePage(Exception):
    """A page could not be resolved into a writable payload."""


class RuneApplier:
    def __init__(
        self,
        client: LeagueClient,
        champions: ChampionQuery,
        runes: RuneService,
        feedback: SelectionFeedback,
        validate_rune: Callable[[dict], dict] | None = None,
    ) -> None:
        self._client = client
        self._champions = champions
        self._runes = runes
        self._feedback = feedback
        self._validate_rune = validate_rune

    def sync(
        self,
        session: dict[str, Any],
        settings: AutomationSettings,
        role: str,
        progress: AutomationProgress,
        should_run: Callable[[], bool],
    ) -> None:
        """Apply once per role/champion during finalization; otherwise forget the last page."""
        locked = normalize_champion_id(local_player(session).get("championId"))
        if session.get("timer", {}).get("phase", "") == "FINALIZATION" and locked:
            rune_key = (role, locked)
            if progress.rune_key != rune_key and self.apply(
                session, settings, should_run=should_run
            ):
                progress.rune_key = rune_key
        else:
            progress.rune_key = None
            self._feedback.clear_rune()

    def validated_page(self, raw: dict) -> dict:
        # Production injects catalog-backed validation. Standalone runners still reject malformed pages.
        page = RunePage.model_validate(raw)
        if page.primaryStyleId == page.subStyleId or any(
            value <= 0 for value in page.selectedPerkIds
        ):
            raise ValueError("Invalid rune page")
        normalized = page.model_dump()
        return self._validate_rune(normalized) if self._validate_rune else normalized

    def apply(
        self,
        session: dict[str, Any],
        settings: AutomationSettings,
        *,
        should_run: Callable[[], bool] = lambda: True,
    ) -> bool:
        """
        Applies the rune page for the currently selected champion.

        Priority:
        1) User-selected custom preset (if configured)
        2) First catalog-valid League recommendation, preferring the assigned role
        """
        role = assigned_role(session)
        champion = local_champion(session)
        if champion == 0:
            return False
        try:
            resolved = self._resolve(settings, role, champion)
            if resolved is None:
                self._unavailable(role, champion)
                print(f"[RUNES] No recommended runes found for championId={champion}")
                return False
            page, prefix, fallback = resolved
            name = build_rune_page_name(
                prefix=prefix,
                champion_name=self._champions.get_champion_name_by_id(champion) or str(champion),
            )
            try:
                payload = _payload(page, name)
            except InvalidRunePage as error:
                self._unavailable(role, champion)
                print(f"[RUNES] {error} for championId={champion}: {page}")
                return False
            if not self._write(payload, should_run):
                return False
            if fallback:
                self._feedback.publish_rune(
                    (role, champion, "fallback"), "rune_fallback", role, champion
                )
            else:
                self._feedback.clear_rune()
            return True
        except QueryUnavailable:
            self._unavailable(role, champion)
            return False
        except Exception as e:
            print(f"[RUNES] Error applying runes: {e}")
            return False

    def _unavailable(self, role: str, champion: int) -> None:
        self._feedback.publish_rune(
            (role, champion, "unavailable"), "rune_unavailable", role, champion
        )

    def _resolve(
        self, settings: AutomationSettings, role: str, champion: int
    ) -> tuple[dict, str, bool] | None:
        """(page, name prefix, used fallback) or None when no valid page exists."""
        choice = settings.rune_choice(role, champion)
        fallback = choice.missing
        if choice.slot in (1, 2, 3):
            page = self._custom_page(settings, champion, choice.slot)
            if page is not None:
                return page, f"Custom {choice.slot}", fallback
            fallback = True
        if not settings.recommendations_enabled:
            return None
        for recommended in self._runes.get_recommended_pages(champion, role):
            try:
                return self.validated_page(recommended), "Auto", fallback
            except ValueError:
                continue
        return None

    def _custom_page(self, settings: AutomationSettings, champion: int, slot: int) -> dict | None:
        stored = settings.custom_rune_page(champion, slot)
        if not isinstance(stored, dict):
            print(
                f"[RUNES] Custom rune preset not found slot={slot} championId={champion}, falling back to recommended"
            )
            return None
        candidate = {
            "primaryStyleId": stored.get("primaryStyleId"),
            "subStyleId": stored.get("subStyleId"),
            "selectedPerkIds": stored.get("selectedPerkIds"),
        }
        try:
            int(candidate["primaryStyleId"])
            int(candidate["subStyleId"])
            well_formed = len(safe_int_list(candidate["selectedPerkIds"])) == 9
        except (TypeError, ValueError):
            well_formed = False
        if not well_formed:
            print(
                f"[RUNES] Invalid custom rune preset slot={slot} championId={champion}, falling back to recommended"
            )
            return None
        try:
            return self.validated_page(candidate)
        except ValueError:
            return None

    def _write(self, payload: dict[str, Any], should_run: Callable[[], bool]) -> bool:
        """Update an automation page, else create one, else clean up and retry or overwrite."""
        name = payload["name"]
        res = self._client.rune_pages()
        if res.status_code != 200:
            print(f"[RUNES] Failed to fetch rune pages: {res.status_code} {res.text}")
            return False
        pages = res.json()
        if not isinstance(pages, list):
            print(f"[RUNES] Unexpected /lol-perks/v1/pages response: {type(pages)}")
            return False

        target = rune_pages.update_target(pages)
        if target is not None and self._put(target, payload, should_run):
            return True

        if not should_run():
            return False
        created = self._client.create_rune_page(payload)
        if created.status_code in WRITE_OK:
            print(f"[RUNES] Created rune page {name}")
            return True

        if (
            created.status_code == 400
            and isinstance(created.text, str)
            and "max pages reached" in created.text.lower()
        ):
            deleted_any = False
            for pid in rune_pages.cleanup_candidate_ids(pages):
                if not should_run():
                    return False
                if self._client.delete_rune_page(pid).status_code in (200, 204):
                    deleted_any = True
            if deleted_any:
                if not should_run():
                    return False
                if self._client.create_rune_page(payload).status_code in WRITE_OK:
                    print(f"[RUNES] Created rune page {name} (after cleanup)")
                    return True
            # As a last resort, overwrite the currently selected editable page.
            target = rune_pages.last_resort_target(pages)
            if target is not None and self._put(target, payload, should_run):
                return True

        print(f"[RUNES] Failed to create rune page: {created.status_code} {created.text}")
        return False

    def _put(self, page: dict, payload: dict[str, Any], should_run: Callable[[], bool]) -> bool:
        if not should_run():
            return False
        pid = rune_pages.page_id(page)
        if pid is None:
            return False
        reply = self._client.update_rune_page(pid, {"id": pid, **payload})
        if reply.status_code in WRITE_OK:
            print(f"[RUNES] Updated rune page id={pid} name={payload['name']}")
            return True
        print(f"[RUNES] Failed to update rune page: {reply.status_code} {reply.text}")
        return False


def _payload(page: dict, name: str) -> dict[str, Any]:
    try:
        primary = int(page.get("primaryStyleId"))
        secondary = int(page.get("subStyleId"))
    except (TypeError, ValueError) as error:
        raise InvalidRunePage("Invalid style ids") from error
    selected = safe_int_list(page.get("selectedPerkIds"))
    if len(selected) != 9:
        raise InvalidRunePage("Invalid selectedPerkIds")
    return rune_pages.rune_page_payload(name, primary, secondary, selected)
