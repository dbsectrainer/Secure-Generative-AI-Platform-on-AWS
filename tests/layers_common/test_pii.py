"""Tests for optional Comprehend PII redaction."""

from __future__ import annotations

from botocore.exceptions import ClientError

import pii
from pii import PiiError, redact_pii


class FakeComprehend:
    def __init__(self, entities=None, error=None):
        self.entities = entities or []
        self.error = error

    def detect_pii_entities(self, **_kwargs):
        if self.error:
            raise self.error
        return {"Entities": self.entities}


def test_disabled_returns_input(monkeypatch):
    monkeypatch.setenv("PII_REDACTION_ENABLED", "false")
    assert redact_pii("email a@b.com") == "email a@b.com"


def test_entities_are_replaced(monkeypatch):
    text = "Email a@b.com or call 555-0100"
    entities = [
        {"Type": "EMAIL", "BeginOffset": 6, "EndOffset": 13},
        {"Type": "PHONE", "BeginOffset": 22, "EndOffset": 30},
    ]
    monkeypatch.setenv("PII_REDACTION_ENABLED", "true")
    monkeypatch.setattr(pii, "_client", lambda *_args: FakeComprehend(entities))
    assert redact_pii(text) == "Email [EMAIL] or call [PHONE]"


def test_invalid_offsets_are_ignored(monkeypatch):
    monkeypatch.setenv("PII_REDACTION_ENABLED", "true")
    monkeypatch.setattr(
        pii, "_client", lambda *_args: FakeComprehend([{"Type": "EMAIL", "BeginOffset": 99, "EndOffset": 2}])
    )
    text = "short"
    assert redact_pii(text) == text


def test_service_error_fails_closed(monkeypatch):
    monkeypatch.setenv("PII_REDACTION_ENABLED", "true")
    error = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
        "DetectPiiEntities",
    )
    monkeypatch.setattr(pii, "_client", lambda *_args: FakeComprehend(error=error))
    try:
        redact_pii("email a@b.com")
    except PiiError:
        pass
    else:
        raise AssertionError("expected PiiError")
