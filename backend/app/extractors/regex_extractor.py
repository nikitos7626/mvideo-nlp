from __future__ import annotations

import re
from typing import Iterable

from flashtext import KeywordProcessor

from app.extractors.base import Prediction
from app.extractors.normalization.dictionaries import BRANDS, COLORS
from app.extractors.normalization.units import UnitNormalizer

_u = UnitNormalizer()


class RegexExtractor:
    """
    Tier 1: FlashText + Regex.

    Атрибуты:
      • brand             — FlashText (словарь брендов)
      • color             — FlashText (словарь цветов с приоритетами)
      • memory_rom        — Regex + UnitNormalizer
      • memory_ram        — Regex + UnitNormalizer
      • screen_diagonal   — Regex + UnitNormalizer
      • battery           — Regex + UnitNormalizer
      • refresh_rate      — Regex + UnitNormalizer
      • resolution        — Regex
      • cpu               — Regex (паттерны) + канонизация
      • os                — Regex (словарь)
      • weight            — Regex + UnitNormalizer
      • power             — Regex + UnitNormalizer
      • volume            — Regex + UnitNormalizer
      • warranty          — Regex + UnitNormalizer
    """

    name = "regex"
    version = "1.2.0"

    # ---------- Regex-паттерны ----------
    # Весь вход уже приведён к lower-case, re.IGNORECASE не нужен.

    _ROM_RE = re.compile(
        r"(?:rom|встроенн\w*\s+памят\w*|накопит\w*|storage|память\s+пользователя)?"
        r"\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(тб|tb|гб|gb)\b"
    )
    _RAM_RE = re.compile(
        r"(?:ram|озу|оперативн\w*\s+памят\w*)\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(гб|gb)\b"
    )
    _RAM_RE2 = re.compile(
        r"(\d+(?:[.,]\d+)?)\s*(гб|gb)\s*(?:ram|озу|оперативной)\b"
    )
    # Экран: 6.7", 6.7 дюйма, 6,7 ″, диагональ — 50 дюймов
    _SCREEN_RE = re.compile(
        r"(?:диагонал\w*|экран\w*)?\s*[:=\-—–]?\s*"
        r"(\d+(?:[.,]\d+)?)\s*(?:\"|″|”|дюйм\w*|inch(?:es)?\b)",
        re.IGNORECASE,
    )
    # Батарея: 4422 мАч, 5000 мА*ч, 5000mAh, батарея — 4422 мач
    _BATTERY_RE = re.compile(
        r"(?:батаре\w*|аккумулятор\w*|ёмкост\w*\s+батаре\w*)?\s*[:=\-—–]?\s*"
        r"(\d{3,6}(?:[.,]\d+)?)\s*(?:мА[·*.\-\s]?ч|mAh|mah)\b",
        re.IGNORECASE,
    )
    _REFRESH_RE = re.compile(r"(\d{2,4})\s*(?:гц|hz)\b")
    _RES_RE = re.compile(r"\b(\d{3,4})\s*[x×]\s*(\d{3,4})\b")

    # --- новые ---

    # Вес с контекстом (вес/масса/weight)
    _WEIGHT_CTX_RE = re.compile(
        r"(?:вес\w*|масс\w*|weight)\s*[:=]?\s*"
        r"(\d+(?:[.,]\d+)?)\s*"
        r"(кг|kg|килограмм\w*|гр|грамм\w*|gr|г|g)\b"
    )
    # Вес без контекста — только килограммы (явный маркер массы)
    _WEIGHT_KG_RE = re.compile(
        r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(?:кг|kg|килограмм\w*)\b"
    )
    # Вес без контекста — граммы (для наушников, мышей, мелких устройств)
    _WEIGHT_G_RE = re.compile(
        r"(?<!\d)(\d{1,4}(?:[.,]\d+)?)\s*(?:гр|грамм\w*|gr|г|g)\b"
    )

    # Мощность: 1500 Вт, 1.5 кВт, 500w
    _POWER_RE = re.compile(
        r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(квт|kw|вт|w|ватт\w*)\b"
    )

    # Объём: 1.7 л, 500 мл, 2l
    _VOLUME_RE = re.compile(
        r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(мл|ml|л|l|литр\w*)\b"
    )

    # Гарантия: только с ключевым словом, иначе "12 месяцев" — что угодно
    _WARRANTY_RE = re.compile(
        r"(?:гаранти\w*|warranty)\s*[:=]?\s*"
        r"(\d+)\s*(мес\w*|month\w*|год\w*|лет|года|year\w*)"
    )

    # CPU-паттерны: (regex, base_confidence). Идём по порядку,
    # берём первое совпадение. Специфичные — выше.
    _CPU_PATTERNS: list[tuple[re.Pattern[str], float]] = [
        (re.compile(r"\bsnapdragon\s+\d+(?:\s+gen\s+\d+)?\b"), 0.94),
        (re.compile(r"\bmediatek\s+dimensity\s+\d+\b"), 0.94),
        (re.compile(r"\bdimensity\s+\d+\b"), 0.85),
        (re.compile(r"\bexynos\s+\d+\b"), 0.93),
        (re.compile(r"\bkirin\s+\d+\b"), 0.93),
        (re.compile(r"\bapple\s+m\d+(?:\s+(?:pro|max|ultra))?\b"), 0.95),
        (re.compile(r"\bm\d+\s+(?:pro|max|ultra)\b"), 0.88),
        (re.compile(r"\bintel\s+core\s+i[3579](?:-\d+\w*)?\b"), 0.95),
        (re.compile(r"\bcore\s+i[3579](?:-\d+\w*)?\b"), 0.90),
        (re.compile(r"\bryzen\s+\d+(?:\s+\w+)?\b"), 0.92),
        (re.compile(r"\bceleron\s+\w+\b"), 0.85),
        (re.compile(r"\bpentium\s+\w+\b"), 0.85),
    ]

    # Словарь канонизации токенов CPU
    _CPU_CANON = {
        "snapdragon": "Snapdragon",
        "mediatek": "MediaTek",
        "dimensity": "Dimensity",
        "exynos": "Exynos",
        "kirin": "Kirin",
        "apple": "Apple",
        "intel": "Intel",
        "core": "Core",
        "ryzen": "Ryzen",
        "celeron": "Celeron",
        "pentium": "Pentium",
        "gen": "Gen",
        "pro": "Pro",
        "max": "Max",
        "ultra": "Ultra",
    }

    # Операционные системы. Ключи — lower.
    _OS_MAP: dict[str, str] = {
        "android": "Android",
        "андроид": "Android",
        "ios": "iOS",
        "иос": "iOS",
        "ipados": "iPadOS",
        "windows": "Windows",
        "виндовс": "Windows",
        "macos": "macOS",
        "макос": "macOS",
        "linux": "Linux",
        "линукс": "Linux",
        "harmonyos": "HarmonyOS",
        "harmony os": "HarmonyOS",
        "tizen": "Tizen",
        "webos": "webOS",
        "chromeos": "ChromeOS",
        "chrome os": "ChromeOS",
        "ubuntu": "Ubuntu",
        "redos": "RedOS",
        "astra linux": "Astra Linux",
    }

    # ---------- Конструктор ----------

    def __init__(
        self,
        brands: dict[str, str] | None = None,
        colors: dict[str, tuple[str, int]] | None = None,
    ):
        self._brands: dict[str, str] = brands or BRANDS
        self._colors: dict[str, tuple[str, int]] = colors or COLORS

        self._brand_kp = KeywordProcessor(case_sensitive=False)
        for alias, canon in self._brands.items():
            self._brand_kp.add_keyword(alias, canon)

        # Предкомпилированные паттерны для цветов (границы без \b,
        # чтобы работало с кириллицей)
        self._color_patterns: list[tuple[re.Pattern[str], str, int, str]] = []
        for alias, (canon, prio) in self._colors.items():
            pat = re.compile(r"(?<!\w)" + re.escape(alias) + r"(?!\w)")
            self._color_patterns.append((pat, canon, prio, alias))

        # Предкомпилированные паттерны для ОС
        self._os_patterns: list[tuple[re.Pattern[str], str]] = [
            (re.compile(r"(?<!\w)" + re.escape(alias) + r"(?!\w)"), canon)
            for alias, canon in self._OS_MAP.items()
        ]

    # ================== публичный API ==================

    def health(self) -> bool:
        return True

    def extract(self, card: dict) -> list[Prediction]:
        title = (card.get("title") or "").lower()
        description = (card.get("description") or "").lower()
        seller = card.get("seller_attributes") or {}
        seller_text = " ".join(f"{k} {v}".lower() for k, v in seller.items())
        full_text = f"{title}\n{description}\n{seller_text}"

        out: list[Prediction] = []
        seen_attrs: set[str] = set()

        if (brand := self._find_brand(title, description, seller)):
            out.append(brand)
            seen_attrs.add("brand")

        if (color := self._find_color(full_text, seller)):
            out.append(color)
            seen_attrs.add("color")

        for pred in self._find_numeric(full_text, title):
            if pred["attribute"] not in seen_attrs:
                out.append(pred)
                seen_attrs.add(pred["attribute"])

        return out

    # ================== FlashText-хелперы ==================

    def _find_brand(self, title, description, seller):
        for k in ("brand", "бренд", "производитель", "vendor"):
            v = seller.get(k)
            if not v:
                continue
            key = str(v).lower().strip()
            canon = self._brands.get(key, str(v))
            return Prediction(attribute="brand", value=canon,
                              confidence=0.98, source="flashtext", raw=str(v))

        hits_title = self._brand_kp.extract_keywords(title)
        hits_desc = self._brand_kp.extract_keywords(description)
        hits = hits_title or hits_desc
        if hits:
            canon = hits[0]
            conf = 0.95 if hits_title else 0.88
            return Prediction(attribute="brand", value=canon,
                              confidence=conf, source="flashtext", raw=canon)
        return None

    def _find_color(self, full_text, seller):
        for k in ("color", "цвет"):
            v = seller.get(k)
            if v:
                key = str(v).lower().strip()
                canon, _prio = self._colors.get(key, (key, 0))
                return Prediction(attribute="color", value=canon,
                                  confidence=0.95, source="flashtext", raw=str(v))

        best: tuple[int, str, str] | None = None
        for pat, canon, prio, alias in self._color_patterns:
            if pat.search(full_text):
                if best is None or prio > best[0]:
                    best = (prio, canon, alias)

        if best:
            _prio, canon, alias = best
            return Prediction(attribute="color", value=canon,
                              confidence=0.85, source="flashtext", raw=alias)
        return None

    # ================== Regex-хелперы ==================

    def _find_numeric(self, text: str, title: str) -> Iterable[Prediction]:
        # --- RAM (перед ROM, чтобы «8 гб озу» не ушло в rom) ---
        ram_match = self._RAM_RE2.search(text) or self._RAM_RE.search(text)
        ram_span: tuple[int, int] | None = None
        if ram_match:
            ram_span = ram_match.span()
            yield Prediction(
                attribute="memory_ram",
                value=_u.memory(ram_match.group(1), ram_match.group(2)),
                confidence=self._conf(0.90, ram_match.group(0), title),
                source="regex", raw=ram_match.group(0).strip(),
            )

        # --- ROM ---
        for m in self._ROM_RE.finditer(text):
            if ram_span and self._overlaps(m.span(), ram_span):
                continue
            # отсеиваем мусор: если непосредственно перед числом идёт "озу"/"ram"
            prefix_start = max(ram_span[1] if ram_span and m.start() >= ram_span[1] else 0, m.start() - 10)
            prefix = text[prefix_start:m.start()].lower()
            if re.search(r"\b(?:озу|ram|оперативн\w*)\s*[:=]?\s*$", prefix):
                continue
            yield Prediction(
                attribute="memory_rom",
                value=_u.memory(m.group(1), m.group(2)),
                confidence=self._conf(0.92, m.group(0), title),
                source="regex", raw=m.group(0).strip(),
            )
            break

        # --- Экран ---
        if (m := self._SCREEN_RE.search(text)):
            try:
                num = float(m.group(1).replace(",", "."))
                if 3 <= num <= 25:
                    yield Prediction(
                        attribute="screen_diagonal",
                        value=_u.screen_diagonal(m.group(1)),
                        confidence=self._conf(0.92, m.group(0), title),
                        source="regex", raw=m.group(0).strip(),
                    )
            except ValueError:
                pass

        # --- Батарея ---
        if (m := self._BATTERY_RE.search(text)):
            yield Prediction(
                attribute="battery", value=_u.battery(m.group(1)),
                confidence=self._conf(0.90, m.group(0), title),
                source="regex", raw=m.group(0).strip(),
            )

        # --- Частота ---
        if (m := self._REFRESH_RE.search(text)):
            hz = int(m.group(1))
            if 30 <= hz <= 240:
                yield Prediction(
                    attribute="refresh_rate", value=_u.refresh_rate(m.group(1)),
                    confidence=self._conf(0.85, m.group(0), title),
                    source="regex", raw=m.group(0).strip(),
                )

        # --- Разрешение ---
        if (m := self._RES_RE.search(text)):
            yield Prediction(
                attribute="resolution",
                value=_u.resolution(m.group(1), m.group(2)),
                confidence=0.88, source="regex", raw=m.group(0).strip(),
            )

        # --- Вес ---
        if (m := self._WEIGHT_CTX_RE.search(text)):
            yield Prediction(
                attribute="weight",
                value=_u.weight(m.group(1), m.group(2)),
                confidence=self._conf(0.92, m.group(0), title),
                source="regex", raw=m.group(0).strip(),
            )
        elif (m := self._WEIGHT_KG_RE.search(text)):
            # только "кг" — явный маркер веса
            yield Prediction(
                attribute="weight",
                value=_u.weight(m.group(1), "кг"),
                confidence=self._conf(0.80, m.group(0), title),
                source="regex", raw=m.group(0).strip(),
            )
        elif (m := self._WEIGHT_G_RE.search(text)):
            grams = float(m.group(1).replace(",", "."))
            if grams <= 2000:  # защита от мусора
                yield Prediction(
                    attribute="weight",
                    value=_u.weight(m.group(1), "г"),
                    confidence=self._conf(0.72, m.group(0), title),
                    source="regex", raw=m.group(0).strip(),
                )

        # --- Мощность ---
        if (m := self._POWER_RE.search(text)):
            yield Prediction(
                attribute="power", value=_u.power(m.group(1), m.group(2)),
                confidence=self._conf(0.88, m.group(0), title),
                source="regex", raw=m.group(0).strip(),
            )

        # --- Объём ---
        if (m := self._VOLUME_RE.search(text)):
            yield Prediction(
                attribute="volume", value=_u.volume(m.group(1), m.group(2)),
                confidence=self._conf(0.85, m.group(0), title),
                source="regex", raw=m.group(0).strip(),
            )

        # --- Гарантия ---
        if (m := self._WARRANTY_RE.search(text)):
            yield Prediction(
                attribute="warranty",
                value=_u.warranty(m.group(1), m.group(2)),
                confidence=0.90, source="regex", raw=m.group(0).strip(),
            )

        # --- CPU ---
        if (m := self._find_cpu(text)):
            raw_match, base_conf = m
            yield Prediction(
                attribute="cpu",
                value=self._canon_cpu(raw_match.group(0)),
                confidence=self._conf(base_conf, raw_match.group(0), title),
                source="regex", raw=raw_match.group(0).strip(),
            )

        # --- OS ---
        if (m := self._find_os(text)):
            raw_text, canon = m
            yield Prediction(
                attribute="os", value=canon,
                confidence=0.90, source="regex", raw=raw_text,
            )

    # ================== CPU / OS ==================

    def _find_cpu(self, text: str):
        for pat, conf in self._CPU_PATTERNS:
            if (m := pat.search(text)):
                return m, conf
        return None

    def _canon_cpu(self, raw: str) -> str:
        """'snapdragon 8 gen 3' → 'Snapdragon 8 Gen 3'."""
        out: list[str] = []
        for tok in raw.split():
            low = tok.lower()
            if low in self._CPU_CANON:
                out.append(self._CPU_CANON[low])
            elif re.fullmatch(r"m\d+", low):
                out.append("M" + low[1:])
            else:
                out.append(tok)
        return " ".join(out)

    def _find_os(self, text: str):
        """Возвращает (raw_match, canonical) или None. Приоритет — самому
        длинному совпадению (chrome os раньше chrome, harmony os раньше harmony)."""
        best: tuple[int, str, str] | None = None
        for pat, canon in self._os_patterns:
            if (m := pat.search(text)):
                length = m.end() - m.start()
                if best is None or length > best[0]:
                    best = (length, m.group(0), canon)
        if best:
            return best[1], best[2]
        return None

    # ================== утилиты ==================

    @staticmethod
    def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
        return not (a[1] <= b[0] or b[1] <= a[0])

    @staticmethod
    def _conf(base: float, raw: str, title: str) -> float:
        return min(0.99, base + (0.03 if raw and raw in title else 0.0))