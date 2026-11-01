"""
Optional Amazon Comprehend PII redaction.

Guardrails remain the primary PII control. When enabled, this module detects
PII with Comprehend and replaces each entity with a type marker such as
``[EMAIL]`` before text is embedded, stored, or sent to the model.

Environment variables:
    PII_REDACTION_ENABLED   "true" to enable (default: false)
    PII_LANGUAGE_CODE       Comprehend language code (default: en)
    COMPREHEND_REGION       Region (defaults to AWS_REGION / eu-west-1)
    COMPREHEND_ENDPOINT_URL Optional local endpoint override for tests
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)


class PiiError(Exception):
    """PII redaction failed; callers must fail closed."""


def _enabled() -> bool:
    return os.environ.get("PII_REDACTION_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@lru_cache(maxsize=4)
def _client(region: str, endpoint_url: str) -> Any:
    kwargs: dict[str, Any] = {
        "region_name": region,
        "config": Config(
            region_name=region,
            retries={"max_attempts": 2, "mode": "standard"},
            connect_timeout=3,
            read_timeout=10,
        ),
    }
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    return boto3.client("comprehend", **kwargs)


def redact_pii(text: str) -> str:
    """Return *text* with Comprehend-detected PII replaced by type markers.

    When redaction is disabled or the text is empty, the input is returned
    unchanged. Detection/API failures raise :class:`PiiError` so callers can
    fail closed rather than forward unredacted data.
    """
    if not text or not _enabled():
        return text

    region = os.environ.get(
        "COMPREHEND_REGION", os.environ.get("AWS_REGION", "eu-west-1")
    )
    endpoint_url = os.environ.get("COMPREHEND_ENDPOINT_URL") or ""
    language = os.environ.get("PII_LANGUAGE_CODE", "en")

    try:
        response = _client(region, endpoint_url).detect_pii_entities(
            Text=text,
            LanguageCode=language,
        )
    except (ClientError, BotoCoreError) as exc:
        logger.error("Comprehend PII detection failed: %s", exc)
        raise PiiError("PII redaction service is unavailable.") from exc

    entities = [
        entity
        for entity in response.get("Entities", [])
        if isinstance(entity, dict)
        and isinstance(entity.get("BeginOffset"), int)
        and isinstance(entity.get("EndOffset"), int)
        and 0 <= entity["BeginOffset"] < entity["EndOffset"] <= len(text)
    ]
    if not entities:
        return text

    redacted = text
    for entity in sorted(entities, key=lambda item: item["BeginOffset"], reverse=True):
        marker = f"[{entity.get('Type', 'PII')}]"
        redacted = (
            redacted[: entity["BeginOffset"]] + marker + redacted[entity["EndOffset"] :]
        )

    logger.info("PII redaction applied", extra={"entity_count": len(entities)})
    return redacted
