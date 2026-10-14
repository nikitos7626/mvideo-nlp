from __future__ import annotations

import io
import json

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.extractors.regex_extractor import RegexExtractor


router = APIRouter(prefix="/api/extract", tags=["extract"])

# FlashText-процессор строится один раз при импорте модуля —
# дальше работает как синглтон, на каждый запрос ничего не собирается.
_extractor = RegexExtractor()

# Обязательные поля, которые хотим видеть в каждой карточке.
# Отсюда считаем "missing" — что не удалось закрыть регулярками.
REQUIRED_ATTRS: set[str] = {
    "brand", "model", "memory_rom",
    "screen_diagonal", "battery", "color",
}


# --------------------------- схемы ---------------------------

class CardIn(BaseModel):
    external_id: str | None = None
    category: str | None = None
    title: str = ""
    description: str = ""
    seller_attributes: dict = Field(default_factory=dict)


class PredictionOut(BaseModel):
    attribute: str
    value: str
    confidence: float
    source: str
    raw: str | None = None


class CardOut(BaseModel):
    external_id: str | None
    category: str | None
    predictions: list[PredictionOut]
    missing: list[str]


class BatchOut(BaseModel):
    total: int
    cards: list[CardOut]


# --------------------------- хелперы ---------------------------

def _run(card: CardIn) -> CardOut:
    """Прогоняет одну карточку через Tier 1 и упаковывает в CardOut."""
    raw_preds = _extractor.extract({
        "title": card.title,
        "description": card.description,
        "seller_attributes": card.seller_attributes,
    })
    found = {p["attribute"] for p in raw_preds}
    return CardOut(
        external_id=card.external_id,
        category=card.category,
        predictions=[PredictionOut(**p) for p in raw_preds],
        missing=sorted(REQUIRED_ATTRS - found),
    )


def _rows_from_file(filename: str, raw: bytes) -> list[dict]:
    """CSV или JSON → список dict'ов. Пустой файл → 400, а не 500."""
    if not raw or not raw.strip():
        raise HTTPException(400, "Файл пустой")

    name = (filename or "").lower()
    if name.endswith(".json"):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise HTTPException(400, f"Невалидный JSON: {e}") from e
        rows = data if isinstance(data, list) else [data]
        if not rows:
            raise HTTPException(400, "В JSON нет карточек")
        return rows

    if name.endswith(".csv"):
        import pandas as pd
        try:
            df = pd.read_csv(io.BytesIO(raw))
        except pd.errors.EmptyDataError as e:
            raise HTTPException(400, "CSV не содержит колонок/строк") from e
        if df.empty:
            raise HTTPException(400, "CSV пустой")
        return df.to_dict(orient="records")

    raise HTTPException(400, "Только CSV или JSON")


# --------------------------- эндпоинты ---------------------------

@router.get("/health")
def health() -> dict:
    """Быстрая проверка: extractor поднят, версия видна."""
    return {
        "ok": True,
        "extractor": _extractor.name,
        "version": _extractor.version,
    }


@router.post("", response_model=CardOut)
def extract_one(card: CardIn) -> CardOut:
    """
    Одна карточка → список извлечённых атрибутов.

    Пример тела запроса:
    {
      "external_id": "sku-1",
      "category": "smartphones",
      "title": "Смартфон Apple iPhone 15 Pro Max 256GB Black Titanium",
      "description": "Экран 6.7 дюймов, батарея 4422 мАч",
      "seller_attributes": {"rom": "256gb", "color": "black"}
    }
    """
    return _run(card)


@router.post("/batch", response_model=BatchOut)
async def extract_batch(file: UploadFile = File(...)) -> BatchOut:
    """
    Файл CSV или JSON → список карточек с извлечёнными атрибутами.

    Ожидаемые колонки: external_id, category, title, description, seller_attributes.
    seller_attributes в CSV — JSON-строка, в JSON — объект.
    """
    rows = _rows_from_file(file.filename or "", await file.read())

    cards: list[CardOut] = []
    for i, row in enumerate(rows):
        # seller_attributes может прийти строкой из CSV — парсим
        sa = row.get("seller_attributes")
        if isinstance(sa, str):
            try:
                row["seller_attributes"] = json.loads(sa) if sa.strip() else {}
            except json.JSONDecodeError:
                raise HTTPException(
                    400,
                    f"Row {i}: seller_attributes не валидный JSON: {sa!r}",
                )
        cards.append(_run(CardIn(**row)))

    return BatchOut(total=len(cards), cards=cards)