"""
Строгий LLM-фоллбэк экстрактор характеристик (Strict LLM Fallback Extractor).
Вызывается ТОЛЬКО точечно при наличии пропусков в карточке и точной модели,
с жестким контролем галлюцинаций через схему JSON и AttributeSanityValidator.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx

from app.config import settings
from app.extractors.base import Prediction
from app.extractors.sanity import AttributeSanityValidator

logger = logging.getLogger(__name__)


class StrictLlmFallbackExtractor:
    """
    Tier 3: Строгий точечный LLM-фоллбэк для редких пропусков и новых брендов.
    Поддерживает любой OpenAI-совместимый эндпоинт (GigaChat, vLLM, LiteLLM, DeepSeek, OpenAI).
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        model: str | None = None,
        timeout: float = 3.5,
    ) -> None:
        self.api_key = api_key or os.environ.get("LLM_API_KEY") or getattr(settings, "llm_api_key", "")
        self.api_base = (
            api_base
            or os.environ.get("LLM_API_BASE")
            or getattr(settings, "llm_api_base", "https://api.openai.com/v1")
        ).rstrip("/")
        self.model = model or os.environ.get("LLM_MODEL") or getattr(settings, "llm_model", "gpt-4o-mini")
        self.timeout = timeout
        self.is_enabled = bool(self.api_key and self.api_key.strip())

        if self.is_enabled:
            logger.info("StrictLlmFallbackExtractor activated with model %s", self.model)
        else:
            logger.info("StrictLlmFallbackExtractor disabled (no LLM_API_KEY provided)")

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str | None:
        """Безопасный вызов LLM с таймаутом и перехватом любых сбоев сети."""
        if not self.is_enabled:
            return None

        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 200,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices") or []
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()
                else:
                    logger.warning("LLM API returned status %d: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            logger.warning("LLM call failed or timed out: %s", e)

        return None

    def enrich_missing_attributes(
        self,
        brand: str,
        model: str,
        missing_attrs: set[str],
        category_key: str,
        raw_text: str = "",
    ) -> list[Prediction]:
        """
        Точечный запрос в LLM для заполнения ТОЛЬКО пропущенных обязательных полей.
        Возвращает проверенные через AttributeSanityValidator предсказания.
        """
        if not self.is_enabled or not missing_attrs or not (brand or model):
            return []

        system_prompt = (
            "Ты — промышленный экстрактор спецификаций каталога М.Видео. "
            "Твоя задача — вернуть официальные заводские характеристики для указанной модели техники. "
            "Категорически запрещено выдумывать, гадать или округлять. "
            "Если точное заводское значение неизвестно на 100% — верни null. "
            "Ответ строго в формате JSON без разметки markdown."
        )

        attrs_list = sorted(list(missing_attrs))
        user_prompt = (
            f"Товар: {brand} {model}\n"
            f"Описание продавца: {raw_text[:300]}\n"
            f"Заполни ТОЛЬКО следующие недостающие параметры: {attrs_list}\n"
            f"Формат: JSON-объект, где ключи — названия параметров ({attrs_list}), "
            "а значения — строки с физическими единицами (например '5000 мАч', '6.67\"', 'Snapdragon 8 Gen 3') или null."
        )

        content = self._call_llm(system_prompt, user_prompt)
        if not content:
            return []

        # Парсим JSON из ответа
        # Срезаем markdown code fences если модель вернула ```json
        content_clean = re.sub(r"^```(?:json)?\s*", "", content.strip())
        content_clean = re.sub(r"\s*```$", "", content_clean).strip()

        try:
            data = json.loads(content_clean)
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from LLM: %r", content)
            return []

        if not isinstance(data, dict):
            return []

        out: list[Prediction] = []
        for attr in missing_attrs:
            val = data.get(attr)
            if not val or not isinstance(val, str):
                continue

            val_clean = val.strip()
            if not val_clean or val_clean.lower() in ("null", "none", "unknown", "нет"):
                continue

            # Физическая валидация здравого смысла М.Видео
            if not AttributeSanityValidator.is_valid(attr, val_clean, category_key):
                logger.warning("LLM proposed value '%s' for %s rejected by SanityValidator", val_clean, attr)
                continue

            out.append({
                "attribute": attr,
                "value": val_clean,
                "confidence": 0.88,
                "source": "llm_strict",
                "raw_text": val_clean,
            })

        return out

    def verify_new_brand(self, candidate_brand: str, context: str = "") -> bool:
        """
        Проверяет через LLM, является ли кандидат реальным брендом/производителем.
        Используется перед автоматической регистрацией нового бренда в базу данных.
        """
        if not self.is_enabled or not candidate_brand or len(candidate_brand) < 2:
            return False

        system_prompt = (
            "Ты — валидатор сущностей торгового каталога М.Видео. "
            "Отвечай строго одним словом: YES или NO."
        )
        user_prompt = (
            f"Является ли '{candidate_brand}' реальным брендом, торговой маркой или производителем "
            f"электроники, бытовой техники или потребительских товаров?\n"
            f"Контекст: {context[:200]}\n"
            "Ответь строго YES или NO."
        )

        content = self._call_llm(system_prompt, user_prompt)
        if not content:
            return False

        clean_resp = content.strip().upper()
        return "YES" in clean_resp
