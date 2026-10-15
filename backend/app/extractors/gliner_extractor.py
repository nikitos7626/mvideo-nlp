from __future__ import annotations

import logging
import re
from typing import Any

import torch
from gliner import GLiNER

from app.extractors.base import Prediction
from app.extractors.normalization.dictionaries import BRANDS, COLORS
from app.extractors.normalization.units import UnitNormalizer

logger = logging.getLogger(__name__)


class AttributeTypeValidator:
    """Защита от контекстных галлюцинаций и путаницы единиц измерения."""

    @staticmethod
    def is_valid(attr_name: str, value: str) -> bool:
        if not value or not value.strip():
            return False

        val_lower = value.lower().strip()

        if attr_name == "refresh_rate":
            # Частота обязана быть в Гц / Hz
            if any(u in val_lower for u in ["мач", "mah", "дюйм", '"', "гб", "gb", "тб"]):
                return False
            return bool(re.search(r"\b\d{2,3}\s*(?:гц|hz)\b", val_lower)) or val_lower.isdigit()

        if attr_name == "battery":
            # Емкость аккумулятора не должна содержать дюймов, герц или памяти
            if any(u in val_lower for u in ["гб", "gb", "тб", "дюйм", '"', "гц", "hz"]):
                return False
            return bool(re.search(r"\d{3,5}", val_lower))

        if attr_name in ("memory_rom", "memory_ram"):
            if any(u in val_lower for u in ['"', "дюйм", "мач", "mah", "гц", "hz"]):
                return False
            return bool(re.search(r"\b\d+\s*(?:гб|gb|тб|tb)\b", val_lower) or val_lower.isdigit())

        if attr_name == "screen_diagonal":
            if any(u in val_lower for u in ["гб", "gb", "тб", "tb", "мач", "mah", "гц", "hz"]):
                return False
            return bool(re.search(r"\d{1,2}(?:[.,]\d{1,2})?", val_lower))

        if attr_name == "color":
            # Цвет не может содержать цифры, технические характеристики или разрешения
            if re.search(r"\d", val_lower):
                return False
            return len(val_lower) >= 3

        if attr_name == "model":
            # Модель не должна быть одиночным общим словом вроде "смартфон" или "телефон"
            if val_lower in {"смартфон", "телефон", "ноутбук", "планшет", "телевизор", "наушники", "беспроводные", "пылесос", "робот-пылесос", "холодильник"}:
                return False
            return len(val_lower) >= 2

        if attr_name == "cleaning_type":
            return any(k in val_lower for k in ["сух", "влажн", "комбинир"])

        if attr_name == "defrost_system":
            return any(k in val_lower for k in ["no frost", "ноу фрост", "капельн", "ручн", "автомат"])

        if attr_name == "display_tech":
            # Белый список матриц дисплея (HLG, HDR10 и звук строго отсекаются)
            return any(k in val_lower for k in AttributeTypeValidator.ALLOWED_DISPLAY_TECHS)

        return True

    ALLOWED_DISPLAY_TECHS: dict[str, str] = {
        "triluminos": "Triluminos",
        "oled": "OLED",
        "олед": "OLED",
        "amoled": "AMOLED",
        "super amoled": "Super AMOLED",
        "superamoled": "Super AMOLED",
        "qled": "QLED",
        "клед": "QLED",
        "neo qled": "Neo QLED",
        "ips": "IPS",
        "ипс": "IPS",
        "va": "VA",
        "tn": "TN",
        "nanocell": "NanoCell",
        "mini led": "Mini-LED",
        "mini-led": "Mini-LED",
        "retina": "Retina",
    }


