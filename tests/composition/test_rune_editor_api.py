"""Rune editor validation uses injected metadata and never writes to League."""

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from rune_pilot.application.game_query_service import GameQueryService
from rune_pilot.application.rune_editor_service import RuneEditorService
from rune_pilot.composition.api_app import create_app
from rune_pilot.domain.rune_editor import normalize_editor_catalog


@pytest.fixture
def metadata():
    styles = []
    for sid in (8000, 8100):
        rows = [[sid + 1, sid + 2], [sid + 11, sid + 12], [sid + 21], [sid + 31]]
        slots = [
            {"perks": row, "type": "kKeyStone" if i == 0 else "kMixedRegularSplashable"}
            for i, row in enumerate(rows)
        ]
        slots += [
            {"perks": row, "type": "kStatMod"} for row in ([5008, 5005], [5008, 5001], [5001, 5011])
        ]
        styles.append(
            {
                "id": sid,
                "name": str(sid),
                "allowedSubStyles": [8000, 8100],
                "slots": slots,
                "iconPath": "perk-images/style.png",
            }
        )
    perks = [
        {"id": rid, "name": f"Rune {rid}", "longDesc": "<b>Damage</b><br> &amp; health"}
        for rid in {rid for style in styles for row in style["slots"] for rid in row["perks"]}
    ]
    return styles, perks


@pytest.fixture
def page():
    return {
        "name": "My page",
        "primaryStyleId": 8000,
        "subStyleId": 8100,
        "selectedPerkIds": [8001, 8011, 8021, 8031, 8111, 8121, 5008, 5008, 5001],
    }


def service(metadata, recommendation=None):
    styles, perks = metadata
    queries = GameQueryService(
        champion_summary=lambda: [],
        owned_champions=lambda: [],
        gameflow_phase=lambda: None,
        skin_options=lambda cid: ({}, set()),
        perk_styles=lambda: styles,
        perks=lambda: perks,
        perk_icon=lambda path: b"png",
    )
    return RuneEditorService(queries, lambda cid: recommendation), queries


def client_for(metadata, recommendation=None):
    editor, queries = service(metadata, recommendation)
    app = create_app(game_queries=queries)
    app.state.rune_editor = editor
    return TestClient(app)


def test_catalog_normalizes_lcu_rows_and_plain_descriptions(metadata):
    with client_for(metadata) as client:
        response = client.get("/runes/editor-catalog")
        assert response.status_code == 200
        style = response.json()["styles"][0]
        assert style["allowedSubStyles"] == [8100]
        assert len(style["rows"]) == 4
        assert len(style["shardRows"]) == 3
        assert style["rows"][0][0]["description"] == "Damage & health"
        assert client.get("/runes/icons/8000").content == b"png"


def test_embedded_legacy_rows_and_separate_stat_style(metadata):
    styles, perks = deepcopy(metadata)
    stat = {"id": 5000, "slots": styles[0]["slots"][4:]}
    for style in styles:
        style["perkSlots"] = [
            {"runes": [{"perkId": rid, "displayName": str(rid)} for rid in row["perks"]]}
            for row in style.pop("slots")[:4]
        ]
    catalog = normalize_editor_catalog(styles + [stat], perks)
    assert catalog.styles[0].rows[0][0].id == 8001
    assert catalog.styles[0].shardRows[0][0].id == 5008


@pytest.mark.parametrize("shards", [[5008, 5008, 5001], [5008, 5001, 5001]])
def test_legal_repeat_shards_are_valid(metadata, page, shards):
    page["selectedPerkIds"][6:] = shards
    with client_for(metadata) as client:
        response = client.post("/runes/validate", json=page)
    assert response.status_code == 200
    assert response.json() == page


@pytest.mark.parametrize(
    "change",
    [
        "same-style",
        "same-secondary-row",
        "secondary-keystone",
        "wrong-primary-row",
        "wrong-shard",
        "missing",
        "long-name",
    ],
)
def test_invalid_pages_rejected(metadata, page, change):
    if change == "same-style":
        page["subStyleId"] = 8000
    if change == "same-secondary-row":
        page["selectedPerkIds"][4:6] = [8111, 8112]
    if change == "secondary-keystone":
        page["selectedPerkIds"][4] = 8101
    if change == "wrong-primary-row":
        page["selectedPerkIds"][0] = 8011
    if change == "wrong-shard":
        page["selectedPerkIds"][8] = 5008
    if change == "missing":
        page["selectedPerkIds"].pop()
    if change == "long-name":
        page["name"] = "a" * 17
    with client_for(metadata) as client:
        assert client.post("/runes/validate", json=page).status_code == 422


@pytest.mark.parametrize("state", ["valid", "missing", "outdated"])
def test_recommendation_explicitly_reports_source_and_unavailable_data(metadata, page, state):
    recommendation = deepcopy(page) if state != "missing" else None
    if state == "outdated":
        recommendation["selectedPerkIds"][0] = 999999
    with client_for(metadata, recommendation) as client:
        response = client.get("/champions/266/runes/recommended")
    assert response.status_code == 200
    data = response.json()
    assert data["champion_id"] == 266
    assert data["source"] == "bundled"
    assert data["unavailableReason"] == (None if state == "valid" else state)
    assert bool(data["page"]) == (state == "valid")


def test_incomplete_metadata_fails_without_inventing_defaults(metadata):
    metadata[0][0]["slots"].pop()
    with client_for(metadata) as client:
        assert client.get("/runes/editor-catalog").status_code == 503
