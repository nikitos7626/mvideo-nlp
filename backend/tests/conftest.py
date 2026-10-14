import sys
from pathlib import Path

# на всякий случай — если запускаешь pytest из другой директории
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))