"""Each automation stage in isolation against a fake League Client."""

from unittest.mock import Mock

from rune_pilot.application.automation_state import AutomationProgress
from rune_pilot.application.automation_steps import ChampSelectStep, LoadoutStep, QueueStep
from rune_pilot.application.selection_feedback import SelectionFeedback


def reply(data=None, status=200):
    result = Mock(status_code=status, text="")
    result.json.return_value = data
    return result


def test_queue_step_throttles_lobby_actions_per_invocation():
    client, lobby, clock = Mock(), Mock(), [100.0]
    lobby.get_gameflow_phase_safe.return_value = "Lobby"
    lobby.ensure_lobby.return_value = True
    client.ready_check.return_value = reply({"state": "None"})
    step = QueueStep(client, lobby, lambda: clock[0])
    cfg = {"queue_id": 420, "primary_role": "top"}

    assert step.run(cfg, lambda: True, None)
    clock[0] = 104.0
    assert step.run(cfg, lambda: True, None)
    clock[0] = 106.0
    assert step.run(cfg, lambda: True, None)
    assert lobby.ensure_lobby.call_count == 2
    client.set_position_preferences.assert_called_with({"firstPreference": "TOP"})
    client.accept_ready_check.assert_not_called()


def test_queue_step_without_auto_queue_only_sets_roles_and_accepts_ready_check():
    client, lobby = Mock(), Mock()
    client.ready_check.return_value = reply({"state": "InProgress"})
    step = QueueStep(client, lobby, lambda: 0.0)
    assert step.run({"auto_queue": False, "secondary_role": "bottom"}, lambda: True, None)
    lobby.ensure_lobby.assert_not_called()
    client.set_position_preferences.assert_called_once_with({"secondPreference": "BOTTOM"})
    client.accept_ready_check.assert_called_once()


def test_queue_step_reports_cancellation_before_any_write():
    client, lobby = Mock(), Mock()
    assert not QueueStep(client, lobby, lambda: 0.0).run({"queue_id": 420}, lambda: False, None)
    lobby.ensure_lobby.assert_not_called()
    client.ready_check.assert_not_called()


def pick_session(**player):
    return {
        "gameId": 7,
        "localPlayerCellId": 0,
        "myTeam": [{"cellId": 0, **player}],
        "actions": [[{"id": 3, "type": "pick", "actorCellId": 0, "isInProgress": True}]],
    }


def test_champ_select_handoff_latches_until_reset():
    lobby, feedback = Mock(), SelectionFeedback()
    step = ChampSelectStep(lobby, feedback)
    assert step.run(pick_session(), {"role_champions": {}}, "TOP", lambda: True)
    assert step.handoff_key == (7, 0, 3)
    assert feedback.read().code == "no_preference"

    assert step.run(pick_session(), {"role_champions": {"TOP": [1]}}, "TOP", lambda: True)
    lobby.auto_pick_impl.assert_not_called()

    step.reset()
    lobby.auto_pick_impl.return_value = {"status": "picked", "champion": 1}
    assert step.run(pick_session(), {"role_champions": {"TOP": [1]}}, "TOP", lambda: True)
    lobby.auto_pick_impl.assert_called_once()
    assert step.handoff_key is None
    assert feedback.read() is None


def test_champ_select_bans_primary_role_choice_outside_role_queues():
    lobby = Mock()
    session = {**pick_session(), "actions": []}
    ChampSelectStep(lobby, SelectionFeedback()).run(
        session, {"primary_role": "jungle", "role_bans": {"JUNGLE": 5}}, "", lambda: True
    )
    lobby.do_ban.assert_called_once()
    assert lobby.do_ban.call_args.args[1] == 5


def test_loadout_waits_for_lock_during_handoff_and_skips_reapplied_skin():
    client = Mock()
    client.set_selection.return_value = reply(status=204)
    progress = AutomationProgress()
    cfg = {"custom_skins": {"TOP": {"1": 1002}}, "primary_summoner_spell": 4}
    hover = pick_session(championPickIntent=1)

    assert LoadoutStep(client).run(hover, cfg, "TOP", True, progress, lambda: True)
    client.set_selection.assert_not_called()
    assert progress.skin_key is None

    locked = pick_session(championId=1)
    step = LoadoutStep(client)
    assert step.run(locked, cfg, "TOP", True, progress, lambda: True)
    assert step.run(locked, cfg, "TOP", True, progress, lambda: True)
    skin_writes = [c for c in client.set_selection.call_args_list if "selectedSkinId" in c.args[0]]
    assert len(skin_writes) == 1
    assert skin_writes[0].args[0] == {"selectedSkinId": 1002}
