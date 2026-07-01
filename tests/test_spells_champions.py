"""
Summoner spell çözümleme + şampiyon slug mantığının karakterizasyon testleri.

Faz 3'te `domain/spells.py` ve `domain/champions.py`'ye taşınacak.
"""

import api


# --- normalize_spell_id / normalize_champion_id -------------------------------
def test_normalize_spell_id():
    assert api.normalize_spell_id("4") == 4
    assert api.normalize_spell_id(0) is None
    assert api.normalize_spell_id(-3) is None
    assert api.normalize_spell_id("x") is None


def test_normalize_champion_id():
    assert api.normalize_champion_id("15") == 15
    assert api.normalize_champion_id(0) is None
    assert api.normalize_champion_id(None) is None


# --- extract_spell_pair -------------------------------------------------------
def test_extract_spell_pair_from_dict_ids():
    assert api.extract_spell_pair({"spell1Id": 4, "spell2Id": 7}) == (True, 4, True, 7)


def test_extract_spell_pair_from_dict_partial():
    assert api.extract_spell_pair({"spell1": 4}) == (True, 4, False, None)


def test_extract_spell_pair_from_list():
    assert api.extract_spell_pair([4, 7]) == (True, 4, True, 7)


def test_extract_spell_pair_none():
    assert api.extract_spell_pair(None) == (False, None, False, None)


def test_extract_spell_pair_present_key_but_invalid_value():
    # Anahtar var (has=True) ama 0 geçersiz → normalize None döner.
    assert api.extract_spell_pair({"spell1Id": 0, "spell2Id": 7}) == (True, None, True, 7)


# --- champion_slug_from_alias -------------------------------------------------
def test_champion_slug_specials():
    assert api.champion_slug_from_alias("MonkeyKing") == "wukong"
    assert api.champion_slug_from_alias("FiddleSticks") == "fiddlesticks"


def test_champion_slug_lowercases():
    assert api.champion_slug_from_alias("Annie") == "annie"
    assert api.champion_slug_from_alias("  Aatrox ") == "aatrox"


def test_champion_slug_empty():
    assert api.champion_slug_from_alias("") == ""
