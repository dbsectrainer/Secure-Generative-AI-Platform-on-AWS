"""
pytest configuration for genai tests.
"""
import sys
from pathlib import Path

_PROMPT_BUILDER = Path(__file__).parent.parent / "prompt_builder"
sys.path.insert(0, str(_PROMPT_BUILDER))
