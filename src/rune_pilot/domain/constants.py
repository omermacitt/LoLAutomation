"""
RunePilot sabit değerleri.

Rune stilleri, oyun modları, roller ve büyücü büyüleri.
"""

from __future__ import annotations

# Rune style ID'leri
STYLE_ID_BY_NAME: dict[str, int] = {
    "precision": 8000,
    "domination": 8100,
    "sorcery": 8200,
    "inspiration": 8300,
    "resolve": 8400,
}

MAX_RUNE_PAGE_NAME_LEN = 16

# Oyun modu kuyruğu ID'leri
QUEUE_MODES: dict[str, int] = {
    "Normal Draft": 400,
    "Ranked Solo/Duo": 420,
    "Ranked Flex": 440,
}

# Rol tanımları
ROLES: dict[str, str | None] = {
    "Yok": None,
    "Top": "TOP",
    "Jungle": "JUNGLE",
    "Mid": "MIDDLE",
    "ADC": "BOTTOM",
    "Support": "UTILITY",
}

# Büyücü büyüleri
SUMMONER_SPELLS: dict[str, int | None] = {
    "Yok": None,
    "Sıçra (Flash)": 4,
    "Tutuştur (Ignite)": 14,
    "Işınlan (Teleport)": 12,
    "Hayalet (Ghost)": 6,
    "İyileştirme (Heal)": 7,
    "Çarp (Smite)": 11,
    "Bitkinlik (Exhaust)": 3,
    "Bariyer (Barrier)": 21,
    "Arındır (Cleanse)": 1,
}

SPELL_NAME_BY_ID: dict[int, str] = {v: k for k, v in SUMMONER_SPELLS.items() if v is not None}
