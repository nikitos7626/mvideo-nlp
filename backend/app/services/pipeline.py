from __future__ import annotations

import logging
import re
from typing import Any

from app.extractors.base import Prediction
from app.extractors.gliner_extractor import GlinerExtractor
from app.extractors.regex_extractor import RegexExtractor

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# ТАКСОНОМИЯ И СХЕМЫ АТРИБУТОВ ПО КАТЕГОРИЯМ КАТАЛОГА М.ВИДЕО
# --------------------------------------------------------------------------
CATEGORY_SCHEMAS: dict[str, dict[str, Any]] = {
    "smartphones": {
        "name_ru": "Смартфоны",
        "keywords": ["смартфон", "телефон", "iphone", "айфон", "galaxy", "redmi", "poco", "realme"],
        "required_attrs": {"brand", "model", "memory_rom", "screen_diagonal", "battery", "color"},
        "gliner_labels": ["бренд", "модель", "объём памяти", "оперативная память", "диагональ экрана", "цвет", "процессор", "ёмкость аккумулятора"],
    },
    "laptops": {
        "name_ru": "Ноутбуки",
        "keywords": ["ноутбук", "лэптоп", "ideapad", "thinkpad", "macbook", "ноут", "zenbook", "vivobook", "redmibook"],
        "required_attrs": {"brand", "model", "cpu", "memory_ram", "memory_rom", "screen_diagonal"},
        "gliner_labels": ["бренд", "модель", "процессор", "оперативная память", "объём памяти", "диагональ экрана", "видеокарта", "цвет"],
    },
    "tvs": {
        "name_ru": "Телевизоры",
        "keywords": ["телевизор", "тв", "smart tv", "triluminos", "oled", "qled"],
        "required_attrs": {"brand", "model", "screen_diagonal", "resolution"},
        "gliner_labels": ["бренд", "модель", "диагональ экрана", "разрешение экрана", "технология экрана", "частота обновления экрана"],
    },
    "vacuum_cleaners": {
        "name_ru": "Пылесосы",
        "keywords": ["пылесос", "робот-пылесос", "vacuum", "клининг"],
        "required_attrs": {"brand", "model", "cleaning_type", "color"},
        "gliner_labels": ["бренд", "модель", "тип уборки", "время работы", "цвет", "объем пылесборника"],
    },
    "refrigerators": {
        "name_ru": "Холодильники",
        "keywords": ["холодильник", "морозильник", "морозильная", "no frost"],
        "required_attrs": {"brand", "model", "defrost_system", "color"},
        "gliner_labels": ["бренд", "модель", "система разморозки", "объем", "цвет"],
    },
    "headphones": {
        "name_ru": "Наушники",
        "keywords": ["наушники", "гарнитура", "airpods", "tws", "earbuds"],
        "required_attrs": {"brand", "model", "color"},
        "gliner_labels": ["бренд", "модель", "цвет", "время работы"],
    },
    "default": {
        "name_ru": "Электроника и техника",
        "keywords": [],
        "required_attrs": {"brand", "model", "color"},
        "gliner_labels": ["бренд", "модель", "цвет"],
    },
}


