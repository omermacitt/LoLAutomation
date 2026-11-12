"""Pure rune page naming."""

import re

from rune_pilot.domain.constants import MAX_RUNE_PAGE_NAME_LEN


def build_rune_page_name(*, prefix: str, champion_name: str) -> str:
    """Generates a safe rune page name within the LoL client character limit."""
    prefix = (prefix or "").strip() or "Auto"
    champ = (champion_name or "").strip() or "Champion"

    # Prefer a compact (no spaces/punctuation) champion name to fit the client limit.
    champ_compact = re.sub(r"[^0-9A-Za-z]", "", champ)
    champ_base = champ_compact or champ

    # Prefer "Prefix Champion" then "Prefix-Champion", then truncate champion name.
    candidate = f"{prefix} {champ_base}"
    if len(candidate) <= MAX_RUNE_PAGE_NAME_LEN:
        return candidate

    candidate = f"{prefix}-{champ_base}"
    if len(candidate) <= MAX_RUNE_PAGE_NAME_LEN:
        return candidate

    sep = " "
    max_champ_len = MAX_RUNE_PAGE_NAME_LEN - (len(prefix) + len(sep))
    if max_champ_len <= 0:
        return prefix[:MAX_RUNE_PAGE_NAME_LEN]
    champ_trunc = champ_base[:max_champ_len]
    return f"{prefix}{sep}{champ_trunc}"
