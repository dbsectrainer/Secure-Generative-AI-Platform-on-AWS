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

_bedrock_config = Config(
    region_name=BEDROCK_REGION,
    retries={"max_attempts": 3, "mode": "adaptive"},
    connect_timeout=5,
    read_timeout=30,
)
_bedrock_client = boto3.client("bedrock-runtime", config=_bedrock_config)
_session = boto3.session.Session()

# Maximum text length accepted by Titan Embeddings v2 (8192 tokens ≈ 32 768 chars)
_MAX_TEXT_LENGTH = 32_768


# ── Input validation ──────────────────────────────────────────────────────────

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
        with urllib_request.urlopen(req, timeout=10) as resp:  # noqa: S310
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

    try:
        text, metadata = _validate_event(event)
        embedding = _generate_embedding(text)
        _index_document(embedding, text, metadata)

        return {
            "statusCode": 200,
            "body": {
                "indexed": True,
                "dimensions": len(embedding),
                "metadata": metadata,
            },
        }

    except ValueError as exc:
        logger.warning("Invalid embedding request: %s", exc)
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
        logger.error("OpenSearch indexing error: %s", exc)
        return {"statusCode": 502, "body": {"error": str(exc)}}

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error: %s", exc)
        return {"statusCode": 500, "body": {"error": "Internal server error."}}
