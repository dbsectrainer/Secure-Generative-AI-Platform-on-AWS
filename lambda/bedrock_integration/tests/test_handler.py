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
    """Build a mock bedrock-runtime invoke_model response for Claude."""
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
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-5-5")
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
        assert result["body"]["model_id"] == "anthropic.claude-sonnet-5-5"

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


def _proxy_event(payload: dict | str | None) -> dict:
    """Build an API Gateway Lambda proxy event with a JSON body."""
    if payload is not None and not isinstance(payload, str):
        payload = json.dumps(payload)
    return {
        "httpMethod": "POST",
        "path": "/invoke",
        "headers": {"Content-Type": "application/json"},
        "body": payload,
        "isBase64Encoded": False,
        "requestContext": {"requestId": "test-request"},
    }


class TestApiGatewayProxy:
    """Regression coverage for the documented `sam local start-api` contract.

    Before this coverage existed, handlers read `prompt` from the top-level
    proxy event, so every HTTP request returned 400.
    """

    def test_proxy_event_body_is_parsed_and_response_is_json(self):
        import handler

        mock_response = _make_bedrock_response("Grounded answer.")

        with patch.object(handler._bedrock_client, "invoke_model", return_value=mock_response):
            result = handler.lambda_handler(
                _proxy_event({"prompt": "What is the policy?"}), None
            )

        assert result["statusCode"] == 200
        assert isinstance(result["body"], str)
        parsed = json.loads(result["body"])
        assert parsed["output"] == "Grounded answer."
        assert result["headers"]["Content-Type"] == "application/json"

    def test_malformed_json_body_returns_400_not_500(self):
        import handler

        result = handler.lambda_handler(_proxy_event("{not json"), None)

        assert result["statusCode"] == 400
        parsed = json.loads(result["body"])
        assert "valid JSON" in parsed["error"]

    def test_empty_body_returns_400(self):
        import handler

        result = handler.lambda_handler(_proxy_event(None), None)

        assert result["statusCode"] == 400
        assert "required" in json.loads(result["body"])["error"]

    def test_non_object_json_body_returns_400(self):
        import handler

        result = handler.lambda_handler(_proxy_event('["not", "an", "object"]'), None)

        assert result["statusCode"] == 400
        assert "JSON object" in json.loads(result["body"])["error"]
