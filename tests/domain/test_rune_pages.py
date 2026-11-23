"""Pure rune page selection rules used by automation."""

import pytest

from rune_pilot.domain import rune_pages


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Auto Annie", True),
        ("Custom 2 Annie", True),
        ("Auto-VeryLongChampion", True),
        ("Custom-Ahri", True),
        ("  Auto Annie", True),
        ("LoLAutomation", True),
        ("LoLAutomation Annie", True),
        ("Automatic", False),
        ("My page", False),
        ("", False),
    ],
)
def test_automation_page_names(name, expected):
    assert rune_pages.is_automation_page_name(name) is expected


def test_update_target_is_first_editable_automation_page():
    pages = [
        "broken",
        {"id": 1, "name": "Auto Annie", "isEditable": False},
        {"id": 2, "name": "Mine"},
        {"id": 3, "name": "Custom 1 Ahri"},
        {"id": 4, "name": "Auto Zed"},
    ]
    assert rune_pages.update_target(pages)["id"] == 3
    assert rune_pages.update_target([{"id": 2, "name": "Mine"}]) is None


def test_cleanup_requires_explicit_deletable_noncurrent_automation_page_with_id():
    pages = [
        {"id": 1, "name": "Auto A", "isDeletable": True},
        {"id": 2, "name": "Auto B", "isDeletable": True, "current": True},
        {"id": 3, "name": "Auto C"},
        {"id": 4, "name": "Mine", "isDeletable": True},
        {"id": "x", "name": "Auto D", "isDeletable": True},
        {"id": 6, "name": "Custom-E", "isDeletable": True, "isEditable": False},
        {"id": 7, "name": "Custom 3 F", "isDeletable": True},
    ]
    assert rune_pages.cleanup_candidate_ids(pages) == [1, 7]


def test_last_resort_prefers_current_editable_then_any_editable():
    current = {"id": 2, "current": True}
    pages = [{"id": 1, "isEditable": False, "current": True}, {"id": 5}, current]
    assert rune_pages.last_resort_target(pages) is current
    assert rune_pages.last_resort_target([{"id": 5}])["id"] == 5
    assert rune_pages.last_resort_target([{"id": 1, "isEditable": False}]) is None


def test_payload_is_current_page():
    assert rune_pages.rune_page_payload("Auto A", 8000, 8100, [1] * 9) == {
        "name": "Auto A",
        "primaryStyleId": 8000,
        "subStyleId": 8100,
        "selectedPerkIds": [1] * 9,
        "current": True,
    }
