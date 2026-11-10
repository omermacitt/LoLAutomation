"""Run real orchestration against a fake League Client without clocks or network."""

from unittest.mock import Mock, call

import pytest

from rune_pilot.application.automation import AutomationRunner
from rune_pilot.application.automation_state import AutomationSnapshot
from rune_pilot.application.champion_query import ChampionQuery
from rune_pilot.application.lobby_service import LobbyService
from rune_pilot.application.rune_service import RuneService


def reply(data=None, status=200, text=""):
    result = Mock(status_code=status, text=text)
    result.json.return_value = data
    return result


@pytest.fixture
def setup():
    client = Mock()
    client.champion_summary.return_value = reply([{"id": 1, "name": "Annie", "alias": "Annie"}])
    client.gameflow_phase.return_value = reply("ChampSelect")
    client.ready_check.return_value = reply({"state": "InProgress"})
    client.champ_select_session.return_value = reply(None, 404)
    client.pickable_champion_ids.return_value = reply([1, 2, 3])
    client.complete_action.return_value = reply(status=204)
    client.rune_pages.return_value = reply([])
    client.create_rune_page.return_value = reply(status=201)
    client.update_rune_page.return_value = reply(status=200)
    client.delete_rune_page.return_value = reply(status=204)
    client.set_selection.return_value = reply(status=204)
    page = {"primaryStyleId": 8000, "subStyleId": 8100, "selectedPerkIds": list(range(1, 10))}
    source = Mock()
    source.get_runes_data.return_value = {"1": page}
    champions = ChampionQuery(client)
    sleep = Mock()
    lobby = LobbyService(client, champions, sleep=sleep)
    runner = AutomationRunner(
        client, champions, RuneService(source, champions), lobby, sleep=sleep, now=lambda: 100.0
    )
    return client, runner, lobby, source


def session(phase="FINALIZATION"):
    return {
        "localPlayerCellId": 0,
        "timer": {"phase": phase},
        "myTeam": [{"cellId": 0, "championId": 1, "assignedPosition": "middle"}],
        "actions": [],
    }


def run_iterations(runner, snapshots):
    index = 0

    def wait(_seconds):
        nonlocal index
        if _seconds != 1:
            return False  # Lobby transition delays do not end an iteration.
        index += 1
        return index == len(snapshots)

    runner.run(lambda: index < len(snapshots), lambda: snapshots[index], wait)


def run_once(runner, config):
    run_iterations(runner, [AutomationSnapshot(1, config)])


def test_finalization_accepts_ready_applies_runes_spells_and_skin(setup):
    client, runner, _, _ = setup
    client.champ_select_session.return_value = reply(session())
    config = {
        "auto_queue": False,
        "primary_role": "TOP",
        "primary_summoner_spell": 4,
        "secondary_summoner_spell": 14,
        "role_summoner_spells": {"MIDDLE": {"spell1Id": 12, "spell2Id": 4}},
        "custom_summoner_spells": {"MIDDLE": {"1": {"spell1Id": None}}},
        "custom_skins": {"MIDDLE": {"1": 1001}},
    }
    run_iterations(runner, [AutomationSnapshot(1, config)] * 2)
    assert client.accept_ready_check.call_count == 2
    client.create_rune_page.assert_called_once()
    assert client.create_rune_page.call_args.args[0]["name"] == "Auto Annie"
    assert client.set_selection.call_args_list == [
        call({"spell2Id": 4}),
        call({"selectedSkinId": 1001}),
        call({"spell2Id": 4}),
    ]
    assert "runes_applied" not in config
    assert "skin_applied_key" not in config
    assert client.create_rune_page.call_count == 1
    assert client.set_selection.call_args_list.count(call({"selectedSkinId": 1001})) == 1


def test_idle_queue_replaces_wrong_lobby_sets_roles_then_starts_search(setup):
    client, runner, _, _ = setup
    client.gameflow_phase.return_value = reply("Lobby")
    client.lobby.return_value = reply({"gameConfig": {"queueId": 440}})
    client.create_lobby.return_value = reply(status=201)
    client.matchmaking_search_state.return_value = reply({"searchState": "NotSearching"})
    run_once(
        runner,
        {"queue_id": "420", "auto_queue": True, "primary_role": "middle", "secondary_role": "top"},
    )
    names = [entry[0] for entry in client.mock_calls]
    assert (
        names.index("delete_lobby")
        < names.index("create_lobby")
        < names.index("set_position_preferences")
        < names.index("start_matchmaking")
    )
    client.create_lobby.assert_called_once_with(420)
    client.set_position_preferences.assert_called_once_with(
        {"firstPreference": "MIDDLE", "secondPreference": "TOP"}
    )


