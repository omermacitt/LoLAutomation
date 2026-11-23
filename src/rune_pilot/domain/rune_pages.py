"""Pure rules for choosing which League rune page automation may update, delete or overwrite."""

from typing import Any

AUTOMATION_PAGE_PREFIXES = ("Auto ", "Custom ", "Auto-", "Custom-", "LoLAutomation")


def page_id(page: dict) -> int | None:
    try:
        return int(page.get("id"))
    except (TypeError, ValueError):
        return None


def page_name(page: dict) -> str:
    return str(page.get("name") or "")


def is_editable(page: dict) -> bool:
    return page.get("isEditable") is not False


def is_deletable(page: dict) -> bool:
    """Only an explicit `isDeletable: true` allows deletion."""
    return page.get("isDeletable") is True


def is_automation_page_name(name: str) -> bool:
    """Pages named by RunePilot (or its older LoLAutomation name) belong to automation."""
    return (name or "").strip().startswith(AUTOMATION_PAGE_PREFIXES)


def _pages(pages: list[Any]) -> list[dict]:
    return [page for page in pages if isinstance(page, dict)]


def update_target(pages: list[Any]) -> dict | None:
    """The first editable automation page; it is reused before creating another page."""
    return next(
        (p for p in _pages(pages) if is_editable(p) and is_automation_page_name(page_name(p))),
        None,
    )


def cleanup_candidate_ids(pages: list[Any]) -> list[int]:
    """Non-current, editable, explicitly deletable automation pages, in client order."""
    result = []
    for p in _pages(pages):
        if not is_editable(p) or not is_deletable(p) or p.get("current") is True:
            continue
        if not is_automation_page_name(page_name(p)):
            continue
        pid = page_id(p)
        if pid is not None:
            result.append(pid)
    return result


def last_resort_target(pages: list[Any]) -> dict | None:
    """The current editable page, otherwise any editable page."""
    editable = [p for p in _pages(pages) if is_editable(p)]
    return next((p for p in editable if p.get("current") is True), None) or next(
        iter(editable), None
    )


def rune_page_payload(
    name: str, primary_style_id: int, sub_style_id: int, selected: list[int]
) -> dict[str, Any]:
    return {
        "name": name,
        "primaryStyleId": primary_style_id,
        "subStyleId": sub_style_id,
        "selectedPerkIds": selected,
        "current": True,
    }
