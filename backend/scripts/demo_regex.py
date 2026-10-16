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
    {
        "id": "demo-white-titanium",
        "title": "Смартфон Apple iPhone 15 Pro Max 256GB White Titanium",
        "description": "Флагман. Экран 6.7 дюймов.",
        "seller_attributes": {},
    },
    {
        "id": "demo-ru-color",
        "title": "Смартфон Samsung Galaxy S24 256 ГБ СЕРЫЙ",
        "description": "ЦВЕТ: серый титан.",
        "seller_attributes": {},
    },
    {
        "id": "demo-mixed-case",
        "title": "XIAOMI Redmi Note 13 Pro 8 ГБ ОЗУ 256 ГБ SSD",
        "description": "БАТАРЕЯ 5000 МАЧ, ЭКРАН 6.67 ДЮЙМОВ",
        "seller_attributes": {},
    }
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