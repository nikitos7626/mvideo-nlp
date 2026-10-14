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

    Что закрывает:
      • бренд          (FlashText, словарь брендов)
      • цвет           (FlashText, словарь цветов)
      • memory_rom     (Regex + UnitNormalizer)
      • memory_ram     (Regex + UnitNormalizer)
      • screen_diagonal(Regex + UnitNormalizer)
      • battery        (Regex + UnitNormalizer)
      • resolution     (Regex)
      • refresh_rate   (Regex + UnitNormalizer)
    """

    name = "regex"
    version = "1.0.0"

    # ---------- Regex-паттерны ----------
    # ROM: "256 ГБ", "256GB", "1 ТБ", "1024 Гб", с опциональным "ROM"/"память"
    _ROM_RE = re.compile(
        r"(?:rom|встроенн\w*\s+памят\w*|накопит\w*|storage|память\s+пользователя)?"
        r"\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(ТБ|TB|ГБ|GB)\b",
        re.IGNORECASE,
    )
    # RAM: "8 ГБ ОЗУ", "8GB RAM", "ОЗУ 8 ГБ"
    _RAM_RE = re.compile(
        r"(?:ram|озу|оперативн\w*\s+памят\w*)\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(ГБ|GB)",
        re.IGNORECASE,
    )
    _RAM_RE2 = re.compile(
        r"(\d+(?:[.,]\d+)?)\s*(ГБ|GB)\s*(?:ram|озу|оперативной)",
        re.IGNORECASE,
    )
    # Экран: 6.7", 6.7 дюйма, 6,7 ″, диагональ 6.7
    _SCREEN_RE = re.compile(
        r"(?:диагонал\w*|экран\w*)?\s*[:=]?\s*"
        r"(\d+(?:[.,]\d+)?)\s*(?:\"|″|”|дюйм\w*|inch(?:es)?\b)",
        re.IGNORECASE,
    )
    # Батарея: 4422 мАч, 5000mAh, батарея 4422 мач
    _BATTERY_RE = re.compile(
        r"(?:батаре\w*|аккумулятор\w*|ёмкост\w*\s+батаре\w*)?\s*[:=]?\s*"
        r"(\d{3,6}(?:[.,]\d+)?)\s*(?:мАч|мА·ч|mAh|mah)\b",
        re.IGNORECASE,
    )
    # Частота обновления: 120 Гц, 120Hz, 120 Hz
    _REFRESH_RE = re.compile(
        r"(\d{2,4})\s*(?:Гц|Hz)\b",
        re.IGNORECASE,
    )
    # Разрешение: 1920x1080, 1920 × 1080
    _RES_RE = re.compile(r"\b(\d{3,4})\s*[x×]\s*(\d{3,4})\b")

    def __init__(self, brands: dict[str, str] | None = None,
                 colors: dict[str, str] | None = None):
        self._brands = brands or BRANDS
        self._colors = colors or COLORS

        # FlashText-процессоры. case_sensitive=False — важно: в карточках
        # кто-то пишет Apple, кто-то apple.
        self._brand_kp = KeywordProcessor(case_sensitive=False)
        for alias, canon in self._brands.items():
            # FlashText вернёт canon как "ключ". Используем чистый API.
            self._brand_kp.add_keyword(alias, canon)

        self._color_kp = KeywordProcessor(case_sensitive=False)
        for alias, canon in self._colors.items():
            self._color_kp.add_keyword(alias, canon)

    # ================== публичный API ==================

    def health(self) -> bool:
        return True

    def extract(self, card: dict) -> list[Prediction]:
        # 1. Собираем весь текст карточки в один корпус.
        #    Порядок важен: title весит больше, чем description.
        title = card.get("title") or ""
        description = card.get("description") or ""
        seller = card.get("seller_attributes") or {}

        seller_text = " ".join(f"{k} {v}" for k, v in seller.items())
        full_text = f"{title}\n{description}\n{seller_text}"

        out: list[Prediction] = []
        seen_attrs: set[str] = set()

        # ---- FlashText: бренд и цвет ----
        brand = self._find_brand(title, description, seller, seller_text)
        if brand:
            out.append(brand); seen_attrs.add("brand")

        color = self._find_color(full_text, seller)
        if color:
            out.append(color); seen_attrs.add("color")

        # ---- Regex: числовые атрибуты ----
        for pred in self._find_numeric(full_text, title):
            if pred["attribute"] not in seen_attrs:
                out.append(pred)
                seen_attrs.add(pred["attribute"])

        return out

    # ================== FlashText-хелперы ==================

    def _find_brand(self, title: str, description: str,
                    seller: dict, seller_text: str) -> Prediction | None:
        # 1) явное поле продавца — максимальная уверенность
        for k in ("brand", "бренд", "производитель", "vendor"):
            v = seller.get(k)
            if not v:
                continue
            canon = self._brands.get(str(v).lower().strip(), str(v))
            return Prediction(
                attribute="brand", value=canon,
                confidence=0.98, source="flashtext",
                raw=str(v),
            )

        # 2) FlashText по тексту
        hits_title = self._brand_kp.extract_keywords(title)
        hits_desc = self._brand_kp.extract_keywords(description)
        hits = hits_title or hits_desc
        if hits:
            canon = hits[0]
            # в title — увереннее
            conf = 0.95 if hits_title else 0.88
            return Prediction(attribute="brand", value=canon,
                              confidence=conf, source="flashtext",
                              raw=canon)
        return None

    def _find_color(self, full_text: str, seller: dict) -> Prediction | None:
        for k in ("color", "цвет"):
            v = seller.get(k)
            if v:
                canon = self._colors.get(str(v).lower().strip(), str(v))
                return Prediction(attribute="color", value=canon,
                                  confidence=0.95, source="flashtext",
                                  raw=str(v))

        hits = self._color_kp.extract_keywords(full_text)
        if hits:
            # FlashText вернёт с каноном. Берём первое попадание.
            return Prediction(attribute="color", value=hits[0],
                              confidence=0.85, source="flashtext",
                              raw=hits[0])
        return None

    # ================== Regex-хелперы ==================

    def _find_numeric(self, text: str, title: str) -> Iterable[Prediction]:
        # --- RAM (важно искать РАНЬШЕ ROM, иначе «8 ГБ ОЗУ» съест ROM-паттерн) ---
        ram_match = self._RAM_RE2.search(text) or self._RAM_RE.search(text)
        ram_span = None
        if ram_match:
            ram_span = ram_match.span()
            yield Prediction(
                attribute="memory_ram",
                value=_u.memory(ram_match.group(1), ram_match.group(2)),
                confidence=self._conf(0.90, ram_match.group(0), title),
                source="regex",
                raw=ram_match.group(0).strip(),
            )

        # --- ROM ---
        # Проходим ВСЕ совпадения ROM-паттерна, но пропускаем то,
        # что пересекается с уже найденным RAM.
        for m in self._ROM_RE.finditer(text):
            if ram_span and self._overlaps(m.span(), ram_span):
                continue
            # отсеиваем мусор: если слева от числа идёт "озу"/"ram" — это не ROM
            prefix = text[max(0, m.start() - 20):m.start()].lower()
            if "озу" in prefix or "ram" in prefix or "оператив" in prefix:
                continue
            yield Prediction(
                attribute="memory_rom",
                value=_u.memory(m.group(1), m.group(2)),
                confidence=self._conf(0.92, m.group(0), title),
                source="regex",
                raw=m.group(0).strip(),
            )
            break  # на карточку обычно один ROM

        # --- Экран ---
        if (m := self._SCREEN_RE.search(text)):
            val = _u.screen_diagonal(m.group(1))
            # sanity check: диагонали смартфонов/ноутов 3–20"
            try:
                num = float(m.group(1).replace(",", "."))
                if 3 <= num <= 25:
                    yield Prediction(
                        attribute="screen_diagonal", value=val,
                        confidence=self._conf(0.92, m.group(0), title),
                        source="regex", raw=m.group(0).strip(),
                    )
            except ValueError:
                pass

        # --- Батарея ---
        if (m := self._BATTERY_RE.search(text)):
            yield Prediction(
                attribute="battery",
                value=_u.battery(m.group(1)),
                confidence=self._conf(0.90, m.group(0), title),
                source="regex", raw=m.group(0).strip(),
            )

        # --- Частота обновления ---
        if (m := self._REFRESH_RE.search(text)):
            hz = int(m.group(1))
            if 30 <= hz <= 240:  # разумный диапазон
                yield Prediction(
                    attribute="refresh_rate",
                    value=_u.refresh_rate(m.group(1)),
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

    # ================== утилиты ==================

    @staticmethod
    def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
        return not (a[1] <= b[0] or b[1] <= a[0])

    @staticmethod
    def _conf(base: float, raw: str, title: str) -> float:
        """Если спан найден в title — уверенность выше на 0.03."""
        return min(0.99, base + (0.03 if raw and raw in title else 0.0))