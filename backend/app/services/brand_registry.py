"""
Реестр брендов с поддержкой динамической регистрации (Dynamic Brand Registry).
Позволяет регистрировать новые бренды на лету без перезапуска приложения:
1. Мгновенно добавляет бренд в оперативный KeywordProcessor (FlashText) для поиска за O(1).
2. Персистентно сохраняет новую запись в brands.csv.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Callable

logger = logging.getLogger(__name__)

DEFAULT_BRANDS_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "dictionaries",
    "brands.csv",
)


class BrandRegistry:
    """Синглтон-реестр брендов каталога М.Видео."""

    _instance: BrandRegistry | None = None

    def __init__(self, csv_path: str | None = None) -> None:
        self.csv_path = csv_path or DEFAULT_BRANDS_CSV
        self.brands: dict[str, str] = {}
        self._listeners: list[Callable[[str, str], None]] = []
        self._load()

    @classmethod
    def get_instance(cls) -> BrandRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load(self) -> None:
        """Загружает существующие бренды из CSV."""
        if not os.path.exists(self.csv_path):
            logger.warning("Brands CSV not found at %s", self.csv_path)
            return

        count = 0
        with open(self.csv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(",", 1)
                alias = parts[0].strip().lower()
                canon = parts[1].strip() if len(parts) > 1 else parts[0].strip()
                if alias and canon:
                    self.brands[alias] = canon
                    count += 1
        logger.info("BrandRegistry loaded %d brands from %s", count, self.csv_path)

    def subscribe(self, callback: Callable[[str, str], None]) -> None:
        """Подписывает обработчик (например KeywordProcessor) на появление новых брендов."""
        self._listeners.append(callback)

    def has_brand(self, brand: str) -> bool:
        """Проверяет, зарегистрирован ли бренд."""
        if not brand:
            return False
        return brand.strip().lower() in self.brands

    def get_canonical(self, brand: str) -> str | None:
        """Возвращает каноническое имя бренда или None."""
        if not brand:
            return None
        return self.brands.get(brand.strip().lower())

    def register_brand(self, alias: str, canonical: str | None = None, persist: bool = True) -> bool:
        """
        Динамически регистрирует новый бренд:
        - добавляет в память (O(1))
        - уведомляет слушателей FlashText
        - дописывает в CSV файл для персистентности (если persist=True)
        """
        if not alias or len(alias.strip()) < 2:
            return False

        clean_alias = alias.strip().lower()
        if "," in clean_alias:
            return False

        clean_canon = canonical.strip() if canonical and canonical.strip() else alias.strip().title()

        # Если бренд уже известен, не дублируем
        if clean_alias in self.brands:
            return False

        self.brands[clean_alias] = clean_canon

        # Уведомляем подписчиков (KeywordProcessor и др.)
        for listener in self._listeners:
            try:
                listener(clean_alias, clean_canon)
            except Exception as e:
                logger.error("Error in brand listener: %s", e)

        # Сохраняем на диск при persist=True
        if persist:
            try:
                with open(self.csv_path, "a", encoding="utf-8") as f:
                    f.write(f"{clean_alias},{clean_canon}\n")
                logger.info("Successfully registered new brand: %s -> %s", clean_alias, clean_canon)
            except Exception as e:
                logger.error("Failed to append brand to %s: %s", self.csv_path, e)
                return False

        return True

