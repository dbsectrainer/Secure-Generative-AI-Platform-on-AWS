"""
Unit tests for rag/embedding/handler.py

Run with:
    python -m pytest rag/tests/test_embedding.py -v
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")
    monkeypatch.setenv("BEDROCK_REGION", "eu-west-1")
    monkeypatch.setenv("OPENSEARCH_ENDPOINT", "https://test.aoss.amazonaws.com")
    monkeypatch.setenv("OPENSEARCH_INDEX", "rag-documents")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")


def _make_bedrock_embed_response(vector: list[float]) -> dict:
    body_bytes = json.dumps({"embedding": vector}).encode()
    mock_body = MagicMock()
    mock_body.read.return_value = body_bytes
    return {"body": mock_body}


class TestValidateEvent:
    def test_valid_event(self):
        import handler
        text, meta = handler._validate_event({"text": "hello", "metadata": {"k": "v"}})
        assert text == "hello"
        assert meta == {"k": "v"}

    def test_empty_text_raises(self):
        import handler
        with pytest.raises(ValueError, match="non-empty"):
            handler._validate_event({"text": "   "})

    def test_missing_text_raises(self):
        import handler
        with pytest.raises(ValueError, match="non-empty"):
            handler._validate_event({})

    def test_oversized_text_raises(self):
        import handler
        with pytest.raises(ValueError, match="exceeds maximum"):
            handler._validate_event({"text": "x" * 32_769})

    def test_non_dict_metadata_is_replaced(self):
        import handler
        _, meta = handler._validate_event({"text": "hello", "metadata": "bad"})
        assert meta == {}


class TestGenerateEmbedding:
    def test_returns_vector(self):
        import handler
        vector = [0.1, 0.2, 0.3]
        mock_resp = _make_bedrock_embed_response(vector)
        with patch.object(handler._bedrock_client, "invoke_model", return_value=mock_resp):
            result = handler._generate_embedding("test text")
        assert result == vector

    def test_throttling_raises_client_error(self):
        import handler
        from botocore.exceptions import ClientError
        error = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "InvokeModel",
        )
        with patch.object(handler._bedrock_client, "invoke_model", side_effect=error):
            with pytest.raises(ClientError):
                handler._generate_embedding("test")


class TestLambdaHandler:
    def test_successful_embedding(self):
        import handler
        vector = [0.1] * 1024
        mock_resp = _make_bedrock_embed_response(vector)

        with (
            patch.object(handler._bedrock_client, "invoke_model", return_value=mock_resp),
            patch.object(handler, "_index_document") as mock_index,
        ):
            mock_index.return_value = None
            result = handler.lambda_handler(
                {"text": "hello world", "metadata": {"doc": "test.txt"}}, None
            )

        assert result["statusCode"] == 200
        assert result["body"]["indexed"] is True
        assert result["body"]["dimensions"] == 1024

    def test_missing_text_returns_400(self):
        import handler
        result = handler.lambda_handler({}, None)
        assert result["statusCode"] == 400

    def test_throttling_returns_429(self):
        import handler
        from botocore.exceptions import ClientError
        error = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "InvokeModel",
        )
        with patch.object(handler._bedrock_client, "invoke_model", side_effect=error):
            result = handler.lambda_handler({"text": "hello"}, None)
        assert result["statusCode"] == 429

    def test_opensearch_error_returns_502(self):
        import handler
        vector = [0.1] * 1024
        mock_resp = _make_bedrock_embed_response(vector)

        with (
            patch.object(handler._bedrock_client, "invoke_model", return_value=mock_resp),
            patch.object(
                handler, "_index_document", side_effect=RuntimeError("OS error")
            ),
        ):
            result = handler.lambda_handler({"text": "hello"}, None)

        assert result["statusCode"] == 502
        # Endpoint/response internals must not be disclosed to callers.
        assert "OS error" not in result["body"]["error"]

    def test_unexpected_error_returns_500(self):
        import handler
        with patch.object(
            handler._bedrock_client, "invoke_model", side_effect=Exception("boom")
        ):
            result = handler.lambda_handler({"text": "hello"}, None)
        assert result["statusCode"] == 500


def _proxy_event(payload: dict | str | None) -> dict:
    """Build an API Gateway Lambda proxy event with a JSON body."""
    if payload is not None and not isinstance(payload, str):
        payload = json.dumps(payload)
    return {
        "httpMethod": "POST",
        "path": "/embed",
        "headers": {"Content-Type": "application/json"},
        "body": payload,
        "isBase64Encoded": False,
        "requestContext": {"requestId": "test-request"},
    }


class TestApiGatewayProxy:
    """Regression coverage for the documented HTTP `/embed` endpoint."""

    def test_proxy_event_body_is_parsed_and_response_is_json(self):
        import handler

        vector = [0.1] * 1024
        mock_resp = _make_bedrock_embed_response(vector)

        with (
            patch.object(handler._bedrock_client, "invoke_model", return_value=mock_resp),
            patch.object(handler, "_index_document"),
        ):
            result = handler.lambda_handler(
                _proxy_event({"text": "hello", "metadata": {"doc": "a.txt"}}), None
            )

        assert result["statusCode"] == 200
        parsed = json.loads(result["body"])
        assert parsed["indexed"] is True
        assert parsed["dimensions"] == 1024

    def test_malformed_json_body_returns_400(self):
        import handler

        result = handler.lambda_handler(_proxy_event("{bad"), None)

        assert result["statusCode"] == 400
        assert "valid JSON" in json.loads(result["body"])["error"]

    def test_empty_body_returns_400(self):
        import handler

        result = handler.lambda_handler(_proxy_event(None), None)

        assert result["statusCode"] == 400
