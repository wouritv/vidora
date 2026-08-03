from pathlib import Path
import sys

# Ensure tests can import top-level backend modules (app.py, main.py, etc.)
# regardless of the current working directory used by CI.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

