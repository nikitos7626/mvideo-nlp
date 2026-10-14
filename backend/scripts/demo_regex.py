# backend/scripts/demo_regex.py
"""
Демо Tier 1.

Запуск (из корня backend/):
    python -m scripts.demo_regex
"""
from __future__ import annotations

import json

from app.extractors.regex_extractor import RegexExtractor


CARDS = [
    {
        "id": "demo-1",
        "title": "Смартфон Apple iPhone 15 Pro Max 256GB Black Titanium",
        "description": (
            "Флагман с титановым корпусом. Диагональ экрана 6.7 дюймов OLED Retina. "
            "Батарея емкостью 4422 мАч. Цвет: черный титан."
        ),
        "seller_attributes": {"rom": "256gb", "color": "black"},
    },
    {
        "id": "demo-2",
        "title": "Ноутбук Xiaomi RedmiBook 16 ГБ ОЗУ 512 ГБ SSD",
        "description": "Экран 15.6 дюйма, 120 Гц, разрешение 1920x1080.",
        "seller_attributes": {},
    },
    {
        "id": "demo-3",
        "title": "Наушники беспроводные Sony WH-1000XM5",
        "description": "Чёрные, с шумоподавлением.",
        "seller_attributes": {"color": "black"},
    },
]


def main() -> None:
    extractor = RegexExtractor()
    for card in CARDS:
        preds = extractor.extract(card)
        print(f"\n=== {card['id']} ===")
        print(card["title"])
        print(json.dumps(preds, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()