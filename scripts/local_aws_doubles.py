#!/usr/bin/env python3
"""
Local AWS service doubles for end-to-end verification.

This is a **test harness**, not an AWS emulator and not production code. It
implements only the narrow HTTP surfaces used by the Lambda handlers so that
`sam local start-api` can exercise the full request/response path without
calling paid AWS services or touching live data:

  * Bedrock Runtime  POST /model/{modelId}/invoke
  * OpenSearch       POST /{index}/_doc
                     POST /{index}/_search
  * Lambda Invoke    POST /2015-03-31/functions/{function}/invocations

Every response is deterministic. SigV4 signatures are accepted but not
verified. Run this only on a loopback interface while testing locally:

    python3 scripts/local_aws_doubles.py --port 9000

Then start the API with the mock environment file:

    sam local start-api --env-vars env.mock.json --port 3000 \
      --layer-cache-basedir "$PWD/.aws-sam/layers-pkg"

The verification report must state that AWS integrations were exercised
against these doubles, not against live AWS.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

LOG = logging.getLogger("local-aws-doubles")

# ── Local auth issuer (test-only RSA signing key) ────────────────────────────

AUTH_ISSUER = os.environ.get("AUTH_ISSUER", "http://host.docker.internal:9000")
AUTH_AUDIENCE = os.environ.get("AUTH_AUDIENCE", "secgenai-api")
AUTH_KEY_ID = "local-auth-key"

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()
_PUBLIC_PEM = _PUBLIC_KEY.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)
_PUBLIC_JWK = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(_PUBLIC_KEY))
_PUBLIC_JWK.update({"kid": AUTH_KEY_ID, "use": "sig", "alg": "RS256"})

# Deterministic 1024-dimensional embedding (Titan Text Embeddings v2 default).
EMBEDDING = [round(((i * 37) % 200 - 100) / 1000.0, 4) for i in range(1024)]

RETRIEVAL_CHUNKS = [
    {
        "text": (
            "The platform encrypts documents at rest with a customer-managed "
            "KMS key and requires TLS 1.2 or later in transit."
        ),
        "metadata": {"document_key": "raw/security-controls.txt", "chunk_index": 0},
        "score": 0.94,
    },
    {
        "text": (
            "Audit events are written to CloudTrail with S3 Object Lock "
            "retention for seven years."
        ),
        "metadata": {"document_key": "raw/audit-policy.txt", "chunk_index": 1},
        "score": 0.88,
    },
    {
        "text": (
            "Retrieval results are scoped by document metadata so one tenant "
            "cannot retrieve another tenant's chunks."
        ),
        "metadata": {"document_key": "raw/rag-controls.txt", "chunk_index": 2},
        "score": 0.81,
    },
]

MODEL_PATH = re.compile(r"^/model/(?P<model>[^/]+)/invoke$")
DOC_PATH = re.compile(r"^/(?P<index>[^/]+)/_doc$")
SEARCH_PATH = re.compile(r"^/(?P<index>[^/]+)/_search$")
LAMBDA_PATH = re.compile(r"^/2015-03-31/functions/(?P<function>[^/]+)/invocations$")


def _bedrock_response(model_id: str, request_body: dict[str, Any]) -> dict[str, Any]:
    """Return a Titan embedding or Claude Messages response."""
    if "embed" in model_id.lower():
        return {"embedding": EMBEDDING}

    prompt = ""
    messages = request_body.get("messages")
    if isinstance(messages, list) and messages:
        content = messages[-1].get("content", "")
        if isinstance(content, str):
            prompt = content

    # Keep the mock answer grounded in the retrieved context when present.
    if "Context:" in prompt:
        answer = (
            "Based on the retrieved policy excerpts, the platform encrypts data "
            "with a customer-managed KMS key, retains CloudTrail audit events for "
            "seven years, and scopes retrieval results by document metadata."
        )
    else:
        answer = (
            "Local test double response: AWS Bedrock was not called. "
            "The request/response path completed successfully."
        )

    return {
        "id": "msg_local_double",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": answer}],
        "usage": {"input_tokens": 128, "output_tokens": 42},
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "LocalAWSDoubles/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        LOG.info("%s - %s", self.address_string(), fmt % args)

    # ── Helpers ────────────────────────────────────────────────────────────

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Amzn-Requestid", "local-double-request")
        self.end_headers()
        self.wfile.write(body)

    # ── Routing ────────────────────────────────────────────────────────────

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/auth/token":
            now = int(time.time())
            token = jwt.encode(
                {
                    "sub": "local-test-user",
                    "iss": AUTH_ISSUER,
                    "aud": AUTH_AUDIENCE,
                    "iat": now,
                    "exp": now + 3600,
                },
                _PRIVATE_KEY,
                algorithm="RS256",
                headers={"kid": AUTH_KEY_ID},
            )
            self._send_json(
                200,
                {
                    "access_token": token,
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "issuer": AUTH_ISSUER,
                    "audience": AUTH_AUDIENCE,
                },
            )
            return
        if self.path == "/.well-known/jwks.json":
            self._send_json(200, {"keys": [_PUBLIC_JWK]})
            return
        if self.path.rstrip("/") in ("", "/health"):
            self._send_json(
                200,
                {
                    "status": "ok",
                    "service": "local-aws-doubles",
                    "note": "test harness only; not AWS",
                },
            )
            return
        self._send_json(404, {"message": "not found", "path": self.path})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]

        model_match = MODEL_PATH.match(path)
        if model_match:
            model_id = model_match.group("model")
            payload = _bedrock_response(model_id, self._read_json())
            self._send_json(200, payload)
            return

        lambda_match = LAMBDA_PATH.match(path)
        if lambda_match:
            # The orchestrator invokes the retrieval function; return a
            # RequestResponse payload identical in shape to the retrieval
            # handler's direct-invocation response.
            self._read_json()
            self._send_json(
                200,
                {
                    "statusCode": 200,
                    "body": {
                        "results": RETRIEVAL_CHUNKS,
                        "query": "local mock query",
                        "top_k": len(RETRIEVAL_CHUNKS),
                    },
                },
            )
            return

        if DOC_PATH.match(path):
            self._read_json()
            self._send_json(201, {"result": "created", "_index": "rag-documents"})
            return

        search_match = SEARCH_PATH.match(path)
        if search_match:
            request_body = self._read_json()
            size = request_body.get("size", len(RETRIEVAL_CHUNKS))
            try:
                size = max(1, min(int(size), len(RETRIEVAL_CHUNKS)))
            except (TypeError, ValueError):
                size = len(RETRIEVAL_CHUNKS)
            self._send_json(
                200,
                {
                    "took": 1,
                    "timed_out": False,
                    "hits": {
                        "total": {"value": size, "relation": "eq"},
                        "max_score": RETRIEVAL_CHUNKS[0]["score"],
                        "hits": [
                            {
                                "_index": "rag-documents",
                                "_id": f"chunk-{i}",
                                "_score": chunk["score"],
                                "_source": {
                                    "text": chunk["text"],
                                    "metadata": chunk["metadata"],
                                },
                            }
                            for i, chunk in enumerate(RETRIEVAL_CHUNKS[:size])
                        ],
                    },
                },
            )
            return

        self._send_json(404, {"message": "not found", "path": path})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    LOG.info(
        "Local AWS doubles listening on http://%s:%d (test harness only)",
        args.host,
        args.port,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("Stopping local AWS doubles")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
