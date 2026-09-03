"""RunePilot constants — rune styles, game modes, roles, and summoner spells."""

from __future__ import annotations

STYLE_ID_BY_NAME: dict[str, int] = {
    "precision": 8000,
    "domination": 8100,
    "sorcery": 8200,
    "inspiration": 8300,
    "resolve": 8400,
}

MAX_RUNE_PAGE_NAME_LEN = 16

QUEUE_MODES: dict[str, int] = {
    "Normal Draft": 400,
    "Ranked Solo/Duo": 420,
    "Ranked Flex": 440,
}

ROLES: dict[str, str | None] = {
    "None": None,
    "Top": "TOP",
    "Jungle": "JUNGLE",
    "Mid": "MIDDLE",
    "ADC": "BOTTOM",
    "Support": "UTILITY",
}

SUMMONER_SPELLS: dict[str, int | None] = {
    "None": None,
    "Flash": 4,
    "Ignite": 14,
    "Teleport": 12,
    "Ghost": 6,
    "Heal": 7,
    "Smite": 11,
    "Exhaust": 3,
    "Barrier": 21,
    "Cleanse": 1,
}

SPELL_NAME_BY_ID: dict[int, str] = {v: k for k, v in SUMMONER_SPELLS.items() if v is not None}
