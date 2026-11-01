"""
Bearer-token authentication for API Gateway invocations.

Production uses an API Gateway Cognito authorizer. This module adds
defense-in-depth validation inside the HTTP handlers and provides a testable
JWT/JWKS path for `sam local start-api`:

Environment variables:
    AUTH_REQUIRED       "true" to enforce authentication (default: false)
    AUTH_JWKS_URL       HTTPS endpoint serving the issuer's JWKS
    AUTH_ISSUER         Expected `iss` claim
    AUTH_AUDIENCE       Expected `aud` claim
    AUTH_PUBLIC_KEY     Optional PEM public key (testing/simple deployments)
    AUTH_ALGORITHMS     Comma-separated algorithms (default: RS256)

Direct Lambda invocations (tests and Lambda-to-Lambda calls) are not API
Gateway events and are intentionally not subject to bearer-token validation;
IAM controls those calls.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Authentication failure with an HTTP status code."""

    def __init__(self, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_api_gateway_event(event: Any) -> bool:
    return isinstance(event, dict) and "httpMethod" in event and "body" in event


def _auth_header(event: dict[str, Any]) -> str:
    headers = event.get("headers") or {}
    if not isinstance(headers, dict):
        return ""
    for key, value in headers.items():
        if key.lower() == "authorization" and isinstance(value, str):
            return value.strip()
    return ""


def _bearer_token(event: dict[str, Any]) -> str:
    header = _auth_header(event)
    if not header:
        return ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return ""
    return token.strip()


def _public_key() -> str:
    value = os.environ.get("AUTH_PUBLIC_KEY", "")
    return value.replace("\\n", "\n")


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True)


def _signing_key(token: str) -> Any:
    public_key = _public_key()
    if public_key:
        return public_key
    jwks_url = os.environ.get("AUTH_JWKS_URL", "").strip()
    if not jwks_url:
        raise AuthError("Authentication is not configured.", status_code=500)
    try:
        return _jwks_client(jwks_url).get_signing_key_from_jwt(token).key
    except PyJWKClientError as exc:
        logger.error("JWT signing-key lookup failed: %s", exc)
        raise AuthError("Unable to validate credentials.", status_code=401) from exc


def require_auth(event: Any) -> dict[str, Any] | None:
    """Validate a bearer token for API Gateway events.

    Returns verified claims, or ``None`` for direct invocations and when auth is
    disabled. Raises :class:`AuthError` for missing/invalid credentials.
    """
    if not _truthy(os.environ.get("AUTH_REQUIRED")):
        return None
    if not _is_api_gateway_event(event):
        return None

    token = _bearer_token(event)
    if not token:
        raise AuthError("A valid bearer token is required.")

    issuer = os.environ.get("AUTH_ISSUER", "").strip()
    audience = os.environ.get("AUTH_AUDIENCE", "").strip()
    if not issuer or not audience:
        raise AuthError("Authentication is not configured.", status_code=500)

    algorithms = [
        algorithm.strip()
        for algorithm in os.environ.get("AUTH_ALGORITHMS", "RS256").split(",")
        if algorithm.strip()
    ]
    key = _signing_key(token)
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            issuer=issuer,
            options={
                "verify_aud": False,
                "require": ["exp", "iat", "iss"],
            },
        )
        token_audience = claims.get("aud") or claims.get("client_id")
        if token_audience != audience:
            raise InvalidTokenError("audience does not match")
    except InvalidTokenError as exc:
        logger.warning("Rejected bearer token: %s", exc)
        raise AuthError("Invalid or expired token.") from exc
    except Exception as exc:  # noqa: BLE001 - fail closed without leaking details
        logger.warning("Unexpected token validation failure: %s", exc)
        raise AuthError("Invalid or expired token.") from exc

    return claims
