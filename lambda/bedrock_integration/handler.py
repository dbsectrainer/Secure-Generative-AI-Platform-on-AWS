"""
Bedrock Orchestrator Lambda Function

Invokes an Amazon Bedrock foundation model from within a private VPC, using
an Interface VPC Endpoint for bedrock-runtime. Supports streaming and
non-streaming invocations.

Environment variables:
    BEDROCK_MODEL_ID      – Bedrock foundation model ID (e.g. anthropic.claude-3-sonnet-...)
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

# Boto3 client is created once at module load (reused across warm invocations).
_bedrock_config = Config(
    region_name=BEDROCK_REGION,
    retries={"max_attempts": 3, "mode": "adaptive"},
    connect_timeout=5,
    read_timeout=60,
)

_bedrock_client = boto3.client("bedrock-runtime", config=_bedrock_config)


# ── Input validation ──────────────────────────────────────────────────────────

_MAX_PROMPT_LENGTH = 10_000  # characters


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

    Currently supports Claude 3 (Messages API). Extend this function to handle
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

    # Extract text from Claude 3 Messages API or generic response
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
    logger.debug("Received event", extra={"event_keys": list(event.keys())})

    try:
        prompt = _validate_event(event)
        result = _invoke_bedrock(prompt)

        return {
            "statusCode": 200,
            "body": result,
        }

    except ValueError as exc:
        logger.warning("Invalid request: %s", exc)
        return {
            "statusCode": 400,
            "body": {"error": str(exc)},
        }

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        logger.error("Bedrock ClientError: %s – %s", error_code, exc)

        if error_code in ("ThrottlingException", "ServiceUnavailableException"):
            return {
                "statusCode": 429,
                "body": {"error": "Service temporarily unavailable. Please retry."},
            }
        if error_code == "ValidationException":
            return {
                "statusCode": 400,
                "body": {"error": f"Model validation error: {exc}"},
            }

        return {
            "statusCode": 502,
            "body": {"error": "Upstream service error. Please contact support."},
        }

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error during Bedrock invocation: %s", exc)
        return {
            "statusCode": 500,
            "body": {"error": "Internal server error."},
        }