class GlinerExtractor:
    """
    Tier 2: Zero-shot NER экстрактор на базе GLiNER (urchade/gliner_multi-v2.1).

    Специализируется на извлечении сложных сущностей, плохо покрываемых регулярками:
    - Модель / Серия (iPhone 15 Pro Max, RedmiBook 16, WH-1000XM5)
    - Процессор / Чипсет (Apple A17 Pro, Snapdragon 8 Gen 2, Intel Core i5)
    - Редкие бренды и составные цвета.
    """

    name: str = "gliner"
    version: str = "0.2.1"

    # Приоритетные метки для названия (максимальная плотность сущностей модели и бренда)
    TITLE_LABELS: list[str] = ["модель", "бренд", "цвет"]

    # Приоритетные метки для описания (процессор, доп. характеристики)
    DESC_LABELS: list[str] = ["процессор", "чипсет", "модель", "бренд", "цвет"]

    LABEL_TO_ATTR: dict[str, str] = {
        "бренд": "brand",
        "модель": "model",
        "цвет": "color",
        "процессор": "cpu",
        "чипсет": "cpu",
        "объём памяти": "memory_rom",
        "оперативная память": "memory_ram",
        "диагональ экрана": "screen_diagonal",
        "ёмкость аккумулятора": "battery",
        "частота обновления экрана": "refresh_rate",
        "разрешение экрана": "resolution",
        "тип уборки": "cleaning_type",
        "время работы": "working_time",
        "система разморозки": "defrost_system",
        "технология экрана": "display_tech",
        "объем": "volume",
    }

    _NUM_UNIT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*([a-zA-Zа-яА-ЯёЁ\"']*)")

    def __init__(
        self,
        model_name: str = "urchade/gliner_multi-v2.1",
        threshold: float = 0.30,
        device: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.threshold = threshold
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._model: GLiNER | None = None
        self._units = UnitNormalizer()
        self._validator = AttributeTypeValidator()

    def _ensure_model(self) -> GLiNER:
        if self._model is None:
            logger.info("Загрузка модели GLiNER (%s) на устройство %s...", self.model_name, self.device)
            self._model = GLiNER.from_pretrained(self.model_name)
            self._model.to(self.device)
            self._model.eval()
        return self._model

    def health(self) -> bool:
        try:
            self._ensure_model()
            return True
        except Exception as e:
            logger.error("Health check failed for GLiNER: %s", e)
            return False

    def extract(self, card: dict[str, Any], target_labels: list[str] | None = None) -> list[Prediction]:
        title = (card.get("title") or "").strip()
        description = (card.get("description") or "").strip()
        model = self._ensure_model()

        predictions: list[Prediction] = []
        seen_attrs: set[str] = set()

        # Пасс 1: Заголовок (Title) — здесь самая чистая модель и бренд
        if title:
            t_labels = target_labels or self.TITLE_LABELS
            title_entities = model.predict_entities(title, t_labels, threshold=self.threshold)
            for ent in sorted(title_entities, key=lambda x: float(x.get("score", 0.0)), reverse=True):
                pred = self._entity_to_prediction(ent, is_title=True)
                if pred and pred["attribute"] not in seen_attrs:
                    predictions.append(pred)
                    seen_attrs.add(pred["attribute"])

        # Пасс 2: Описание (Description) — процессор, чипсет, отсутствующие поля
        if description:
            d_labels = target_labels or self.DESC_LABELS
            desc_entities = model.predict_entities(description, d_labels, threshold=self.threshold)
            for ent in sorted(desc_entities, key=lambda x: float(x.get("score", 0.0)), reverse=True):
                pred = self._entity_to_prediction(ent, is_title=False)
                if pred and pred["attribute"] not in seen_attrs:
                    predictions.append(pred)
                    seen_attrs.add(pred["attribute"])

        return predictions

    def _entity_to_prediction(self, ent: dict, is_title: bool) -> Prediction | None:
        label = ent["label"]
        attr_key = self.LABEL_TO_ATTR.get(label)
        if not attr_key:
            return None

        raw_text = ent["text"].strip()
        score = float(ent["score"])

        # Валидация правдоподобности спана
        if not self._validator.is_valid(attr_key, raw_text):
            return None

        # Нормализация
        canon_val = self._normalize(attr_key, raw_text)
        if not canon_val:
            return None

        # Буст уверенности для сущностей из заголовка
        conf = min(0.99, score + (0.05 if is_title else 0.0))

        return Prediction(
            attribute=attr_key,
            value=canon_val,
            confidence=round(conf, 4),
            source="gliner",
            raw=raw_text,
        )

    def _normalize(self, attr_key: str, raw: str) -> str:
        raw_clean = raw.strip().rstrip(".,;:")
        low = raw_clean.lower()

        if attr_key == "brand":
            return BRANDS.get(low, raw_clean)

        if attr_key == "color":
            return COLORS.get(low, raw_clean)

        if attr_key in ("memory_rom", "memory_ram"):
            m = self._NUM_UNIT_RE.search(raw_clean)
            if m:
                val, unit = m.group(1), m.group(2) or "ГБ"
                try:
                    return self._units.memory(val, unit)
                except Exception:
                    pass
            return raw_clean

        if attr_key == "screen_diagonal":
            m = re.search(r"(\d+(?:[.,]\d+)?)", raw_clean)
            if m:
                try:
                    return self._units.screen_diagonal(m.group(1))
                except Exception:
                    pass
            return raw_clean

        if attr_key == "battery":
            m = re.search(r"(\d+)", raw_clean.replace(" ", ""))
            if m:
                try:
                    return self._units.battery(m.group(1))
                except Exception:
                    pass
            return raw_clean

        if attr_key == "refresh_rate":
            m = re.search(r"(\d+)", raw_clean)
            if m:
                try:
                    return self._units.refresh_rate(m.group(1))
                except Exception:
                    pass
            return raw_clean

        if attr_key == "resolution":
            m = re.search(r"(\d{3,4})\s*[*xXхХ×]\s*(\d{3,4})", raw_clean)
            if m:
                try:
                    return self._units.resolution(m.group(1), m.group(2))
                except Exception:
                    pass
            return raw_clean

        if attr_key == "cleaning_type":
            if "сух" in low and "влажн" in low:
                return "сухая и влажная"
            if "влажн" in low:
                return "влажная"
            if "сух" in low:
                return "сухая"
            return raw_clean

        if attr_key == "defrost_system":
            if "no frost" in low or "ноу фрост" in low:
                return "No Frost"
            return raw_clean

        if attr_key == "display_tech":
            for k, canon in AttributeTypeValidator.ALLOWED_DISPLAY_TECHS.items():
                if k in low:
                    return canon
            return raw_clean

        return raw_clean
