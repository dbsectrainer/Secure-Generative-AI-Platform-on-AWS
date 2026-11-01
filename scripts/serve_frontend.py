#!/usr/bin/env python3
"""
Serve the local RAG UI and proxy requests to the running SAM API.

The proxy keeps browser requests same-origin, so no CORS or production hosting
is implied. It is a local verification harness, not a production web server.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

LOG = logging.getLogger("frontend-proxy")
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "SecureGenAIFrontend/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        LOG.info("%s - %s", self.address_string(), fmt % args)

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: object) -> None:
        self._send_bytes(status, json.dumps(payload).encode("utf-8"), "application/json")

    def _root(self) -> Path:
        return Path(self.server.frontend_root).resolve()  # type: ignore[attr-defined]

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/local-token":
            try:
                with urllib.request.urlopen(  # noqa: S310
                    self.server.token_url, timeout=15  # type: ignore[attr-defined]
                ) as response:
                    self._send_bytes(
                        response.status,
                        response.read(),
                        response.headers.get("Content-Type", "application/json"),
                    )
            except urllib.error.HTTPError as exc:
                self._send_bytes(
                    exc.code, exc.read(), exc.headers.get("Content-Type", "application/json")
                )
            except Exception as exc:  # noqa: BLE001
                LOG.warning("Token proxy failed: %s", exc)
                self._send_json(502, {"error": "Local token service is unavailable."})
            return

        path = "index.html" if parsed.path in ("", "/") else parsed.path.lstrip("/")
        candidate = (self._root() / path).resolve()
        if self._root() not in candidate.parents and candidate != self._root():
            self._send_json(403, {"error": "forbidden"})
            return
        if not candidate.is_file():
            self._send_json(404, {"error": "not found"})
            return
        self._send_bytes(
            200,
            candidate.read_bytes(),
            CONTENT_TYPES.get(candidate.suffix, "application/octet-stream"),
        )

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self._send_json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else b""
        target = f"{self.server.api_base_url.rstrip('/')}{parsed.path[len('/api'):]}"
        request = urllib.request.Request(
            target,
            data=body,
            method="POST",
            headers={
                "Content-Type": self.headers.get("Content-Type", "application/json"),
                "Authorization": self.headers.get("Authorization", ""),
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
                self._send_bytes(
                    response.status,
                    response.read(),
                    response.headers.get("Content-Type", "application/json"),
                )
        except urllib.error.HTTPError as exc:
            self._send_bytes(
                exc.code, exc.read(), exc.headers.get("Content-Type", "application/json")
            )
        except Exception as exc:  # noqa: BLE001
            LOG.warning("API proxy failed: %s", exc)
            self._send_json(502, {"error": "API is unavailable."})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--api-base-url", default="http://127.0.0.1:3000")
    parser.add_argument("--token-url", default="http://127.0.0.1:9000/auth/token")
    parser.add_argument("--root", default="frontend")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / "index.html").is_file():
        raise SystemExit(f"frontend root not found: {root}")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.frontend_root = str(root)  # type: ignore[attr-defined]
    server.api_base_url = args.api_base_url  # type: ignore[attr-defined]
    server.token_url = args.token_url  # type: ignore[attr-defined]
    LOG.info("Frontend: http://127.0.0.1:%d (API %s)", args.port, args.api_base_url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("Stopping frontend")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