class CascadedExtractionPipeline:
    """
    Каскадный оркестратор извлечения характеристик промышленного уровня:

    ЭТАП 1: Детекция категории товара (Category Classifier)
            Понимает, что перед нами — смартфон, пылесос, ТВ или холодильник,
            и активирует целевую таксономию атрибутов М.Видео.

    ЭТАП 2: Базовые правила и словари (Tier 1 Fast Rules)
            Сверхбыстро (< 1 мс) снимает бренды, цвета и шаблонные числа (RAM, ROM, экран, батарею).

    ЭТАП 3: Таргетированный Zero-Shot NER (Tier 2 GLiNER)
            Дособирает недостающие сущности (модель, процессор, тип уборки),
            фокусируясь строго на атрибутах определенной категории.

    ЭТАП 4: Валидация и калибровка уверенности (HITL)
            Проверяет полноту карточки, рассчитывает средневзвешенную уверенность
            и определяет статус публикации.
    """

    def __init__(
        self,
        use_gliner: bool = True,
        confidence_threshold: float = 0.75,
        gliner_threshold: float = 0.30,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.use_gliner = use_gliner
        self.regex_extractor = RegexExtractor()
        self.gliner_extractor = GlinerExtractor(threshold=gliner_threshold) if use_gliner else None

    def detect_category(self, card: dict[str, Any]) -> tuple[str, str]:
        """
        Определяет категорию товара по метаданным или тексту названия и описания.
        Возвращает (category_key, category_name_ru).
        """
        raw_cat = (card.get("category") or "").lower()
        title = (card.get("title") or "").lower()
        desc = (card.get("description") or "").lower()
        text_corpus = f"{raw_cat} {title} {desc}"

        # 1. Поиск по ключевым словам таксономии
        for cat_key, schema in CATEGORY_SCHEMAS.items():
            if cat_key == "default":
                continue
            for kw in schema["keywords"]:
                # Словарное совпадение с границами слов или морфемой
                if re.search(rf"\b{re.escape(kw)}", text_corpus):
                    return cat_key, schema["name_ru"]

        return "default", CATEGORY_SCHEMAS["default"]["name_ru"]

    def process_card(self, card: dict[str, Any]) -> dict[str, Any]:
        """
        Сквозной прогон карточки через 4-этапную воронку.
        """
        # ------------------------------------------------------------------
        # ЭТАП 1: Определение категории товара
        # ------------------------------------------------------------------
        cat_key, cat_name = self.detect_category(card)
        schema = CATEGORY_SCHEMAS.get(cat_key, CATEGORY_SCHEMAS["default"])
        required_attrs: set[str] = schema["required_attrs"]
        gliner_labels: list[str] = schema["gliner_labels"]

        predictions_map: dict[str, Prediction] = {}

        # ------------------------------------------------------------------
        # ЭТАП 2: Tier 1 (Regex + FlashText)
        # ------------------------------------------------------------------
        t1_preds = self.regex_extractor.extract(card)
        for p in t1_preds:
            # Для не-смартфонов и не-ноутбуков отсекаем ложные числа памяти
            if cat_key in ("vacuum_cleaners", "refrigerators") and p["attribute"] in ("memory_rom", "memory_ram", "screen_diagonal"):
                continue
            predictions_map[p["attribute"]] = p

        found_attrs = set(predictions_map.keys())
        missing_attrs = required_attrs - found_attrs

        # ------------------------------------------------------------------
        # ЭТАП 3: Tier 2 (GLiNER Zero-Shot NER) — таргетированно под категорию
        # ------------------------------------------------------------------
        if self.use_gliner and self.gliner_extractor and missing_attrs:
            t2_preds = self.gliner_extractor.extract(card, target_labels=gliner_labels)
            for p in t2_preds:
                attr = p["attribute"]
                if attr not in predictions_map or predictions_map[attr]["confidence"] < p["confidence"]:
                    predictions_map[attr] = p

        # ------------------------------------------------------------------
        # ЭТАП 4: Валидация полноты и расчет уверенности
        # ------------------------------------------------------------------
        all_preds = list(predictions_map.values())
        final_found = set(predictions_map.keys())
        final_missing = sorted(list(required_attrs - final_found))

        if all_preds:
            avg_conf = sum(p["confidence"] for p in all_preds) / len(all_preds)
        else:
            avg_conf = 0.0

        # Карточка требует проверки человеком (Human-in-the-Loop), если:
        # 1. Средняя уверенность ниже порога (0.75)
        # 2. Не удалось извлечь критически важные поля категории (бренд или модель)
        # 3. Карточка пустая
        critical_missing = bool({"brand", "model"} & set(final_missing))
        needs_review = (avg_conf < self.confidence_threshold) or critical_missing or (len(all_preds) == 0)

        return {
            "external_id": card.get("external_id") or card.get("id"),
            "category": cat_name,
            "category_key": cat_key,
            "predictions": all_preds,
            "missing": final_missing,
            "overall_confidence": round(avg_conf, 4),
            "needs_review": needs_review,
        }
