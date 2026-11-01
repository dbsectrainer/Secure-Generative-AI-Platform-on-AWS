"""
pytest configuration: add the rag/orchestrator, genai/prompt_builder, and
shared auth layer directories to sys.path so their modules can be imported
directly.
"""
import os
import sys
from pathlib import Path

import pytest

_ORCHESTRATOR_DIR = str(Path(__file__).parent.parent)
_PROMPT_BUILDER_DIR = str(Path(__file__).parent.parent.parent.parent / "genai" / "prompt_builder")
_COMMON_LAYER = str(Path(__file__).parents[3] / "layers" / "common")

for _path in (_COMMON_LAYER, _PROMPT_BUILDER_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)


@pytest.fixture(autouse=True, scope="module")
def _load_orchestrator_handler():
    """Ensure rag/orchestrator/handler.py is loaded (once per test module)."""
    os.environ.setdefault("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-5-5")
    os.environ.setdefault("BEDROCK_REGION", "eu-west-1")
    os.environ.setdefault("RETRIEVAL_LAMBDA_ARN", "arn:aws:lambda:eu-west-1:000000000000:function:retrieve")

    sys.modules.pop("handler", None)
    for _d in (_PROMPT_BUILDER_DIR, _ORCHESTRATOR_DIR):
        if _d in sys.path:
            sys.path.remove(_d)
        sys.path.insert(0, _d)
    yield
