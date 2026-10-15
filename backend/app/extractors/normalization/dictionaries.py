"""
Словари для Tier 1.

Данные лежат в backend/data/dictionaries/*.csv — их можно править
без изменения Python-кода.

BRANDS  : dict[str, str]            — alias → canonical
COLORS  : dict[str, tuple[str,int]] — alias → (canonical, priority)
"""
from __future__ import annotations

from app.extractors.normalization.loaders import load_pairs, load_colors

# Загружается один раз при импорте модуля — работает как синглтон.
BRANDS: dict[str, str] = load_pairs("brands.csv")
COLORS: dict[str, tuple[str, int]] = load_colors("colors.csv")

# UNITS оставляем в коде: их мало, и они не редактируются вручную.
UNITS: dict[str, list[str]] = {
    "memory":  ["гб", "gb", "тб", "tb", "гигабайт", "терабайт"],
    "screen":  ["дюйм", "дюйма", "дюймов", '"', "inch", "in", "”", "″"],
    "battery": ["мач", "mah", "а·ч", "ач"],
    "refresh": ["гц", "hz"],
}