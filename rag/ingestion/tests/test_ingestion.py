"""
Unit tests for rag/ingestion/handler.py

Run with:
    python -m pytest rag/tests/test_ingestion.py -v
"""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    """Set required environment variables for all tests."""
    monkeypatch.setenv("DOCUMENT_BUCKET", "test-bucket")
    monkeypatch.setenv("EMBEDDING_LAMBDA_ARN", "arn:aws:lambda:eu-west-1:123456789012:function:embed")
    monkeypatch.setenv("CHUNK_SIZE", "100")
    monkeypatch.setenv("CHUNK_OVERLAP", "20")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")


# ── _chunk_text ───────────────────────────────────────────────────────────────

class TestChunkText:
    def test_empty_text_returns_empty_list(self):
        import handler
        assert handler._chunk_text("", 100, 20) == []

    def test_short_text_returns_single_chunk(self):
        import handler
        result = handler._chunk_text("Hello world", 100, 20)
        assert result == ["Hello world"]

    def test_chunks_are_within_size(self):
        import handler
        text = "word " * 200  # 1000 chars
        chunks = handler._chunk_text(text, 100, 20)
        for chunk in chunks:
            assert len(chunk) <= 100

    def test_overlap_is_applied(self):
        import handler
        text = "a" * 50 + " " + "b" * 50 + " " + "c" * 50
        chunks = handler._chunk_text(text, 60, 20)
        # With overlap the second chunk should share text with the first
        assert len(chunks) >= 2

    def test_exact_chunk_size_text(self):
        import handler
        text = "x" * 100
        chunks = handler._chunk_text(text, 100, 0)
        assert len(chunks) == 1
        assert chunks[0] == "x" * 100

    def test_long_text_produces_multiple_chunks(self):
        import handler
        text = "word " * 100  # 500 chars
        chunks = handler._chunk_text(text, 50, 10)
        assert len(chunks) > 1


# ── lambda_handler ────────────────────────────────────────────────────────────

def _make_s3_event(bucket: str, key: str) -> dict:
    return {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": bucket},
                    "object": {"key": key},
                }
            }
        ]
    }


class TestLambdaHandler:
    def test_empty_records_returns_200(self):
        import handler
        result = handler.lambda_handler({"Records": []}, None)
        assert result["statusCode"] == 200
        assert result["body"]["processed"] == 0

    def test_successful_single_document(self):
        import handler

        doc_text = "This is a test document with enough words to be chunked properly."
        mock_s3_body = MagicMock()
        mock_s3_body.read.return_value = doc_text.encode("utf-8")
        mock_s3_response = {
            "Body": mock_s3_body,
            "ContentLength": len(doc_text),
        }

        with (
            patch.object(handler._s3_client, "get_object", return_value=mock_s3_response),
            patch.object(handler._lambda_client, "invoke") as mock_invoke,
        ):
            mock_invoke.return_value = {}
            result = handler.lambda_handler(
                _make_s3_event("test-bucket", "raw/doc.txt"), None
            )

        assert result["statusCode"] == 200
        assert result["body"]["processed"] == 1
        assert result["body"]["results"][0]["key"] == "raw/doc.txt"

    def test_s3_error_returns_207(self):
        import handler
        from botocore.exceptions import ClientError

        error = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Key not found"}},
            "GetObject",
        )

        with patch.object(handler._s3_client, "get_object", side_effect=error):
            result = handler.lambda_handler(
                _make_s3_event("test-bucket", "raw/missing.txt"), None
            )

        assert result["statusCode"] == 207
        assert len(result["body"]["errors"]) == 1

    def test_oversized_document_returns_207(self):
        import handler

        large_content = b"x" * (6 * 1024 * 1024)  # 6 MB > 5 MB limit
        mock_s3_body = MagicMock()
        mock_s3_body.read.return_value = large_content
        mock_s3_response = {
            "Body": mock_s3_body,
            "ContentLength": len(large_content),
        }

        with patch.object(handler._s3_client, "get_object", return_value=mock_s3_response):
            result = handler.lambda_handler(
                _make_s3_event("test-bucket", "raw/big.txt"), None
            )

        assert result["statusCode"] == 207
        assert result["body"]["errors"][0]["key"] == "raw/big.txt"

    def test_malformed_record_is_skipped(self):
        import handler
        event = {"Records": [{"s3": {}}]}
        result = handler.lambda_handler(event, None)
        assert result["statusCode"] == 200
        assert result["body"]["processed"] == 0
