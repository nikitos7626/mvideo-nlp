"""
Сервис каталожного обогащения характеристик (Catalog Model Specs Enricher).
Использует эталонную базу знаний характеристик моделей М.Видео (catalog_models_kb.json)
для автоматического дозаполнения недостающих параметров, если продавец не указал их в тексте.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from app.extractors.base import Prediction
from app.extractors.sanity import AttributeSanityValidator

logger = logging.getLogger(__name__)

DEFAULT_KB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "dictionaries",
    "catalog_models_kb.json",
)


class CatalogEnricher:
    """Обогащает карточку эталонными характеристиками из базы моделей М.Видео."""

    def __init__(self, kb_path: str | None = None) -> None:
        self.kb_path = kb_path or DEFAULT_KB_PATH
        self.kb: dict[str, dict[str, dict[str, str]]] = {}
        self._load_kb()

    def _load_kb(self) -> None:
        if not os.path.exists(self.kb_path):
            logger.warning("Catalog KB file not found at %s", self.kb_path)
            return

        try:
            with open(self.kb_path, "r", encoding="utf-8") as f:
                self.kb = json.load(f)
            logger.info("Loaded Catalog KB with %d vendors", len(self.kb))
        except Exception as e:
            logger.error("Failed to load Catalog KB from %s: %s", self.kb_path, e)

    def find_model_specs(self, brand: str, model: str) -> dict[str, str] | None:
        """Ищет спецификации модели по бренду и названию модели."""
        if not brand or not model or not self.kb:
            return None

        b_key = brand.strip().lower()
        vendor_models = self.kb.get(b_key)
        if not vendor_models:
            # Попробуем найти среди всех вендоров частичное совпадение
            for v, v_mods in self.kb.items():
                if v in b_key or b_key in v:
                    vendor_models = v_mods
                    break

        if not vendor_models:
            return None

        m_clean = model.strip().lower()
        # 1. Прямое совпадение
        if m_clean in vendor_models:
            return vendor_models[m_clean]

        # 2. Поиск по подстроке (например "galaxy s22+ 8/128gb" содержит "galaxy s22+")
        best_match = None
        longest_key_len = 0
        for k, specs in vendor_models.items():
            if (k in m_clean or m_clean in k) and len(k) > longest_key_len:
                best_match = specs
                longest_key_len = len(k)

        if best_match and longest_key_len >= 3:
            return best_match

        # 3. Fuzzy search через rapidfuzz если доступен
        try:
            from rapidfuzz import process, fuzz
            choices = list(vendor_models.keys())
            match = process.extractOne(m_clean, choices, scorer=fuzz.token_set_ratio)
            if match and match[1] >= 85:
                return vendor_models[match[0]]
        except ImportError:
            pass

        return None

    def enrich(
        self,
        brand: str,
        model: str,
        missing_attrs: set[str],
        category_key: str,
    ) -> list[Prediction]:
        """
        Возвращает список предсказаний для недостающих атрибутов, найденных в каталоге.
        """
        if not missing_attrs:
            return []

        specs = self.find_model_specs(brand, model)
        if not specs:
            return []

        enriched: list[Prediction] = []
        for attr in missing_attrs:
            val = specs.get(attr)
            if not val:
                continue

            # Валидация физического здравого смысла
            if not AttributeSanityValidator.is_valid(attr, val, category_key):
                continue

            enriched.append({
                "attribute": attr,
                "value": val,
                "confidence": 0.90,
                "source": "catalog_kb",
                "raw_text": val,
            })

        return enriched