def test_matching_lobby_and_active_search_are_not_recreated(setup):
    client, _, lobby, _ = setup
    client.lobby.return_value = reply({"gameConfig": {"queueId": 420}})
    client.matchmaking_search_state.return_value = reply({"searchState": "Searching"})
    assert lobby.ensure_lobby(420)
    lobby.ensure_matchmaking_searching()
    client.delete_lobby.assert_not_called()
    client.create_lobby.assert_not_called()
    client.start_matchmaking.assert_not_called()


def test_ban_protects_teammate_hover_and_pick_retries_next_preference(setup):
    client, _, lobby, _ = setup
    current = {
        "localPlayerCellId": 0,
        "myTeam": [{"cellId": 1, "championPickIntent": 2}],
        "bans": {"myTeamBans": [3]},
        "actions": [
            [
                {"type": "ban", "actorCellId": 0, "id": 10, "completed": False},
                {"type": "pick", "actorCellId": 0, "id": 11, "completed": False},
            ]
        ],
    }
    lobby.do_ban(current, 2)
    client.complete_action.assert_not_called()
    client.complete_action.side_effect = [reply(status=400), reply(status=204)]
    assert lobby.auto_pick_impl(current, [3, 1, 2]) == {"status": "picked", "champion": 2}
    assert client.complete_action.call_args_list == [call(11, 1), call(11, 2)]


def test_custom_runes_update_existing_page_without_reading_recommendations(setup):
    client, runner, _, source = setup
    client.rune_pages.return_value = reply([{"id": 5, "name": "Auto Old", "isEditable": True}])
    custom = {"primaryStyleId": 8200, "subStyleId": 8100, "selectedPerkIds": list(range(11, 20))}
    assert runner.apply_runes(
        session(), {"rune_selection": {"1": 2}, "custom_runes": {"1": {"2": custom}}}
    )
    assert client.update_rune_page.call_args.args == (
        5,
        {"id": 5, "name": "Custom 2 Annie", **custom, "current": True},
    )
    source.get_runes_data.assert_not_called()
    client.create_rune_page.assert_not_called()


def test_page_limit_cleans_only_noncurrent_deletable_automation_pages(setup):
    client, runner, _, _ = setup
    client.rune_pages.return_value = reply(
        [
            {"id": 1, "name": "My page", "isEditable": True, "isDeletable": True},
            {"id": 2, "name": "Auto Old", "isEditable": True, "isDeletable": True},
            {
                "id": 3,
                "name": "Custom Current",
                "isEditable": True,
                "isDeletable": True,
                "current": True,
            },
            {"id": 4, "name": "Auto Locked", "isEditable": False, "isDeletable": True},
        ]
    )
    client.update_rune_page.return_value = reply(status=400)
    client.create_rune_page.side_effect = [
        reply(status=400, text="Max pages reached"),
        reply(status=201),
    ]
    assert runner.apply_runes(session(), {})
    client.delete_rune_page.assert_called_once_with(2)
    assert client.create_rune_page.call_count == 2


def test_invalid_custom_preset_falls_back_and_failed_creation_is_not_success(setup):
    client, runner, _, source = setup
    client.create_rune_page.return_value = reply(status=500)
    assert not runner.apply_runes(
        session(),
        {"rune_selection": {"1": 1}, "custom_runes": {"1": {"1": {"selectedPerkIds": [1]}}}},
    )
    source.get_runes_data.assert_called_once()
    assert client.create_rune_page.call_args.args[0]["name"] == "Auto Annie"


def test_direct_recommendation_does_not_need_lcu_champion_metadata(setup):
    client, runner, _, source = setup
    champions = ChampionQuery(client)
    service = RuneService(source, champions)
    client.champion_summary.side_effect = OSError("offline")
    assert service.get_recommended_page_for_champion(1)["primaryStyleId"] == 8000
    client.champion_summary.assert_not_called()


def test_same_settings_revision_retries_failed_skin_and_new_revision_reapplies(setup):
    client, runner, _, _ = setup
    client.champ_select_session.return_value = reply(session())
    client.set_selection.side_effect = [reply(status=400), reply(status=204), reply(status=204)]
    config = {"auto_queue": False, "custom_skins": {"MIDDLE": {"1": 1001}}}
    run_iterations(runner, [AutomationSnapshot(1, config)] * 3 + [AutomationSnapshot(2, config)])
    assert client.set_selection.call_args_list == [call({"selectedSkinId": 1001})] * 3
    assert client.create_rune_page.call_count == 2
    assert config == {"auto_queue": False, "custom_skins": {"MIDDLE": {"1": 1001}}}


