"""
Unit tests for rag/orchestrator/handler.py

Run with:
    python -m pytest rag/tests/test_orchestrator.py -v
"""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")
    monkeypatch.setenv("BEDROCK_REGION", "eu-west-1")
    monkeypatch.setenv("RETRIEVAL_LAMBDA_ARN", "arn:aws:lambda:eu-west-1:123456789012:function:retrieve")
    monkeypatch.setenv("MAX_TOKENS", "512")
    monkeypatch.setenv("TOP_K", "3")
    monkeypatch.setenv("PROMPT_MODE", "rag")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")


def _make_retrieval_response(chunks: list[str]) -> dict:
    results = [{"text": c, "metadata": {}, "score": 0.9} for c in chunks]
    return {
        "Payload": BytesIO(
            json.dumps({"statusCode": 200, "body": {"results": results}}).encode()
        )
    }


def _make_bedrock_inference_response(output: str) -> dict:
    body_bytes = json.dumps({
        "content": [{"type": "text", "text": output}],
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }).encode()
    mock_body = MagicMock()
    mock_body.read.return_value = body_bytes
    return {"body": mock_body}


class TestValidateEvent:
    def test_valid_event(self):
        import handler
        q, f, k = handler._validate_event({"query": "test?", "filters": {}, "top_k": 3})
        assert q == "test?"
        assert f == {}
        assert k == 3

    def test_missing_query_raises(self):
        import handler
        with pytest.raises(ValueError, match="non-empty"):
            handler._validate_event({})

    def test_invalid_top_k_raises(self):
        import handler
        with pytest.raises(ValueError, match="top_k"):
            handler._validate_event({"query": "q", "top_k": 0})


class TestInvokeRetrieval:
    def test_successful_retrieval(self):
        import handler
        mock_resp = _make_retrieval_response(["chunk one", "chunk two"])
        with patch.object(handler._lambda_client, "invoke", return_value=mock_resp):
            results, latency = handler._invoke_retrieval("test query", {}, 3)
        assert len(results) == 2
        assert results[0]["text"] == "chunk one"
        assert latency >= 0

    def test_retrieval_error_raises(self):
        import handler
        error_resp = {
            "Payload": BytesIO(
                json.dumps({"statusCode": 502, "body": {"error": "OS error"}}).encode()
            )
        }
        with patch.object(handler._lambda_client, "invoke", return_value=error_resp):
            with pytest.raises(RuntimeError, match="Retrieval Lambda returned status"):
                handler._invoke_retrieval("test", {}, 3)


class TestLambdaHandler:
    def test_successful_rag_pipeline(self):
        import handler

        retrieval_mock = _make_retrieval_response(["Context chunk about policy."])
        bedrock_mock = _make_bedrock_inference_response("The policy states X.")

        with (
            patch.object(handler._lambda_client, "invoke", return_value=retrieval_mock),
            patch.object(handler._bedrock_client, "invoke_model", return_value=bedrock_mock),
        ):
            result = handler.lambda_handler({"query": "What is the policy?"}, None)

        assert result["statusCode"] == 200
        body = result["body"]
        assert body["output"] == "The policy states X."
        assert body["usage"]["input_tokens"] == 100
        assert body["usage"]["output_tokens"] == 50
        assert body["retrieval"]["chunks_used"] == 1
        assert "total" in body["latency_ms"]
        assert "estimated_cost_usd" in body["usage"]

    def test_missing_query_returns_400(self):
        import handler
        result = handler.lambda_handler({}, None)
        assert result["statusCode"] == 400

    def test_retrieval_failure_returns_502(self):
        import handler
        error_resp = {
            "Payload": BytesIO(
                json.dumps({"statusCode": 500, "body": {"error": "fail"}}).encode()
            )
        }
        with patch.object(handler._lambda_client, "invoke", return_value=error_resp):
            result = handler.lambda_handler({"query": "test"}, None)
        assert result["statusCode"] == 502

    def test_bedrock_throttle_returns_429(self):
        import handler
        from botocore.exceptions import ClientError

        retrieval_mock = _make_retrieval_response(["context"])
        throttle_error = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Throttled"}},
            "InvokeModel",
        )

        with (
            patch.object(handler._lambda_client, "invoke", return_value=retrieval_mock),
            patch.object(handler._bedrock_client, "invoke_model", side_effect=throttle_error),
        ):
            result = handler.lambda_handler({"query": "test"}, None)

        assert result["statusCode"] == 429

    def test_unexpected_error_returns_500(self):
        import handler
        with patch.object(
            handler._lambda_client, "invoke", side_effect=Exception("boom")
        ):
            result = handler.lambda_handler({"query": "test"}, None)
        assert result["statusCode"] == 500

    def test_empty_retrieval_still_calls_bedrock(self):
        """Even with no context chunks, the pipeline should proceed."""
        import handler

        retrieval_mock = _make_retrieval_response([])
        bedrock_mock = _make_bedrock_inference_response("I don't have enough information.")

        with (
            patch.object(handler._lambda_client, "invoke", return_value=retrieval_mock),
            patch.object(handler._bedrock_client, "invoke_model", return_value=bedrock_mock),
        ):
            result = handler.lambda_handler({"query": "What is unknown topic?"}, None)

        assert result["statusCode"] == 200
        assert result["body"]["retrieval"]["chunks_used"] == 0
