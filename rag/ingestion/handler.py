"""
Document Ingestion Lambda Function

Triggered by S3 ObjectCreated events. Reads the uploaded document, splits it
into overlapping chunks, and invokes the embedding Lambda for each chunk to
store vectors in OpenSearch Serverless.

Environment variables:
    DOCUMENT_BUCKET      – S3 bucket containing raw source documents
    EMBEDDING_LAMBDA_ARN – ARN of the embedding Lambda to invoke per chunk
    CHUNK_SIZE           – Target character count per chunk (default: 1000)
    CHUNK_OVERLAP        – Overlap between consecutive chunks (default: 200)
    LOG_LEVEL            – Python logging level (DEBUG / INFO / WARNING / ERROR)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# ── Logging ───────────────────────────────────────────────────────────────────

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=LOG_LEVEL,
)
logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

DOCUMENT_BUCKET = os.environ["DOCUMENT_BUCKET"]
EMBEDDING_LAMBDA_ARN = os.environ["EMBEDDING_LAMBDA_ARN"]
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "200"))
AWS_REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "eu-west-1"))

_lambda_config = Config(
    region_name=AWS_REGION,
    retries={"max_attempts": 3, "mode": "adaptive"},
    connect_timeout=5,
    read_timeout=60,
)

_s3_client = boto3.client("s3", region_name=AWS_REGION)
_lambda_client = boto3.client("lambda", config=_lambda_config)

# Maximum document size (5 MB) to guard against runaway processing
_MAX_DOCUMENT_BYTES = 5 * 1024 * 1024


# ── Chunking ──────────────────────────────────────────────────────────────────

def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split *text* into overlapping chunks of approximately *chunk_size* chars.

    Chunks are split on whitespace boundaries where possible so that words are
    not cut in half.

    Args:
        text:       The source text to chunk.
        chunk_size: Target size in characters for each chunk.
        overlap:    Number of characters from the previous chunk to repeat at
                    the start of the next chunk.

    Returns:
        List of text chunks; always contains at least one element.
    """
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        # Try to break on a whitespace boundary to avoid splitting words
        if end < text_len:
            boundary = text.rfind(" ", start, end)
            if boundary > start:
                end = boundary

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break

        start = end - overlap

    return chunks


# ── S3 helpers ────────────────────────────────────────────────────────────────

def _read_s3_object(bucket: str, key: str) -> str:
    """Fetch an S3 object and return its contents as a UTF-8 string."""
    response = _s3_client.get_object(Bucket=bucket, Key=key)
    content_length = response.get("ContentLength", 0)
    if content_length > _MAX_DOCUMENT_BYTES:
        raise ValueError(
            f"Document {key!r} is {content_length} bytes, exceeding the "
            f"{_MAX_DOCUMENT_BYTES}-byte limit."
        )
    return response["Body"].read().decode("utf-8", errors="replace")


# ── Embedding invocation ──────────────────────────────────────────────────────

def _invoke_embedding(chunk: str, document_key: str, chunk_index: int) -> None:
    """Asynchronously invoke the embedding Lambda for one text chunk."""
    payload = {
        "text": chunk,
        "metadata": {
            "document_key": document_key,
            "chunk_index": chunk_index,
        },
    }
    _lambda_client.invoke(
        FunctionName=EMBEDDING_LAMBDA_ARN,
        InvocationType="Event",  # asynchronous
        Payload=json.dumps(payload),
    )
    logger.debug(
        "Dispatched embedding request",
        extra={"document_key": document_key, "chunk_index": chunk_index},
    )


# ── Lambda handler ────────────────────────────────────────────────────────────

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:  # noqa: ARG001
    """AWS Lambda entry point – S3 ObjectCreated trigger.

    Processes each S3 record in the event, chunks the document text, and fans
    out asynchronous invocations to the embedding Lambda.

    Returns a summary dict with per-object results.
    """
    records = event.get("Records", [])
    if not records:
        logger.warning("Received event with no Records")
        return {"statusCode": 200, "body": {"processed": 0, "errors": []}}

    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for record in records:
        bucket = record.get("s3", {}).get("bucket", {}).get("name", "")
        key = record.get("s3", {}).get("object", {}).get("key", "")

        if not bucket or not key:
            logger.warning("Skipping malformed S3 record: %s", record)
            continue

        logger.info("Processing document", extra={"bucket": bucket, "key": key})

        try:
            text = _read_s3_object(bucket, key)
            chunks = _chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)

            logger.info(
                "Document chunked",
                extra={"key": key, "chunk_count": len(chunks)},
            )

            for idx, chunk in enumerate(chunks):
                _invoke_embedding(chunk, key, idx)

            results.append({"key": key, "chunks_dispatched": len(chunks)})

        except (ValueError, ClientError) as exc:
            logger.error("Failed to process %r: %s", key, exc)
            errors.append({"key": key, "error": str(exc)})

    return {
        "statusCode": 200 if not errors else 207,
        "body": {
            "processed": len(results),
            "errors": errors,
            "results": results,
        },
    }
