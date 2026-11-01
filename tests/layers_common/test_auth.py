"""Tests for the shared bearer-token validator."""

from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from auth import AuthError, require_auth


@pytest.fixture(scope="module")
def keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem.decode()


def _token(private_pem: bytes, *, audience="secgenai-api", issuer="https://issuer.test", ttl=300):
    now = int(time.time())
    return jwt.encode(
        {
            "sub": "test-user",
            "aud": audience,
            "iss": issuer,
            "iat": now,
            "exp": now + ttl,
        },
        private_pem,
        algorithm="RS256",
    )


def _event(token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return {
        "httpMethod": "POST",
        "body": "{}",
        "headers": headers,
        "requestContext": {"requestId": "test"},
    }


@pytest.fixture(autouse=True)
def _env(monkeypatch, keypair):
    _, public_pem = keypair
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_PUBLIC_KEY", public_pem)
    monkeypatch.setenv("AUTH_ISSUER", "https://issuer.test")
    monkeypatch.setenv("AUTH_AUDIENCE", "secgenai-api")
    monkeypatch.setenv("AUTH_ALGORITHMS", "RS256")


def test_valid_token_is_accepted(keypair):
    private_pem, _ = keypair
    claims = require_auth(_event(_token(private_pem)))
    assert claims["sub"] == "test-user"


def test_missing_token_is_rejected():
    with pytest.raises(AuthError) as exc:
        require_auth(_event())
    assert exc.value.status_code == 401


def test_malformed_token_is_rejected():
    with pytest.raises(AuthError):
        require_auth(_event("not-a-jwt"))


def test_cognito_access_token_client_id_is_accepted(keypair):
    private_pem, _ = keypair
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "test-user",
            "client_id": "secgenai-api",
            "iss": "https://issuer.test",
            "iat": now,
            "exp": now + 300,
            "token_use": "access",
        },
        private_pem,
        algorithm="RS256",
    )
    claims = require_auth(_event(token))
    assert claims["client_id"] == "secgenai-api"


def test_wrong_audience_is_rejected(keypair):
    private_pem, _ = keypair
    with pytest.raises(AuthError):
        require_auth(_event(_token(private_pem, audience="other-api")))


def test_expired_token_is_rejected(keypair):
    private_pem, _ = keypair
    with pytest.raises(AuthError):
        require_auth(_event(_token(private_pem, ttl=-10)))


def test_direct_invocation_bypasses_auth():
    assert require_auth({"prompt": "hello"}) is None


def test_disabled_auth_bypasses(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    assert require_auth(_event()) is None


def test_missing_configuration_fails_closed(monkeypatch, keypair):
    private_pem, _ = keypair
    monkeypatch.delenv("AUTH_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("AUTH_JWKS_URL", raising=False)
    with pytest.raises(AuthError) as exc:
        require_auth(_event(_token(private_pem)))
    assert exc.value.status_code == 500
