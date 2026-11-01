"""Make the shared auth/PII layer importable during tests."""

import sys
from pathlib import Path

_LAYER_DIR = str(Path(__file__).parents[2] / "layers" / "common")
if _LAYER_DIR not in sys.path:
    sys.path.insert(0, _LAYER_DIR)
