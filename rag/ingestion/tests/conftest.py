"""
pytest configuration: add the rag/ingestion directory to sys.path so that
handler.py can be imported directly.
"""
import os
import sys
from pathlib import Path

import pytest

_HANDLER_DIR = str(Path(__file__).parent.parent)


@pytest.fixture(autouse=True, scope="module")
def _load_ingestion_handler():
    """Ensure rag/ingestion/handler.py is loaded (once per test module)."""
    # Set required env vars before first import of this handler
    os.environ.setdefault("DOCUMENT_BUCKET", "test-bucket")
    os.environ.setdefault("EMBEDDING_LAMBDA_ARN", "arn:aws:lambda:eu-west-1:000000000000:function:embed")
    os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-1")

    sys.modules.pop("handler", None)
    if _HANDLER_DIR not in sys.path:
        sys.path.insert(0, _HANDLER_DIR)
    else:
        sys.path.remove(_HANDLER_DIR)
        sys.path.insert(0, _HANDLER_DIR)
    yield
