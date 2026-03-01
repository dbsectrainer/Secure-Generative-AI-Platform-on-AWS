"""
Unit tests for rag/retrieval/handler.py

Run with:
    python -m pytest rag/tests/test_retrieval.py -v
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
    monkeypatch.setenv("TOP_K", "5")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")


def _make_bedrock_embed_response(vector: list[float]) -> dict:
    body_bytes = json.dumps({"embedding": vector}).encode()
    mock_body = MagicMock()
    mock_body.read.return_value = body_bytes
    return {"body": mock_body}


class TestValidateEvent:
    def test_valid_event(self):
        import handler
        query, filters, top_k = handler._validate_event(
            {"query": "what is policy?", "filters": {"doc": "p.txt"}, "top_k": 3}
        )
        assert query == "what is policy?"
        assert filters == {"doc": "p.txt"}
        assert top_k == 3

    def test_missing_query_raises(self):
        import handler
        with pytest.raises(ValueError, match="non-empty"):
            handler._validate_event({})

    def test_empty_query_raises(self):
        import handler
        with pytest.raises(ValueError, match="non-empty"):
            handler._validate_event({"query": "  "})

    def test_query_too_long_raises(self):
        import handler
        with pytest.raises(ValueError, match="exceeds maximum"):
            handler._validate_event({"query": "q" * 8_001})

    def test_top_k_too_large_raises(self):
        import handler
        with pytest.raises(ValueError, match="top_k"):
            handler._validate_event({"query": "q", "top_k": 101})

    def test_top_k_zero_raises(self):
        import handler
        with pytest.raises(ValueError, match="top_k"):
            handler._validate_event({"query": "q", "top_k": 0})

    def test_invalid_filters_type_is_replaced(self):
        import handler
        _, filters, _ = handler._validate_event({"query": "q", "filters": "bad"})
        assert filters == {}


class TestBuildSearchQuery:
    def test_no_filters(self):
        import handler
        query = handler._build_search_query([0.1, 0.2], {}, 5)
        assert "filter" not in query["query"]["knn"]["embedding"]

    def test_with_filters(self):
        import handler
        query = handler._build_search_query([0.1, 0.2], {"doc": "file.txt"}, 5)
        assert "filter" in query["query"]["knn"]["embedding"]
        must = query["query"]["knn"]["embedding"]["filter"]["bool"]["must"]
        assert any(t.get("term", {}).get("metadata.doc") == "file.txt" for t in must)

    def test_top_k_in_query(self):
        import handler
        query = handler._build_search_query([0.1], {}, 7)
        assert query["size"] == 7
        assert query["query"]["knn"]["embedding"]["k"] == 7


class TestLambdaHandler:
    def test_successful_retrieval(self):
        import handler

        vector = [0.1] * 1024
        mock_embed_resp = _make_bedrock_embed_response(vector)

        opensearch_hits = {
            "hits": {
                "hits": [
                    {
                        "_score": 0.95,
                        "_source": {
                            "text": "Relevant chunk",
                            "metadata": {"document_key": "raw/doc.txt", "chunk_index": 0},
                        },
                    }
                ]
            }
        }

        with (
            patch.object(handler._bedrock_client, "invoke_model", return_value=mock_embed_resp),
            patch.object(handler, "_search_opensearch", return_value=[
                {"text": "Relevant chunk", "metadata": {}, "score": 0.95}
            ]),
        ):
            result = handler.lambda_handler({"query": "test query"}, None)

        assert result["statusCode"] == 200
        assert len(result["body"]["results"]) == 1
        assert result["body"]["results"][0]["text"] == "Relevant chunk"

    def test_missing_query_returns_400(self):
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
            result = handler.lambda_handler({"query": "test"}, None)
        assert result["statusCode"] == 429

    def test_opensearch_error_returns_502(self):
        import handler

        vector = [0.1] * 1024
        mock_embed_resp = _make_bedrock_embed_response(vector)

        with (
            patch.object(handler._bedrock_client, "invoke_model", return_value=mock_embed_resp),
            patch.object(
                handler, "_search_opensearch", side_effect=RuntimeError("OS down")
            ),
        ):
            result = handler.lambda_handler({"query": "test"}, None)

        assert result["statusCode"] == 502

    def test_unexpected_error_returns_500(self):
        import handler
        with patch.object(
            handler._bedrock_client, "invoke_model", side_effect=Exception("boom")
        ):
            result = handler.lambda_handler({"query": "test"}, None)
        assert result["statusCode"] == 500
