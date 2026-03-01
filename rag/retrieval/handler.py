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

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.config import Config
from botocore.credentials import Credentials
from botocore.exceptions import ClientError

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
OPENSEARCH_ENDPOINT = os.environ["OPENSEARCH_ENDPOINT"].rstrip("/")
OPENSEARCH_INDEX = os.environ.get("OPENSEARCH_INDEX", "rag-documents")
TOP_K = int(os.environ.get("TOP_K", "5"))

_bedrock_config = Config(
    region_name=BEDROCK_REGION,
    retries={"max_attempts": 3, "mode": "adaptive"},
    connect_timeout=5,
    read_timeout=30,
)
_bedrock_client = boto3.client("bedrock-runtime", config=_bedrock_config)
_session = boto3.session.Session()

_MAX_QUERY_LENGTH = 8_000


# ── Input validation ──────────────────────────────────────────────────────────

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

    top_k = int(event.get("top_k", TOP_K))
    if top_k < 1 or top_k > 100:
        raise ValueError("top_k must be between 1 and 100.")

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
        with urllib_request.urlopen(req, timeout=10) as resp:  # noqa: S310
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

    try:
        query, filters, top_k = _validate_event(event)
        embedding = _embed_query(query)
        results = _search_opensearch(embedding, filters, top_k)

        return {
            "statusCode": 200,
            "body": {
                "results": results,
                "query": query,
                "top_k": top_k,
            },
        }

    except ValueError as exc:
        logger.warning("Invalid retrieval request: %s", exc)
        return {"statusCode": 400, "body": {"error": str(exc)}}

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        logger.error("Bedrock ClientError: %s – %s", error_code, exc)
        if error_code in ("ThrottlingException", "ServiceUnavailableException"):
            return {
                "statusCode": 429,
                "body": {"error": "Service temporarily unavailable. Please retry."},
            }
        return {"statusCode": 502, "body": {"error": "Upstream Bedrock error."}}

    except RuntimeError as exc:
        logger.error("OpenSearch retrieval error: %s", exc)
        return {"statusCode": 502, "body": {"error": str(exc)}}

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error: %s", exc)
        return {"statusCode": 500, "body": {"error": "Internal server error."}}
