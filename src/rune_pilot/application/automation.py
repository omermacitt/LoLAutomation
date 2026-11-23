"""Automation orchestration through injected League, lobby and rune services."""

import time
from collections.abc import Callable
from typing import Any

from rune_pilot.application.automation_state import AutomationProgress, AutomationSnapshot
from rune_pilot.application.automation_steps import (
    ChampSelectStep,
    LoadoutStep,
    QueueStep,
    RuneApplier,
)
from rune_pilot.application.champion_query import ChampionQuery
from rune_pilot.application.lobby_service import LobbyService
from rune_pilot.application.ports.league_client import LeagueClient
from rune_pilot.application.rune_service import RuneService
from rune_pilot.application.selection_feedback import SelectionFeedback
from rune_pilot.domain.automation_settings import AutomationSettings
from rune_pilot.domain.champ_select import assigned_role


class AutomationRunner:
    def __init__(
        self,
        client: LeagueClient,
        champions: ChampionQuery,
        runes: RuneService,
        lobby: LobbyService,
        *,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.time,
        feedback: SelectionFeedback | None = None,
        validate_rune: Callable[[dict], dict] | None = None,
    ):
        self._client = client
        self._lobby = lobby
        self._sleep = sleep
        self._now = now
        self.feedback = feedback if feedback is not None else SelectionFeedback()
        # Read at call time so the catalog validator can be replaced on a live runner.
        self._validate_rune = validate_rune
        self._runes = RuneApplier(
            client,
            champions,
            runes,
            self.feedback,
            lambda page: self._validate_rune(page) if self._validate_rune else page,
        )
        self._loadout = LoadoutStep(client)

    def apply_runes(
        self,
        session: dict[str, Any],
        cfg: dict[str, Any],
        *,
        should_run: Callable[[], bool] = lambda: True,
    ) -> bool:
        """Applies the configured preset or a valid League recommendation for the actual champion."""
        return self._runes.apply(
            session, AutomationSettings.from_mapping(cfg), should_run=should_run
        )

    def run(
        self,
        should_run: Callable[[], bool],
        get_snapshot: Callable[[], AutomationSnapshot],
        wait: Callable[[float], bool] | None = None,
    ) -> None:
        """
        Background automation loop (thread target).

        Settings are copied on each iteration. Progress belongs to this invocation,
        and a settings revision change resets it even if the values are identical.
        """
        print("[AUTO] Automation loop started")
        progress = AutomationProgress()
        queue = QueueStep(self._client, self._lobby, self._now)
        champ_select = ChampSelectStep(self._lobby, self.feedback)
        self.feedback.clear()
        self.feedback.clear_rune()
        pause = wait if wait is not None else self._sleep

        while should_run():
            try:
                snapshot = get_snapshot()
                cfg = snapshot.config
                if snapshot.revision != progress.revision:
                    progress.reset(snapshot.revision)
                if not cfg:
                    pause(1)
                    continue
                settings = AutomationSettings.from_mapping(cfg)
                if not self._iterate(
                    settings, snapshot.revision, progress, queue, champ_select, should_run, wait
                ):
                    break
            except Exception as e:
                print(f"[AUTO] Loop error: {e}")
                pause(1)

            pause(1)

    def _iterate(
        self,
        settings: AutomationSettings,
        revision: int,
        progress: AutomationProgress,
        queue: QueueStep,
        champ_select: ChampSelectStep,
        should_run: Callable[[], bool],
        wait: Callable[[float], bool] | None,
    ) -> bool:
        """One pass over queue and champion select; False means cancellation."""
        if not queue.run(settings, should_run, wait):
            return False

        session = self._champ_select_session()
        if not should_run():
            return False
        if not session:
            progress.reset(revision)
            champ_select.reset()
            self.feedback.clear()
            self.feedback.clear_rune()
            return True

        role = assigned_role(session)
        if not champ_select.run(session, settings, role, should_run) or not should_run():
            return False
        self._runes.sync(session, settings, role, progress, should_run)
        if not should_run():
            return False
        return self._loadout.run(
            session, settings, role, champ_select.handoff_key is not None, progress, should_run
        )

    def _champ_select_session(self) -> dict[str, Any] | None:
        reply = self._client.champ_select_session()
        if reply.status_code != 200:
            return None
        try:
            return reply.json()
        except Exception:
            return None
