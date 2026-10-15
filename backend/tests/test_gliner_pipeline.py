import pytest

from app.extractors.gliner_extractor import GlinerExtractor
from app.services.pipeline import CascadedExtractionPipeline


@pytest.fixture(scope="module")
def gliner():
    return GlinerExtractor()


@pytest.fixture(scope="module")
def pipeline():
    return CascadedExtractionPipeline(use_gliner=True)


def _get(preds, attr):
    return next((p for p in preds if p["attribute"] == attr), None)


def test_gliner_model_extraction(gliner):
    card = {
        "title": "Смартфон Apple iPhone 15 Pro Max 256GB Black Titanium",
        "description": "Флагман с титановым корпусом на чипе Apple A17 Pro.",
    }
    preds = gliner.extract(card)
    model = _get(preds, "model")
    brand = _get(preds, "brand")

    assert model is not None
    assert "iPhone 15 Pro Max" in model["value"]
    assert brand is not None
    assert brand["value"] == "Apple"


def test_gliner_headphone_model(gliner):
    card = {
        "title": "Наушники беспроводные Sony WH-1000XM5",
        "description": "Чёрные, с активным шумоподавлением.",
    }
    preds = gliner.extract(card)
    model = _get(preds, "model")
    assert model is not None
    assert model["value"] == "WH-1000XM5"


def test_cascaded_pipeline_full_integration(pipeline):
    card = {
        "id": "test-101",
        "title": "Смартфон Apple iPhone 15 Pro Max 256GB Black Titanium",
        "description": (
            "Флагман с титановым корпусом. Экран 6.7 дюймов 120 Гц. Батарея емкостью 4422 мАч."
        ),
        "seller_attributes": {"rom": "256gb", "color": "black"},
    }
    res = pipeline.process_card(card)

    assert res["overall_confidence"] >= 0.75
    assert not res["needs_review"]
    attrs = {p["attribute"]: p["value"] for p in res["predictions"]}

    assert attrs.get("brand") == "Apple"
    assert "iPhone 15 Pro Max" in attrs.get("model", "")
    assert attrs.get("memory_rom") == "256 ГБ"
    assert attrs.get("screen_diagonal") == '6,7"'
    assert attrs.get("battery") == "4422 мАч"
