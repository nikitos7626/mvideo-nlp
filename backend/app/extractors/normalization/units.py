import re

class UnitNormalizer:
    """Приводит единицы измерения к каноническому виду М.Видео."""

    # --- Память ---
    @staticmethod
    def memory(value: str, unit: str) -> str:
        """1024 ГБ → 1 ТБ ; 256gb → 256 ГБ ; 0.5 TB → 512 ГБ."""
        num = float(value.replace(",", "."))
        u = unit.upper().replace("B", "Б").replace("T", "Т")

        if u in ("ТБ", "TB", "ТБАЙТ"):
            gb = num * 1024
        else:
            gb = num

        if gb >= 1024 and gb % 1024 == 0:
            return f"{int(gb / 1024)} ТБ"
        return f"{int(gb)} ГБ" if gb.is_integer() else f"{gb} ГБ"

    # --- Экран: 6.7 дюйма / 6.7" / 6,7 in → 6,7" ---
    @staticmethod
    def screen_diagonal(value: str) -> str:
        num = float(value.replace(",", "."))
        # в каталоге М.Видео дробная часть через запятую, единица — дюйм-кавычка
        if num.is_integer():
            result = str(int(num))
        else:
            result = str(num).replace(".", ",")
            
        return f'{result}"'

    # --- Батарея: 4.422 mAh / 4422 mah → 4422 мАч ---
    @staticmethod
    def battery(value: str) -> str:
        num = int(float(value.replace(",", ".").replace(" ", "")))
        return f"{num} мАч"

    # --- Частота: 120 hz / 120 Гц → 120 Гц ---
    @staticmethod
    def refresh_rate(value: str) -> str:
        return f"{int(float(value.replace(',', '.')))} Гц"

    # --- Разрешение: 1920 x 1080 → 1920×1080 ---
    @staticmethod
    def resolution(w: str, h: str) -> str:
        return f"{int(w)}×{int(h)}"