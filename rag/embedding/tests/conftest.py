"""
pytest configuration: add the rag/embedding directory to sys.path so that
handler.py can be imported directly.
"""
import os
import sys
from pathlib import Path

import pytest

_HANDLER_DIR = str(Path(__file__).parent.parent)


@pytest.fixture(autouse=True, scope="module")
def _load_embedding_handler():
    """Ensure rag/embedding/handler.py is loaded (once per test module)."""
    os.environ.setdefault("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")
    os.environ.setdefault("BEDROCK_REGION", "eu-west-1")
    os.environ.setdefault("OPENSEARCH_ENDPOINT", "https://test.aoss.amazonaws.com")
    os.environ.setdefault("OPENSEARCH_INDEX", "rag-documents")

    sys.modules.pop("handler", None)
    if _HANDLER_DIR not in sys.path:
        sys.path.insert(0, _HANDLER_DIR)
    else:
        sys.path.remove(_HANDLER_DIR)
        sys.path.insert(0, _HANDLER_DIR)
    yield
