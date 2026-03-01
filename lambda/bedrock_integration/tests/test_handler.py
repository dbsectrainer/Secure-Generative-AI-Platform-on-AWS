"""
Unit tests for the Bedrock orchestrator Lambda handler.

Run with:
    python -m pytest lambda/bedrock_integration/tests/ -v
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_bedrock_response(output_text: str, input_tokens: int = 10, output_tokens: int = 20) -> dict:
    """Build a mock bedrock-runtime invoke_model response for Claude 3."""
    body_bytes = json.dumps(
        {
            "content": [{"type": "text", "text": output_text}],
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        }
    ).encode()

    mock_body = MagicMock()
    mock_body.read.return_value = body_bytes

    return {"body": mock_body}


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    """Set required environment variables for all tests."""
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")
    monkeypatch.setenv("BEDROCK_REGION", "eu-west-1")
    monkeypatch.setenv("DOCUMENT_BUCKET", "test-bucket")
    monkeypatch.setenv("MAX_TOKENS", "512")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")


class TestValidateEvent:
    def test_valid_prompt(self):
        import handler
        assert handler._validate_event({"prompt": "Hello world"}) == "Hello world"

    def test_strips_whitespace(self):
        import handler
        assert handler._validate_event({"prompt": "  Hello  "}) == "Hello"

    def test_missing_prompt_raises(self):
        import handler
        with pytest.raises(ValueError, match="non-empty"):
            handler._validate_event({})

    def test_empty_prompt_raises(self):
        import handler
        with pytest.raises(ValueError, match="non-empty"):
            handler._validate_event({"prompt": "   "})

    def test_oversized_prompt_raises(self):
        import handler
        with pytest.raises(ValueError, match="exceeds maximum"):
            handler._validate_event({"prompt": "x" * 10_001})

    def test_max_length_prompt_passes(self):
        import handler
        result = handler._validate_event({"prompt": "x" * 10_000})
        assert len(result) == 10_000


class TestLambdaHandler:
    def test_successful_invocation(self):
        import handler

        mock_response = _make_bedrock_response("Paris is the capital of France.")

        with patch.object(handler._bedrock_client, "invoke_model", return_value=mock_response):
            result = handler.lambda_handler({"prompt": "What is the capital of France?"}, None)

        assert result["statusCode"] == 200
        assert result["body"]["output"] == "Paris is the capital of France."
        assert result["body"]["usage"]["input_tokens"] == 10
        assert result["body"]["usage"]["output_tokens"] == 20
        assert result["body"]["model_id"] == "anthropic.claude-3-sonnet-20240229-v1:0"

    def test_missing_prompt_returns_400(self):
        import handler

        result = handler.lambda_handler({}, None)

        assert result["statusCode"] == 400
        assert "error" in result["body"]

    def test_empty_prompt_returns_400(self):
        import handler

        result = handler.lambda_handler({"prompt": ""}, None)

        assert result["statusCode"] == 400

    def test_throttling_returns_429(self):
        from botocore.exceptions import ClientError
        import handler

        throttle_error = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "InvokeModel",
        )

        with patch.object(handler._bedrock_client, "invoke_model", side_effect=throttle_error):
            result = handler.lambda_handler({"prompt": "Test prompt"}, None)

        assert result["statusCode"] == 429
        assert "retry" in result["body"]["error"].lower()

    def test_service_unavailable_returns_429(self):
        from botocore.exceptions import ClientError
        import handler

        error = ClientError(
            {"Error": {"Code": "ServiceUnavailableException", "Message": "Service down"}},
            "InvokeModel",
        )

        with patch.object(handler._bedrock_client, "invoke_model", side_effect=error):
            result = handler.lambda_handler({"prompt": "Test prompt"}, None)

        assert result["statusCode"] == 429

    def test_validation_exception_returns_400(self):
        from botocore.exceptions import ClientError
        import handler

        error = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid model"}},
            "InvokeModel",
        )

        with patch.object(handler._bedrock_client, "invoke_model", side_effect=error):
            result = handler.lambda_handler({"prompt": "Test prompt"}, None)

        assert result["statusCode"] == 400

    def test_generic_client_error_returns_502(self):
        from botocore.exceptions import ClientError
        import handler

        error = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Upstream error"}},
            "InvokeModel",
        )

        with patch.object(handler._bedrock_client, "invoke_model", side_effect=error):
            result = handler.lambda_handler({"prompt": "Test prompt"}, None)

        assert result["statusCode"] == 502

    def test_unexpected_error_returns_500(self):
        import handler

        with patch.object(
            handler._bedrock_client, "invoke_model", side_effect=RuntimeError("unexpected")
        ):
            result = handler.lambda_handler({"prompt": "Test prompt"}, None)

        assert result["statusCode"] == 500
        assert result["body"]["error"] == "Internal server error."
