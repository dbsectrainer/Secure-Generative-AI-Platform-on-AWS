"""
Bedrock Orchestrator Lambda Function

Invokes an Amazon Bedrock foundation model from within a private VPC, using
an Interface VPC Endpoint for bedrock-runtime. Supports streaming and
non-streaming invocations.

Environment variables:
    BEDROCK_MODEL_ID      – Bedrock foundation model ID (e.g. anthropic.claude-sonnet-5-5)
    BEDROCK_REGION        – AWS region where Bedrock is available
    DOCUMENT_BUCKET       – S3 bucket name containing RAG source documents
    MAX_TOKENS            – Maximum number of tokens in the model response
    LOG_LEVEL             – Python logging level (DEBUG / INFO / WARNING / ERROR)
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

BEDROCK_MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", os.environ.get("AWS_REGION", "eu-west-1"))
DOCUMENT_BUCKET = os.environ["DOCUMENT_BUCKET"]
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "2048"))

# Optional endpoint override for local end-to-end tests. Production leaves this
# unset so boto3 resolves the regional Bedrock endpoint normally. Deliberately
# not named AWS_ENDPOINT_URL_* — SAM reserves/filters AWS_* variables.
BEDROCK_ENDPOINT_URL = os.environ.get("BEDROCK_ENDPOINT_URL") or None

# Boto3 client is created once at module load (reused across warm invocations).
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


# ── Input validation ──────────────────────────────────────────────────────────

_MAX_PROMPT_LENGTH = 10_000  # characters


def _is_api_gateway_event(event: Any) -> bool:
    """Return True when *event* is an API Gateway Lambda proxy event."""
    return isinstance(event, dict) and "httpMethod" in event and "body" in event


def _parse_event(event: Any) -> dict[str, Any]:
    """Return the request payload from a direct invocation or proxy event.

    Direct Lambda invocations (``sam local invoke``, tests, Lambda-to-Lambda)
    pass the payload at the top level. API Gateway proxy events carry the JSON
    request body in a ``body`` string; without unwrapping it every HTTP request
    is rejected as missing fields.
    """
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
    """Build a direct-invocation or API Gateway proxy response.

    API Gateway requires ``body`` to be a JSON string. Returning a dict causes
    local API Gateway to emit a Python repr (single quotes), which is not valid
    JSON and cannot be parsed by HTTP clients.
    """
    if proxy:
        return {
            "statusCode": status_code,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body),
        }
    return {"statusCode": status_code, "body": body}


def _validate_event(event: dict[str, Any]) -> str:
    """Extract and validate the prompt from the incoming event.

    Raises:
        ValueError: if the prompt is missing, empty, or exceeds length limits.
    """
    prompt = event.get("prompt", "").strip()
    if not prompt:
        raise ValueError("Request must include a non-empty 'prompt' field.")
    if len(prompt) > _MAX_PROMPT_LENGTH:
        raise ValueError(
            f"Prompt length {len(prompt)} exceeds maximum of {_MAX_PROMPT_LENGTH} characters."
        )
    return prompt


# ── Bedrock invocation ────────────────────────────────────────────────────────

def _build_request_body(prompt: str, max_tokens: int) -> str:
    """Build the model-specific request body.

    Currently supports Claude (Messages API body). Extend this function to handle
    additional model families (Titan, Llama, etc.).
    """
    if "anthropic.claude" in BEDROCK_MODEL_ID:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [
                {"role": "user", "content": prompt},
            ],
        }
    else:
        # Generic text-completion body for other model families
        body = {
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": max_tokens,
                "temperature": 0.7,
                "topP": 0.9,
            },
        }

    return json.dumps(body)


def _invoke_bedrock(prompt: str) -> dict[str, Any]:
    """Invoke the Bedrock model and return the parsed response."""
    request_body = _build_request_body(prompt, MAX_TOKENS)

    logger.info(
        "Invoking Bedrock model",
        extra={"model_id": BEDROCK_MODEL_ID, "prompt_length": len(prompt)},
    )

    response = _bedrock_client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=request_body,
    )

    response_body = json.loads(response["body"].read())
    logger.debug("Bedrock raw response received")

    # Extract text from Claude Messages API or generic response
    if "anthropic.claude" in BEDROCK_MODEL_ID:
        output_text = response_body["content"][0]["text"]
        input_tokens = response_body.get("usage", {}).get("input_tokens", 0)
        output_tokens = response_body.get("usage", {}).get("output_tokens", 0)
    else:
        output_text = response_body.get("results", [{}])[0].get("outputText", "")
        input_tokens = 0
        output_tokens = 0

    logger.info(
        "Bedrock invocation complete",
        extra={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    )

    return {
        "output": output_text,
        "model_id": BEDROCK_MODEL_ID,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    }


# ── Lambda handler ────────────────────────────────────────────────────────────

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:  # noqa: ARG001
    """AWS Lambda entry point.

    Expected event structure::

        {
            "prompt": "Your question or instruction here"
        }

    Returns::

        {
            "statusCode": 200,
            "body": {
                "output": "<model response text>",
                "model_id": "<bedrock model id>",
                "usage": {"input_tokens": N, "output_tokens": N}
            }
        }
    """
    is_proxy = _is_api_gateway_event(event)
    logger.debug(
        "Received event",
        extra={"event_keys": list(event.keys()) if isinstance(event, dict) else []},
    )

    try:
        payload = _parse_event(event)
        prompt = _validate_event(payload)
        result = _invoke_bedrock(prompt)

        return _build_response(200, result, is_proxy)

    except ValueError as exc:
        logger.warning("Invalid request: %s", exc)
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
        if error_code == "ValidationException":
            # Do not echo provider details back to the caller; they can include
            # account/model identifiers and request internals.
            return _build_response(
                400,
                {"error": "The model rejected the request. Check model configuration."},
                is_proxy,
            )

        return _build_response(
            502,
            {"error": "Upstream service error. Please contact support."},
            is_proxy,
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error during Bedrock invocation: %s", exc)
        return _build_response(500, {"error": "Internal server error."}, is_proxy)
