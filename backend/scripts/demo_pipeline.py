# backend/scripts/demo_pipeline.py
"""
Демо Каскадного пайплайна (Tier 1 Regex + Tier 2 GLiNER + HITL).

Запуск (из корня backend/):
    python -m scripts.demo_pipeline
"""
from __future__ import annotations

import json
import sys

from app.services.pipeline import CascadedExtractionPipeline

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


CARDS = [
    {
        "id": "demo-1",
        "title": "Смартфон Apple iPhone 15 Pro Max 256GB Black Titanium",
        "description": (
            "Флагман с титановым корпусом на чипе Apple A17 Pro. "
            "Диагональ экрана 6.7 дюймов OLED Retina 120 Гц. Батарея емкостью 4422 мАч. Цвет: черный титан."
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
    pipeline = CascadedExtractionPipeline(use_gliner=True)
    for card in CARDS:
        res = pipeline.process_card(card)
        print(f"\n==========================================")
        print(f"SKU ID: {res['external_id']} | Overall Conf: {res['overall_confidence']} | Needs Review: {res['needs_review']}")
        print(f"Found attributes: {len(res['predictions'])} | Missing: {res['missing']}")
        print(json.dumps(res["predictions"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
