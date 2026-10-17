from app.extractors.sanity import AttributeSanityValidator
from app.services.pipeline import CascadedExtractionPipeline


def test_sanity_battery_valid_and_invalid():
    # Валидная батарея
    assert AttributeSanityValidator.is_valid("battery", "5000 мАч", "smartphones")
    assert AttributeSanityValidator.is_valid("battery", "4500 mAh", "smartphones")

    # Перепутанные единицы (частота экрана или память в батарее)
    assert not AttributeSanityValidator.is_valid("battery", "144 Гц", "smartphones")
    assert not AttributeSanityValidator.is_valid("battery", "120 Hz", "smartphones")
    assert not AttributeSanityValidator.is_valid("battery", "6.7 дюймов", "smartphones")
    assert not AttributeSanityValidator.is_valid("battery", "256 ГБ", "smartphones")


def test_sanity_screen_cross_pollution():
    # Валидный экран
    assert AttributeSanityValidator.is_valid("screen_diagonal", "6.7 дюйм", "smartphones")
    assert AttributeSanityValidator.is_valid("screen_diagonal", "15.6\"", "laptops")
    assert AttributeSanityValidator.is_valid("screen_diagonal", "55\"", "tvs")

    # Смартфон с экраном 15.6" — физически невозможно
    assert not AttributeSanityValidator.is_valid("screen_diagonal", "15.6\"", "smartphones")
    # Перепутанная частота или батарея в экране
    assert not AttributeSanityValidator.is_valid("screen_diagonal", "144 Гц", "smartphones")
    assert not AttributeSanityValidator.is_valid("screen_diagonal", "5000 мАч", "smartphones")


def test_sanity_category_forbidden_attributes():
    # Пылесос и холодильник не имеют ОЗУ, накопителя или процессора
    assert not AttributeSanityValidator.is_valid("memory_rom", "256 ГБ", "vacuum_cleaners")
    assert not AttributeSanityValidator.is_valid("memory_ram", "16 ГБ", "refrigerators")
    assert not AttributeSanityValidator.is_valid("cpu", "Snapdragon 8 Gen 2", "vacuum_cleaners")
    assert not AttributeSanityValidator.is_valid("screen_diagonal", "6.7 дюйм", "vacuum_cleaners")


def test_sanity_color_marketing_spam():
    # Реальные цвета
    assert AttributeSanityValidator.is_valid("color", "Черный титан", "smartphones")
    assert AttributeSanityValidator.is_valid("color", "Синий", "smartphones")

    # Маркетинговый спам и ошибочные спаны
    assert not AttributeSanityValidator.is_valid("color", "красивый дизайн", "smartphones")
    assert not AttributeSanityValidator.is_valid("color", "15 Pro Max", "smartphones")
    assert not AttributeSanityValidator.is_valid("color", "новинка 2024", "smartphones")


def test_pipeline_blocks_sanity_violations():
    pipeline = CascadedExtractionPipeline(use_gliner=False)
    # Карточка, где в тексте нарочно написана галлюцинация или перепутанные единицы
    card = {
        "title": "Робот-пылесос Xiaomi Mi Robot Vacuum 5000 мАч",
        "description": "Сухая и влажная уборка. Батарея 5000 мАч. Экран 6.7 дюймов 120 Гц. Память 256 ГБ.",
    }
    res = pipeline.process_card(card)
    attrs = {p["attribute"]: p["value"] for p in res["predictions"]}

    # Батарея и тип уборки должны пройти
    assert attrs.get("battery") == "5000 мАч"
    assert attrs.get("brand") == "Xiaomi"

    # Экран и память на пылесосе должны быть заблокированы валидатором
    assert "screen_diagonal" not in attrs
    assert "memory_rom" not in attrs
    assert "refresh_rate" not in attrs
