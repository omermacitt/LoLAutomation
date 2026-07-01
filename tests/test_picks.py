"""
Ban/pick karar mantığının karakterizasyon testleri.

Bu davranış Faz 3'te `domain/picks.py`'ye taşınacak.
"""

import api


def test_is_banned_detects_both_teams():
    session = {"bans": {"myTeamBans": [1, 2], "theirTeamBans": [3]}}
    assert api.is_banned(session, 1) is True
    assert api.is_banned(session, 3) is True
    assert api.is_banned(session, 99) is False


def test_is_banned_handles_missing_bans():
    assert api.is_banned({}, 1) is False
    assert api.is_banned({"bans": None}, 1) is False


def test_is_picked_true_when_champion_on_a_team():
    session = {
        "myTeam": [{"championId": 5}, {"championId": 0}],
        "theirTeam": [{"championId": 7}],
    }
    assert api.is_picked(session, 5) is True
    assert api.is_picked(session, 7) is True
    assert api.is_picked(session, 9) is False


def test_is_picked_zero_is_never_picked():
    session = {"myTeam": [{"championId": 0}], "theirTeam": []}
    assert api.is_picked(session, 0) is False


def test_is_teammate_showing_via_championId_and_intent():
    session = {"myTeam": [{"championId": 0, "championPickIntent": 42}]}
    assert api.is_teammate_showing(session, 42) is True

    session2 = {"myTeam": [{"championId": 11, "championPickIntent": 0}]}
    assert api.is_teammate_showing(session2, 11) is True

    assert api.is_teammate_showing(session2, 99) is False
