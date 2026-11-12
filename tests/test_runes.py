"""
Rün mantığının karakterizasyon testleri.

Bu davranış Faz 3'te `domain/runes.py` + `domain/rune_naming.py`'ye taşınacak; testler
o zaman import yolunu güncelleyip aynı beklentileri koruyacak (regresyon kalkanı).
"""

from rune_pilot.domain import rune_rules as api
from rune_pilot.domain.constants import MAX_RUNE_PAGE_NAME_LEN
from rune_pilot.shared.utils import safe_int_list


def test_safe_int_list_filters_non_ints():
    assert safe_int_list(["1", "2", "x", 3, None]) == [1, 2, 3]


def test_safe_int_list_non_list_returns_empty():
    assert safe_int_list("nope") == []
    assert safe_int_list(None) == []


def test_build_rune_page_name_simple_fits():
    assert api.build_rune_page_name(prefix="Auto", champion_name="Annie") == "Auto Annie"


def test_build_rune_page_name_strips_punctuation_and_spaces():
    name = api.build_rune_page_name(prefix="Auto", champion_name="Aurelion Sol")
    assert name == "Auto AurelionSol"
    assert len(name) <= MAX_RUNE_PAGE_NAME_LEN


def test_build_rune_page_name_truncates_when_too_long():
    name = api.build_rune_page_name(prefix="Custom 1", champion_name="Aurelion Sol")
    assert len(name) <= MAX_RUNE_PAGE_NAME_LEN
    assert name.startswith("Custom 1")


def test_build_rune_page_name_defaults_on_empty():
    assert api.build_rune_page_name(prefix="", champion_name="") == "Auto Champion"
