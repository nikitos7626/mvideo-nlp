from __future__ import annotations

import csv
from pathlib import Path

# backend/data/dictionaries — относительно этого файла
# parents[3] поднимается из app/extractors/normalization до backend/
DICT_DIR = Path(__file__).resolve().parents[3] / "data" / "dictionaries"


def load_pairs(filename: str) -> dict[str, str]:
    """
    Читает CSV с двумя колонками: alias,canonical.
    Возвращает {alias_lower: canonical}.
    Игнорирует пустые строки и строки с # (комментарии).
    """
    path = DICT_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Dictionary not found: {path}")

    out: dict[str, str] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header_skipped = False
        for row in reader:
            if not row or not row[0].strip():
                continue
            if row[0].lstrip().startswith("#"):
                continue
            if not header_skipped:
                header_skipped = True
                # пропускаем шапку "alias,canonical"
                if row[0].strip().lower() == "alias":
                    continue
            alias = row[0].strip().lower()
            canon = row[1].strip() if len(row) > 1 else row[0].strip()
            if alias and canon:
                out[alias] = canon
    return out


def load_colors(filename: str = "colors.csv") -> dict[str, tuple[str, int]]:
    """
    Читает CSV с тремя колонками: alias,canonical,priority.
    Возвращает {alias_lower: (canonical, priority)}.
    """
    path = DICT_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Dictionary not found: {path}")

    out: dict[str, tuple[str, int]] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header_skipped = False
        for row in reader:
            if not row or not row[0].strip():
                continue
            if row[0].lstrip().startswith("#"):
                continue
            if not header_skipped:
                header_skipped = True
                if row[0].strip().lower() == "alias":
                    continue
            alias = row[0].strip().lower()
            canon = row[1].strip() if len(row) > 1 else alias
            try:
                prio = int(row[2]) if len(row) > 2 else 100
            except ValueError:
                prio = 100
            if alias and canon:
                out[alias] = (canon, prio)
    return out