def test_missing_session_resets_progress_for_next_game_and_restart_has_fresh_state(setup):
    client, runner, _, _ = setup
    client.champ_select_session.side_effect = [reply(session()), reply(None, 404), reply(session())]
    config = {"auto_queue": False}
    run_iterations(runner, [AutomationSnapshot(1, config)] * 3)
    assert client.create_rune_page.call_count == 2
    assert client.set_selection.call_count == 2
    client.champ_select_session.side_effect = None
    client.champ_select_session.return_value = reply(session())
    run_once(runner, config)
    assert client.create_rune_page.call_count == 3
    assert client.set_selection.call_count == 3


def test_champion_change_and_nonfinal_phase_reapply_runes(setup):
    client, runner, _, source = setup
    source.get_runes_data.return_value["2"] = source.get_runes_data.return_value["1"]
    other = session()
    other["myTeam"][0]["championId"] = 2
    client.champ_select_session.side_effect = [
        reply(session()),
        reply(other),
        reply(session("BAN_PICK")),
        reply(session()),
    ]
    run_iterations(runner, [AutomationSnapshot(1, {"auto_queue": False})] * 4)
    assert client.create_rune_page.call_count == 3


def test_cancel_during_rune_read_prevents_any_rune_write(setup):
    client, runner, _, _ = setup
    running = True

    def read_pages():
        nonlocal running
        running = False
        return reply([{"id": 5, "name": "Auto Old"}])

    client.rune_pages.side_effect = read_pages
    assert not runner.apply_runes(session(), {}, should_run=lambda: running)
    client.update_rune_page.assert_not_called()
    client.create_rune_page.assert_not_called()
    client.delete_rune_page.assert_not_called()


def test_cancel_during_pickable_read_prevents_pick_and_during_lobby_read_prevents_delete(setup):
    client, _, lobby, _ = setup
    running = True

    def pickable():
        nonlocal running
        running = False
        return reply([1])

    client.pickable_champion_ids.side_effect = pickable
    current = picking()
    assert lobby.auto_pick_impl(current, [1], should_run=lambda: running) == {"status": "cancelled"}
    client.complete_action.assert_not_called()
    running = True

    def read_lobby():
        nonlocal running
        running = False
        return reply({"gameConfig": {"queueId": 440}})

    client.lobby.side_effect = read_lobby
    assert not lobby.ensure_lobby(420, should_run=lambda: running)
    client.delete_lobby.assert_not_called()
    client.create_lobby.assert_not_called()


def picking(role="jungle", champion=0, intent=0, game=1, phase="BAN_PICK", active=True):
    return {
        "gameId": game,
        "localPlayerCellId": 0,
        "timer": {"phase": phase},
        "myTeam": [
            {
                "cellId": 0,
                "championId": champion,
                "championPickIntent": intent,
                "assignedPosition": role,
            }
        ],
        "actions": [
            [
                {
                    "id": 10,
                    "actorCellId": 0,
                    "type": "pick",
                    "completed": bool(champion),
                    "isInProgress": active,
                }
            ]
        ],
    }


def test_autofill_empty_pool_hands_off_without_using_primary_role_and_stays_manual_after_update(
    setup,
):
    client, runner, _, _ = setup
    client.champ_select_session.return_value = reply(picking())
    base = {"auto_queue": False, "primary_role": "MIDDLE", "role_champions": {"MIDDLE": [1]}}
    run_iterations(
        runner,
        [
            AutomationSnapshot(1, base),
            AutomationSnapshot(2, {**base, "role_champions": {"JUNGLE": [2]}}),
        ],
    )
    client.complete_action.assert_not_called()
    notice = runner.feedback.read()
    assert notice.code == "no_preference"
    assert notice.role == "JUNGLE"
    assert notice.id == 1


def test_empty_autofill_pool_warns_before_pick_turn_starts(setup):
    client, runner, _, _ = setup
    client.champ_select_session.return_value = reply(picking(active=False))
    run_once(
        runner, {"auto_queue": False, "primary_role": "MIDDLE", "role_champions": {"MIDDLE": [1]}}
    )
    assert runner.feedback.read().code == "no_preference"
    client.complete_action.assert_not_called()


