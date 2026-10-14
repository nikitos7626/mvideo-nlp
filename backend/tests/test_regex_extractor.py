import pytest

from app.extractors.regex_extractor import RegexExtractor


@pytest.fixture
def ext():
    return RegexExtractor()


def _get(preds, attr):
    return next((p for p in preds if p["attribute"] == attr), None)


# ---------- ROM ----------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("256 ГБ", "256 ГБ"),
        ("256GB", "256 ГБ"),
        ("1 ТБ", "1 ТБ"),
        ("1024 ГБ", "1 ТБ"),
        ("512 гб", "512 ГБ"),
    ],
)
def test_rom(ext, raw, expected):
    p = _get(ext.extract({"title": f"Смартфон {raw}", "description": ""}),
             "memory_rom")
    assert p and p["value"] == expected


# ---------- Экран ----------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ('6.7"', '6,7"'),
        ("6.7 дюймов", '6,7"'),
        ("6,7 дюйма", '6,7"'),
    ],
)
def test_screen(ext, raw, expected):
    p = _get(ext.extract({"title": f"Экран {raw}", "description": ""}),
             "screen_diagonal")
    assert p and p["value"] == expected


# ---------- RAM vs ROM ----------

@pytest.mark.parametrize(
    "text,ram,rom",
    [
        ("Ноутбук 16 ГБ ОЗУ 512 ГБ SSD",  "16 ГБ", "512 ГБ"),
        ("Ноутбук ОЗУ 32 ГБ / SSD 1 ТБ",  "32 ГБ", "1 ТБ"),
        ("Смартфон 8 ГБ RAM 128 ГБ ROM",  "8 ГБ",  "128 ГБ"),
        ("iPhone 256 ГБ",                 None,    "256 ГБ"),
    ],
)
def test_ram_rom_disambiguation(ext, text, ram, rom):
    preds = ext.extract({"title": text, "description": ""})
    got_ram = _get(preds, "memory_ram")
    got_rom = _get(preds, "memory_rom")
    assert (got_ram["value"] if got_ram else None) == ram
    assert (got_rom["value"] if got_rom else None) == rom


# ---------- Прочее ----------

def test_brand_from_seller_overrides_text(ext):
    preds = ext.extract({
        "title": "Смартфон Samsung Galaxy",
        "description": "",
        "seller_attributes": {"brand": "Apple"},
    })
    assert _get(preds, "brand")["value"] == "Apple"


def test_no_hallucination(ext):
    preds = ext.extract({"title": "Наушники беспроводные", "description": ""})
    assert _get(preds, "memory_rom") is None
    assert _get(preds, "screen_diagonal") is None