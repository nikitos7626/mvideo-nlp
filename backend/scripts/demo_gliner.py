# backend/scripts/demo_gliner.py
"""
Демо Tier 2: GLiNER Zero-Shot экстрактор.

Запуск (из корня backend/):
    python -m scripts.demo_gliner
"""
from __future__ import annotations

import json
import sys

from app.extractors.gliner_extractor import GlinerExtractor

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


CARDS = [
    {
        "id": "demo-1",
        "title": "Смартфон Apple iPhone 15 Pro Max 256GB Black Titanium",
        "description": (
            "Флагман с титановым корпусом на чипе Apple A17 Pro. "
            "Экран 6.7 дюймов 120 Гц. Батарея 4422 мАч. Цвет: черный титан."
        ),
        "seller_attributes": {"rom": "256gb", "color": "black"},
    },
    {
        "id": "demo-2",
        "title": "Ноутбук Xiaomi RedmiBook 16 ГБ ОЗУ 512 ГБ SSD",
        "description": "Процессор Intel Core i5-12450H, экран 15.6 дюйма, 120 Гц, разрешение 1920x1080.",
        "seller_attributes": {},
    },
    {
        "id": "demo-3",
        "title": "Наушники беспроводные Sony WH-1000XM5",
        "description": "Чёрные, с активным шумоподавлением.",
        "seller_attributes": {"color": "black"},
    },
]


def main() -> None:
    extractor = GlinerExtractor()
    for card in CARDS:
        preds = extractor.extract(card)
        print(f"\n=== {card['id']}: {card['title']} ===")
        print(json.dumps(preds, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
