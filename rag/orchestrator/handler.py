"""
RAG Orchestrator Lambda Function

Coordinates the full RAG pipeline in a single Lambda invocation:
  1. Validate the incoming query.
  2. Invoke the retrieval Lambda to fetch relevant context chunks.
  3. Construct the grounded prompt via PromptBuilder.
  4. Call Amazon Bedrock for inference.
  5. Return the grounded response with token usage and stage latencies.

Environment variables:
    BEDROCK_MODEL_ID     – Bedrock model for inference (Claude Sonnet 5.5)
    BEDROCK_REGION       – AWS region for Bedrock (default: AWS_REGION)
    RETRIEVAL_LAMBDA_ARN – ARN of the retrieval Lambda
    MAX_TOKENS           – Maximum response tokens (default: 2048)
    TOP_K                – Retrieval top-k (default: 5)
    PROMPT_MODE          – PromptBuilder mode: rag | citation | summarisation
    LOG_LEVEL            – Python logging level
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Allow importing prompt_builder from the genai package when deployed as a
# Lambda layer or when running tests with sys.path manipulation.
_GENAI_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "genai", "prompt_builder")
if _GENAI_PATH not in sys.path:
    sys.path.insert(0, _GENAI_PATH)

from builder import PromptBuilder  # noqa: E402

# ── Logging ───────────────────────────────────────────────────────────────────

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=LOG_LEVEL,
)
logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

BEDROCK_MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", os.environ.get("AWS_REGION", "eu-west-1"))
RETRIEVAL_LAMBDA_ARN = os.environ["RETRIEVAL_LAMBDA_ARN"]
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "2048"))
TOP_K = int(os.environ.get("TOP_K", "5"))
PROMPT_MODE = os.environ.get("PROMPT_MODE", "rag")

# Optional Bedrock Guardrail. When set, content filtering and the PII
# anonymization/blocking policy configured on the guardrail are applied by
# Bedrock as part of InvokeModel. Unset in purely local runs.
BEDROCK_GUARDRAIL_ID = os.environ.get("BEDROCK_GUARDRAIL_ID") or None
BEDROCK_GUARDRAIL_VERSION = os.environ.get("BEDROCK_GUARDRAIL_VERSION") or "DRAFT"

# Optional endpoint overrides for local end-to-end tests (unset in production).
BEDROCK_ENDPOINT_URL = os.environ.get("BEDROCK_ENDPOINT_URL") or None
LAMBDA_ENDPOINT_URL = os.environ.get("LAMBDA_ENDPOINT_URL") or None

_bedrock_config = Config(
    region_name=BEDROCK_REGION,
    retries={"max_attempts": 3, "mode": "adaptive"},
    connect_timeout=5,
    read_timeout=60,
)
_bedrock_client = boto3.client(
    "bedrock-runtime",
    config=_bedrock_config,
    **({"endpoint_url": BEDROCK_ENDPOINT_URL} if BEDROCK_ENDPOINT_URL else {}),
)
_lambda_config = Config(
    region_name=BEDROCK_REGION,
    retries={"max_attempts": 3, "mode": "adaptive"},
    connect_timeout=5,
    read_timeout=60,
)
_lambda_client = boto3.client(
    "lambda",
    config=_lambda_config,
    **({"endpoint_url": LAMBDA_ENDPOINT_URL} if LAMBDA_ENDPOINT_URL else {}),
)

_MAX_QUERY_LENGTH = 8_000
_prompt_builder = PromptBuilder(mode=PROMPT_MODE, use_restricted=True)


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
    """Return (query, filters, top_k) from the incoming event.

    Raises:
        ValueError: for invalid or missing inputs.
    """
    query = event.get("query", "").strip()
    if not query:
        raise ValueError("Request must include a non-empty 'query' field.")
    if len(query) > _MAX_QUERY_LENGTH:
        raise ValueError(
            f"Query length {len(query)} exceeds maximum of {_MAX_QUERY_LENGTH} characters."
        )
    filters = event.get("filters", {})
    if not isinstance(filters, dict):
        filters = {}
    top_k = _parse_top_k(event.get("top_k", TOP_K))
    return query, filters, top_k


# ── Retrieval ─────────────────────────────────────────────────────────────────

def _invoke_retrieval(
    query: str, filters: dict[str, Any], top_k: int
) -> tuple[list[dict[str, Any]], float]:
    """Synchronously invoke the retrieval Lambda and return (results, latency_ms)."""
    payload = {"query": query, "filters": filters, "top_k": top_k}

    start = time.monotonic()
    response = _lambda_client.invoke(
        FunctionName=RETRIEVAL_LAMBDA_ARN,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload),
    )
    latency_ms = (time.monotonic() - start) * 1000

    response_payload = json.loads(response["Payload"].read())
    status_code = response_payload.get("statusCode", 500)

    if status_code != 200:
        body = response_payload.get("body", {})
        raise RuntimeError(
            f"Retrieval Lambda returned status {status_code}: "
            f"{body.get('error', 'unknown error')}"
        )

    results: list[dict[str, Any]] = response_payload.get("body", {}).get("results", [])
    logger.info(
        "Retrieval complete",
        extra={"results_count": len(results), "latency_ms": round(latency_ms, 1)},
    )
    return results, latency_ms


# ── Bedrock inference ─────────────────────────────────────────────────────────

def _invoke_bedrock(payload: dict[str, Any]) -> tuple[str, dict[str, int], float]:
    """Call Bedrock with *payload* and return (output_text, usage, latency_ms)."""
    start = time.monotonic()
    invoke_kwargs: dict[str, Any] = {
        "modelId": BEDROCK_MODEL_ID,
        "contentType": "application/json",
        "accept": "application/json",
        "body": json.dumps(payload),
    }
    if BEDROCK_GUARDRAIL_ID:
        invoke_kwargs["guardrailIdentifier"] = BEDROCK_GUARDRAIL_ID
        invoke_kwargs["guardrailVersion"] = BEDROCK_GUARDRAIL_VERSION

    response = _bedrock_client.invoke_model(**invoke_kwargs)
    latency_ms = (time.monotonic() - start) * 1000

    response_body = json.loads(response["body"].read())

    output_text: str = response_body["content"][0]["text"]
    usage = {
        "input_tokens": response_body.get("usage", {}).get("input_tokens", 0),
        "output_tokens": response_body.get("usage", {}).get("output_tokens", 0),
    }

    logger.info(
        "Bedrock inference complete",
        extra={
            "model_id": BEDROCK_MODEL_ID,
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "latency_ms": round(latency_ms, 1),
        },
    )
    return output_text, usage, latency_ms


# ── Lambda handler ────────────────────────────────────────────────────────────

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:  # noqa: ARG001
    """AWS Lambda entry point for the RAG orchestrator.

    Expected event structure::

        {
            "query":   "What is our data retention policy?",
            "filters": {"document_key": "raw/policy.txt"},
            "top_k":   5
        }

    Returns::

        {
            "statusCode": 200,
            "body": {
                "output":  "<grounded model response>",
                "model_id": "...",
                "usage": {
                    "input_tokens": N,
                    "output_tokens": N,
                    "estimated_cost_usd": 0.000NNN
                },
                "retrieval": {
                    "chunks_used": N,
                    "latency_ms": NNN
                },
                "latency_ms": {
                    "retrieval": NNN,
                    "prompt_construction": NNN,
                    "bedrock_inference": NNN,
                    "total": NNN
                }
            }
        }
    """
    pipeline_start = time.monotonic()
    is_proxy = _is_api_gateway_event(event)
    logger.debug("RAG orchestrator received event")

    try:
        payload = _parse_event(event)
        query, filters, top_k = _validate_event(payload)

        # ── Stage 1: Retrieval ─────────────────────────────────────────────
        retrieval_results, retrieval_latency = _invoke_retrieval(query, filters, top_k)
        context_chunks = [r["text"] for r in retrieval_results if r.get("text")]

        # ── Stage 2: Prompt construction ───────────────────────────────────
        prompt_start = time.monotonic()
        built = _prompt_builder.build(
            query=query,
            context_chunks=context_chunks,
            max_tokens=MAX_TOKENS,
        )
        prompt_latency = (time.monotonic() - prompt_start) * 1000
        payload = built["payload"]
        token_estimate = built["token_estimate"]

        # ── Stage 3: Bedrock inference ─────────────────────────────────────
        output_text, usage, bedrock_latency = _invoke_bedrock(payload)

        total_latency = (time.monotonic() - pipeline_start) * 1000

        # Cost estimation: Claude Sonnet 5.5 pricing (USD per 1K tokens)
        # Input: $0.002 / 1K tokens, Output: $0.010 / 1K tokens
        # These are approximate values; use AWS pricing calculator for exact costs.
        estimated_cost = (
            usage["input_tokens"] * 0.002 / 1000
            + usage["output_tokens"] * 0.010 / 1000
        )

        return _build_response(
            200,
            {
                "output": output_text,
                "model_id": BEDROCK_MODEL_ID,
                "usage": {
                    "input_tokens": usage["input_tokens"],
                    "output_tokens": usage["output_tokens"],
                    "prompt_token_estimate": token_estimate["prompt_tokens"],
                    "estimated_cost_usd": round(estimated_cost, 6),
                },
                "retrieval": {
                    "chunks_used": len(context_chunks),
                    "latency_ms": round(retrieval_latency, 1),
                },
                "latency_ms": {
                    "retrieval": round(retrieval_latency, 1),
                    "prompt_construction": round(prompt_latency, 1),
                    "bedrock_inference": round(bedrock_latency, 1),
                    "total": round(total_latency, 1),
                },
            },
            is_proxy,
        )

    except ValueError as exc:
        logger.warning("Invalid RAG request: %s", exc)
        return _build_response(400, {"error": str(exc)}, is_proxy)

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
        logger.error("Pipeline stage error: %s", exc)
        return _build_response(
            502,
            {"error": "A downstream pipeline stage failed. Please retry later."},
            is_proxy,
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected orchestrator error: %s", exc)
        return _build_response(500, {"error": "Internal server error."}, is_proxy)
