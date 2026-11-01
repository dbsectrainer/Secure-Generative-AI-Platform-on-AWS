"""
Embedding Generation Lambda Function

Generates a vector embedding for a text chunk using Amazon Bedrock
(Titan Text Embeddings v2) and stores the vector in an OpenSearch Serverless
collection via the _bulk API.

Environment variables:
    BEDROCK_EMBEDDING_MODEL_ID  – Bedrock embedding model ID
                                  (default: amazon.titan-embed-text-v2:0)
    BEDROCK_REGION              – AWS region for Bedrock (default: AWS_REGION)
    OPENSEARCH_ENDPOINT         – HTTPS endpoint of the OpenSearch Serverless
                                  collection (no trailing slash)
    OPENSEARCH_INDEX            – OpenSearch index name (default: rag-documents)
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

# Maximum text length accepted by Titan Embeddings v2 (8192 tokens ≈ 32 768 chars)
_MAX_TEXT_LENGTH = 32_768


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


def _validate_event(event: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return (text, metadata) extracted from the event.

    Raises:
        ValueError: if the text field is missing, empty, or too long.
    """
    text = event.get("text", "").strip()
    if not text:
        raise ValueError("Event must include a non-empty 'text' field.")
    if len(text) > _MAX_TEXT_LENGTH:
        raise ValueError(
            f"Text length {len(text)} exceeds maximum of {_MAX_TEXT_LENGTH} characters."
        )
    metadata = event.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    return text, metadata


# ── Embedding generation ──────────────────────────────────────────────────────

def _generate_embedding(text: str) -> list[float]:
    """Call Bedrock Titan Embeddings v2 and return the embedding vector."""
    body = json.dumps({"inputText": text})

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
        "Embedding generated",
        extra={
            "model_id": BEDROCK_EMBEDDING_MODEL_ID,
            "dimensions": len(embedding),
            "latency_ms": round(latency_ms, 1),
        },
    )
    return embedding


# ── OpenSearch indexing ───────────────────────────────────────────────────────

def _sigv4_headers(method: str, url: str, body: bytes, region: str) -> dict[str, str]:
    """Return SigV4-signed headers for an OpenSearch Serverless request."""
    credentials: Credentials = _session.get_credentials().get_frozen_credentials()
    request = AWSRequest(method=method, url=url, data=body)
    SigV4Auth(credentials, "aoss", region).add_auth(request)
    return dict(request.headers)


def _index_document(
    embedding: list[float],
    text: str,
    metadata: dict[str, Any],
) -> None:
    """Index the embedding and its source text into OpenSearch Serverless."""
    doc = {
        "embedding": embedding,
        "text": text,
        "metadata": metadata,
    }
    url = f"{OPENSEARCH_ENDPOINT}/{OPENSEARCH_INDEX}/_doc"
    body = json.dumps(doc).encode("utf-8")
    headers = _sigv4_headers("POST", url, body, BEDROCK_REGION)
    headers["Content-Type"] = "application/json"

    req = urllib_request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib_request.urlopen(req, timeout=10) as resp:  # noqa: S310  # nosec B310
            status = resp.status
            response_body = resp.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        raise RuntimeError(
            f"OpenSearch indexing failed with HTTP {exc.code}: {exc.read().decode()}"
        ) from exc

    if status not in (200, 201):
        raise RuntimeError(f"Unexpected OpenSearch status {status}: {response_body}")

    logger.info(
        "Document indexed in OpenSearch",
        extra={"index": OPENSEARCH_INDEX, "status": status},
    )


# ── Lambda handler ────────────────────────────────────────────────────────────

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:  # noqa: ARG001
    """AWS Lambda entry point.

    Expected event structure::

        {
            "text": "The text chunk to embed",
            "metadata": {
                "document_key": "raw/my-doc.txt",
                "chunk_index": 0
            }
        }

    Returns::

        {
            "statusCode": 200,
            "body": {
                "indexed": true,
                "dimensions": 1024,
                "metadata": {...}
            }
        }
    """
    logger.debug("Received embedding event")

    is_proxy = _is_api_gateway_event(event)
    try:
        require_auth(event)
    except AuthError as exc:
        return _build_response(exc.status_code, {"error": exc.message}, is_proxy)

    try:
        payload = _parse_event(event)
        text, metadata = _validate_event(payload)
        text = redact_pii(text)
        embedding = _generate_embedding(text)
        _index_document(embedding, text, metadata)

        return _build_response(
            200,
            {
                "indexed": True,
                "dimensions": len(embedding),
                "metadata": metadata,
            },
            is_proxy,
        )

    except ValueError as exc:
        logger.warning("Invalid embedding request: %s", exc)
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
        # Log details for operators, but never return endpoint/response internals
        # to the API caller.
        logger.error("OpenSearch indexing error: %s", exc)
        return _build_response(
            502,
            {"error": "Vector index service error. Please retry later."},
            is_proxy,
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error: %s", exc)
        return _build_response(500, {"error": "Internal server error."}, is_proxy)