def test_all_banned_or_taken_preferences_require_manual_choice_without_random_pick(setup):
    client, runner, _, _ = setup
    current = picking()
    current["bans"] = {"myTeamBans": [1], "theirTeamBans": [2]}
    current["theirTeam"] = [{"championId": 3}]
    client.champ_select_session.return_value = reply(current)
    run_iterations(
        runner,
        [AutomationSnapshot(1, {"auto_queue": False, "role_champions": {"JUNGLE": [1, 2, 3]}})] * 3,
    )
    client.complete_action.assert_not_called()
    assert runner.feedback.read().code == "all_unavailable"
    assert runner.feedback.read().id == 1


def test_banned_first_and_taken_second_choose_third_preference(setup):
    client, runner, _, _ = setup
    current = picking()
    current["bans"] = {"theirTeamBans": [1]}
    current["theirTeam"] = [{"championId": 2}]
    client.champ_select_session.return_value = reply(current)
    run_once(runner, {"auto_queue": False, "role_champions": {"JUNGLE": [1, 2, 3]}})
    client.complete_action.assert_called_once_with(10, 3)
    assert runner.feedback.read() is None


def test_hover_is_respected_even_when_cleared_until_the_next_session(setup):
    client, runner, _, _ = setup
    client.champ_select_session.side_effect = [
        reply(picking(intent=2)),
        reply(picking()),
        reply(picking(game=2)),
    ]
    run_iterations(
        runner,
        [AutomationSnapshot(1, {"auto_queue": False, "role_champions": {"JUNGLE": [1]}})] * 3,
    )
    client.complete_action.assert_called_once_with(10, 1)
    assert runner.feedback.read() is None


def test_manual_lock_clears_notice_and_applies_actual_champion_customizations(setup):
    client, runner, _, source = setup
    client.champ_select_session.side_effect = [
        reply(picking()),
        reply(picking(champion=2, phase="FINALIZATION")),
    ]
    custom = {"primaryStyleId": 8200, "subStyleId": 8100, "selectedPerkIds": list(range(11, 20))}
    config = {
        "auto_queue": False,
        "primary_role": "MIDDLE",
        "role_champions": {"MIDDLE": [1]},
        "primary_summoner_spell": 4,
        "secondary_summoner_spell": 7,
        "custom_summoner_spells": {"JUNGLE": {"2": {"spell1Id": 4, "spell2Id": 11}}},
        "custom_skins": {"JUNGLE": {"2": 2001}},
        "custom_runes": {"2": {"2": custom}},
        "rune_selection": {"2": 2},
    }
    run_iterations(runner, [AutomationSnapshot(1, config)] * 2)
    client.complete_action.assert_not_called()
    assert runner.feedback.read() is None
    assert client.create_rune_page.call_args.args[0]["selectedPerkIds"] == custom["selectedPerkIds"]
    source.get_runes_data.assert_not_called()
    assert client.set_selection.call_args_list == [
        call({"spell1Id": 4, "spell2Id": 11}),
        call({"selectedSkinId": 2001}),
    ]


def test_replacement_champion_does_not_inherit_first_preferences_spells(setup):
    client, runner, _, _ = setup
    client.champ_select_session.return_value = reply(picking(role="middle", champion=2))
    run_once(
        runner,
        {
            "auto_queue": False,
            "primary_role": "MIDDLE",
            "role_champions": {"MIDDLE": [1, 2]},
            "role_summoner_spells": {"MIDDLE": {"spell1Id": 4, "spell2Id": 14}},
            "primary_summoner_spell": 4,
            "secondary_summoner_spell": 14,
        },
    )
    assert client.set_selection.call_args_list == [call({"selectedSkinId": 2000})]


def test_future_pick_action_and_locked_champion_are_never_overridden(setup):
    client, _, lobby, _ = setup
    assert lobby.auto_pick_impl(picking(active=False), [1]) == {"status": "no_pick_available"}
    assert lobby.auto_pick_impl(picking(champion=2), [1]) == {"status": "manual_selection"}
    assert lobby.auto_pick_impl(picking(intent=2), [1]) == {"status": "manual_selection"}
    client.complete_action.assert_not_called()
    client.pickable_champion_ids.assert_not_called()


def test_failed_pick_hands_off_and_notice_clears_when_session_ends(setup):
    client, runner, _, _ = setup
    client.champ_select_session.return_value = reply(picking())
    client.complete_action.return_value = reply(status=400)
    run_once(runner, {"auto_queue": False, "role_champions": {"JUNGLE": [1]}})
    assert runner.feedback.read().code == "pick_failed"
    client.champ_select_session.return_value = reply(None, 404)
    run_once(runner, {"auto_queue": False})
    assert runner.feedback.read() is None
