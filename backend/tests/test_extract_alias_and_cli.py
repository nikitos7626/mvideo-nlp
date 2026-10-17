import subprocess
import sys
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_extract_alias_endpoint():
    """Тест эндпоинта-алиаса POST /extract (для автоматических тестеров)."""
    payload = {
        "title": "Смартфон Apple iPhone 15 Pro Max 256GB синий титан",
        "description": "Флагманский смартфон"
    }
    response = client.post("/extract", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "Смартфоны"
    assert any(p["attribute"] == "brand" and p["value"] == "Apple" for p in data["predictions"])


def test_root_content_negotiation_json():
    """Тест GET / с Accept: application/json."""
    response = client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 200
    data = response.json()
    assert "endpoints" in data
    assert data["endpoints"]["extract"] == "POST /api/extract"
    assert data["endpoints"]["extract_alias"] == "POST /extract"


def test_extract_cli_module_import():
    """Тест функции extract_attributes из extract.py."""
    from extract import extract_attributes
    res = extract_attributes("Смартфон Samsung S24 256GB")
    assert res["category"] == "Смартфоны"
    assert any(p["attribute"] == "brand" and p["value"] == "Samsung" for p in res["predictions"])
