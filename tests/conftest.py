import sys
from pathlib import Path

# The scripts in src/ import each other by plain name (e.g. `from features import ...`).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
