"""
Vector Retrieval Lambda Function

Accepts a natural-language query, generates an embedding via Bedrock, and
executes a k-NN search against OpenSearch Serverless with optional metadata
filtering to return the most semantically relevant document chunks.

Environment variables:
    BEDROCK_EMBEDDING_MODEL_ID  – Bedrock embedding model ID
                                  (default: amazon.titan-embed-text-v2:0)
    BEDROCK_REGION              – AWS region for Bedrock (default: AWS_REGION)
    OPENSEARCH_ENDPOINT         – HTTPS endpoint of the OpenSearch Serverless
                                  collection (no trailing slash)
    OPENSEARCH_INDEX            – OpenSearch index name (default: rag-documents)
    TOP_K                       – Number of results to return (default: 5)
    LOG_LEVEL                   – Python logging level
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any
from urllib.parse import urlparse

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.config import Config
from botocore.credentials import Credentials
from botocore.exceptions import ClientError

from auth import AuthError, require_auth
from pii import PiiError, redact_pii

try:
    import urllib.request as urllib_request
    import urllib.error as urllib_error
except ImportError:  # pragma: no cover
    pass

# ── Logging ───────────────────────────────────────────────────────────────────

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=LOG_LEVEL,
)
logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

BEDROCK_EMBEDDING_MODEL_ID = os.environ.get(
    "BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"
)
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", os.environ.get("AWS_REGION", "eu-west-1"))
def _validated_endpoint(value: str) -> str:
    """Require an absolute HTTP(S) endpoint; avoid file/custom URL schemes."""
    parsed = urlparse(value.rstrip("/"))
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("OPENSEARCH_ENDPOINT must be an absolute http(s) URL")
    return value.rstrip("/")


OPENSEARCH_ENDPOINT = _validated_endpoint(os.environ["OPENSEARCH_ENDPOINT"])
OPENSEARCH_INDEX = os.environ.get("OPENSEARCH_INDEX", "rag-documents")
TOP_K = int(os.environ.get("TOP_K", "5"))

# Optional endpoint override for local end-to-end tests (unset in production).
BEDROCK_ENDPOINT_URL = os.environ.get("BEDROCK_ENDPOINT_URL") or None

_bedrock_config = Config(
    region_name=BEDROCK_REGION,
    retries={"max_attempts": 3, "mode": "adaptive"},
    connect_timeout=5,
    read_timeout=30,
)
_bedrock_client = boto3.client(
    "bedrock-runtime",
    config=_bedrock_config,
    **({"endpoint_url": BEDROCK_ENDPOINT_URL} if BEDROCK_ENDPOINT_URL else {}),
)
_session = boto3.session.Session()

_MAX_QUERY_LENGTH = 8_000


# ── Input validation ──────────────────────────────────────────────────────────

def _is_api_gateway_event(event: Any) -> bool:
    """Return True when *event* is an API Gateway Lambda proxy event."""
    return isinstance(event, dict) and "httpMethod" in event and "body" in event


def _parse_event(event: Any) -> dict[str, Any]:
    """Return the payload from a direct invocation or an API Gateway event."""
    if not isinstance(event, dict):
        raise ValueError("Request payload must be a JSON object.")
    if not _is_api_gateway_event(event):
        return event

    raw_body = event.get("body")
    if raw_body in (None, ""):
        raise ValueError("Request body is required.")
    if isinstance(raw_body, dict):
        return raw_body
    if not isinstance(raw_body, str):
        raise ValueError("Request body must be a JSON object.")
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ValueError("Request body must contain valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Request body must contain a JSON object.")
    return payload


def _build_response(
    status_code: int, body: dict[str, Any], proxy: bool
) -> dict[str, Any]:
    """Build a direct-invocation or API Gateway proxy response."""
    if proxy:
        return {
            "statusCode": status_code,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body),
        }
    return {"statusCode": status_code, "body": body}


def _parse_top_k(raw_value: Any) -> int:
    """Validate and coerce a caller-supplied ``top_k`` value."""
    if isinstance(raw_value, bool) or not isinstance(raw_value, (int, str)):
        raise ValueError("top_k must be an integer between 1 and 100.")
    try:
        top_k = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("top_k must be an integer between 1 and 100.") from exc
    if top_k < 1 or top_k > 100:
        raise ValueError("top_k must be between 1 and 100.")
    return top_k


def _validate_event(event: dict[str, Any]) -> tuple[str, dict[str, Any], int]:
    """Return (query, filter_metadata, top_k) from the event.

    Raises:
        ValueError: if the query is missing, empty, or too long.
    """
    query = event.get("query", "").strip()
    if not query:
        raise ValueError("Event must include a non-empty 'query' field.")
    if len(query) > _MAX_QUERY_LENGTH:
        raise ValueError(
            f"Query length {len(query)} exceeds maximum of {_MAX_QUERY_LENGTH} characters."
        )

    filters = event.get("filters", {})
    if not isinstance(filters, dict):
        filters = {}

    top_k = _parse_top_k(event.get("top_k", TOP_K))

    return query, filters, top_k


# ── Embedding generation ──────────────────────────────────────────────────────

def _embed_query(query: str) -> list[float]:
    """Generate an embedding vector for the query string."""
    body = json.dumps({"inputText": query})

    start = time.monotonic()
    response = _bedrock_client.invoke_model(
        modelId=BEDROCK_EMBEDDING_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    latency_ms = (time.monotonic() - start) * 1000

    response_body = json.loads(response["body"].read())
    embedding: list[float] = response_body["embedding"]

    logger.info(
        "Query embedding generated",
        extra={
            "model_id": BEDROCK_EMBEDDING_MODEL_ID,
            "dimensions": len(embedding),
            "latency_ms": round(latency_ms, 1),
        },
    )
    return embedding


# ── OpenSearch search ─────────────────────────────────────────────────────────

def _sigv4_headers(method: str, url: str, body: bytes, region: str) -> dict[str, str]:
    """Return SigV4-signed headers for an OpenSearch Serverless request."""
    credentials: Credentials = _session.get_credentials().get_frozen_credentials()
    request = AWSRequest(method=method, url=url, data=body)
    SigV4Auth(credentials, "aoss", region).add_auth(request)
    return dict(request.headers)


def _build_search_query(
    embedding: list[float],
    filters: dict[str, Any],
    top_k: int,
) -> dict[str, Any]:
    """Construct an OpenSearch k-NN query with optional metadata filters.

    Metadata filters are applied as ``filter`` clauses on the k-NN query so
    that only documents matching all provided key/value pairs are returned.
    This implements the retrieval filtering requirement.
    """
    knn_query: dict[str, Any] = {
        "vector": embedding,
        "k": top_k,
    }

    # Apply metadata filters as a bool filter on the k-NN clause
    if filters:
        filter_terms = [
            {"term": {f"metadata.{k}": v}} for k, v in filters.items()
        ]
        knn_query["filter"] = {
            "bool": {"must": filter_terms}
        }

    return {
        "size": top_k,
        "_source": ["text", "metadata"],
        "query": {
            "knn": {
                "embedding": knn_query
            }
        },
    }


def _search_opensearch(
    embedding: list[float],
    filters: dict[str, Any],
    top_k: int,
) -> list[dict[str, Any]]:
    """Execute the k-NN search and return the top-k hits."""
    url = f"{OPENSEARCH_ENDPOINT}/{OPENSEARCH_INDEX}/_search"
    search_body = _build_search_query(embedding, filters, top_k)
    body_bytes = json.dumps(search_body).encode("utf-8")

    headers = _sigv4_headers("POST", url, body_bytes, BEDROCK_REGION)
    headers["Content-Type"] = "application/json"

    req = urllib_request.Request(url, data=body_bytes, headers=headers, method="POST")

    try:
        start = time.monotonic()
        with urllib_request.urlopen(req, timeout=10) as resp:  # noqa: S310  # nosec B310
            latency_ms = (time.monotonic() - start) * 1000
            response_body = json.loads(resp.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        raise RuntimeError(
            f"OpenSearch search failed with HTTP {exc.code}: {exc.read().decode()}"
        ) from exc

    hits = response_body.get("hits", {}).get("hits", [])
    logger.info(
        "OpenSearch search complete",
        extra={
            "hits": len(hits),
            "latency_ms": round(latency_ms, 1),
            "filters_applied": bool(filters),
        },
    )

    return [
        {
            "text": hit.get("_source", {}).get("text", ""),
            "metadata": hit.get("_source", {}).get("metadata", {}),
            "score": hit.get("_score", 0.0),
        }
        for hit in hits
    ]


# ── Lambda handler ────────────────────────────────────────────────────────────

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:  # noqa: ARG001
    """AWS Lambda entry point.

    Expected event structure::

        {
            "query": "What is the refund policy?",
            "filters": {
                "document_key": "raw/policy.txt"
            },
            "top_k": 3
        }

    Returns::

        {
            "statusCode": 200,
            "body": {
                "results": [
                    {
                        "text": "...",
                        "metadata": {"document_key": "...", "chunk_index": 0},
                        "score": 0.92
                    },
                    ...
                ],
                "query": "...",
                "top_k": 3
            }
        }
    """
    logger.debug("Received retrieval event")

    is_proxy = _is_api_gateway_event(event)
    try:
        require_auth(event)
    except AuthError as exc:
        return _build_response(exc.status_code, {"error": exc.message}, is_proxy)

    try:
        payload = _parse_event(event)
        query, filters, top_k = _validate_event(payload)
        query = redact_pii(query)
        embedding = _embed_query(query)
        results = _search_opensearch(embedding, filters, top_k)

        return _build_response(
            200,
            {
                "results": results,
                "query": query,
                "top_k": top_k,
            },
            is_proxy,
        )

    except ValueError as exc:
        logger.warning("Invalid retrieval request: %s", exc)
        return _build_response(400, {"error": str(exc)}, is_proxy)

    except PiiError as exc:
        logger.error("PII redaction failed: %s", exc)
        return _build_response(
            502,
            {"error": "PII redaction failed. Please retry later."},
            is_proxy,
        )

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        logger.error("Bedrock ClientError: %s – %s", error_code, exc)
        if error_code in ("ThrottlingException", "ServiceUnavailableException"):
            return _build_response(
                429,
                {"error": "Service temporarily unavailable. Please retry."},
                is_proxy,
            )
        return _build_response(502, {"error": "Upstream Bedrock error."}, is_proxy)

    except RuntimeError as exc:
        logger.error("OpenSearch retrieval error: %s", exc)
        return _build_response(
            502,
            {"error": "Vector search service error. Please retry later."},
            is_proxy,
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error: %s", exc)
        return _build_response(500, {"error": "Internal server error."}, is_proxy)
