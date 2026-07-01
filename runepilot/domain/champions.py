"""
Şampiyon kimlik/slug yardımcıları (saf domain mantığı).

`champion_slug_from_alias`, runes.json üretilirken kullanılan slug formatıyla
(bkz. webscrapping.py) birebir uyumlu olmalıdır.
"""

from __future__ import annotations

# LCU alias'ı ile runes.json slug'ının ayrıştığı özel durumlar.
_SPECIAL_SLUGS: dict[str, str] = {
    "MonkeyKing": "wukong",
    "FiddleSticks": "fiddlesticks",
}


def champion_slug_from_alias(alias: str) -> str:
    """LCU alias'ını (ör. "Annie", "MonkeyKing") runes.json slug'ına çevirir."""
    alias = (alias or "").strip()
    if alias in _SPECIAL_SLUGS:
        return _SPECIAL_SLUGS[alias]
    return alias.lower()
