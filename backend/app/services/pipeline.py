from __future__ import annotations

import logging
from typing import Any

from app.extractors.base import Prediction
from app.extractors.gliner_extractor import GlinerExtractor
from app.extractors.regex_extractor import RegexExtractor

logger = logging.getLogger(__name__)

# Обязательные характеристики каталога М.Видео для фильтров поиска
REQUIRED_ATTRS: set[str] = {
    "brand",
    "model",
    "memory_rom",
    "screen_diagonal",
    "battery",
    "color",
}


class CascadedExtractionPipeline:
    """
    Каскадный оркестратор извлечения характеристик (Tier 1 + Tier 2 + Tier 3).

    1. Tier 1 (FastRules: Regex + FlashText):
       Сверхбыстро (< 1 мс) и с высокой точностью (0.90+) снимает бренды из справочника,
       цвета, и числовые параметры (RAM, ROM, диагональ, батарея, частота, разрешение).
    2. Tier 2 (GLiNER Zero-Shot NER):
       Запускается ТОЛЬКО для тех обязательных атрибутов, которые не закрыл Tier 1
       (в первую очередь: модель/серия, процессор/чипсет, редкие бренды).
    3. Валидация и калибровка:
       Проверяет типы, рассчитывает интегральный Confidence Score и выставляет флаг
       needs_review для модерации человеком (Human-in-the-Loop).
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

    def process_card(self, card: dict[str, Any]) -> dict[str, Any]:
        """
        Прогоняет карточку через каскад экстракторов.

        Возвращает:
        - predictions: список извлеченных атрибутов
        - missing: список оставшихся незаполненными обязательных полей
        - overall_confidence: средневзвешенная уверенность
        - needs_review: флаг необходимости ручной проверки
        """
        predictions_map: dict[str, Prediction] = {}

        # ------------------------------------------------------------------
        # ЭТАП 1: Tier 1 (Regex + FlashText)
        # ------------------------------------------------------------------
        t1_preds = self.regex_extractor.extract(card)
        for p in t1_preds:
            predictions_map[p["attribute"]] = p

        found_attrs = set(predictions_map.keys())
        missing_attrs = REQUIRED_ATTRS - found_attrs

        # ------------------------------------------------------------------
        # ЭТАП 2: Tier 2 (GLiNER Zero-Shot NER) — если остались пропуски
        # ------------------------------------------------------------------
        # Если не хватает модели, процессора или бренда/цвета — зовем GLiNER
        if self.use_gliner and self.gliner_extractor and missing_attrs:
            t2_preds = self.gliner_extractor.extract(card)
            for p in t2_preds:
                attr = p["attribute"]
                # Заполняем пропущенные или заменяем менее уверенные
                if attr not in predictions_map or predictions_map[attr]["confidence"] < p["confidence"]:
                    predictions_map[attr] = p

        # ------------------------------------------------------------------
        # ЭТАП 3: Оценка уверенности и статуса (HITL)
        # ------------------------------------------------------------------
        all_preds = list(predictions_map.values())
        final_found = set(predictions_map.keys())
        final_missing = sorted(list(REQUIRED_ATTRS - final_found))

        if all_preds:
            avg_conf = sum(p["confidence"] for p in all_preds) / len(all_preds)
        else:
            avg_conf = 0.0

        # Карточка требует проверки человеком (Human-in-the-Loop), если:
        # 1. Средняя уверенность ниже порога (0.75)
        # 2. Не удалось извлечь критически важные поля (модель или бренд)
        critical_missing = bool({"brand", "model"} & set(final_missing))
        needs_review = (avg_conf < self.confidence_threshold) or critical_missing or (len(all_preds) == 0)

        return {
            "external_id": card.get("external_id") or card.get("id"),
            "category": card.get("category"),
            "predictions": all_preds,
            "missing": final_missing,
            "overall_confidence": round(avg_conf, 4),
            "needs_review": needs_review,
        }
