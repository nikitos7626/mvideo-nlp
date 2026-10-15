# interactive.py
"""
Быстрый запуск интерактивного режима из корня проекта.

Запуск:
    python interactive.py
"""
import os
import sys

# Добавляем backend в sys.path
backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from scripts.interactive import main

if __name__ == "__main__":
    main()
