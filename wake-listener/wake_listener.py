#!/usr/bin/env python3
"""Tiny always-on HTTP listener that runs directly on the host (NOT inside
Docker — it exists specifically to start the container when it's down, so it
can't live inside the thing it starts). Deliberately stdlib-only: it must
work with no venv activated, e.g. launched automatically by systemd at boot.

Exposes exactly one authenticated action — "docker compose up -d" in this
project's directory — and nothing else. No arbitrary command execution, no
free-form input reaches the shell: the phone/tablet app can only ever
trigger this one fixed, idempotent, safe operation.

Config comes from the same .env file docker-compose.yml already reads
(WAKE_LISTENER_PORT, WAKE_SECRET), so there is exactly one file to edit for
all of this project's settings, not a second config format to keep in sync.
"""

from __future__ import annotations

import hmac
import json
import logging
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent

logging.basicConfig(level=logging.INFO, format="%(asctime)s wake-listener: %(message)s")
logger = logging.getLogger("wake-listener")


def _read_env_file(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE parser for .env — no python-dotenv dependency, so
    this keeps working even outside the project's venv."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def load_config() -> tuple[int, str]:
    env = _read_env_file(PROJECT_DIR / ".env")
    port = int(env.get("WAKE_LISTENER_PORT", "9191"))
    secret = env.get("WAKE_SECRET", "")
    if not secret:
        logger.warning(
            "WAKE_SECRET is not set in .env — the wake endpoint will refuse all requests "
            "until you add one (see the main README's \"Waking the server remotely\" section)"
        )
    return port, secret


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib signature
        logger.info("%s - %s", self.address_string(), format % args)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib method name
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib method name
        if self.path != "/wake":
            self._send_json(404, {"error": "not found"})
            return

        port, secret = load_config()
        provided = self.headers.get("X-Wake-Secret", "")
        if not secret or not hmac.compare_digest(provided, secret):
            self._send_json(401, {"error": "invalid secret"})
            return

        logger.info("valid wake request received — running docker compose up -d")
        try:
            result = subprocess.run(
                ["docker", "compose", "up", "-d"],
                cwd=PROJECT_DIR,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.exception("failed to run docker compose")
            self._send_json(500, {"error": str(exc)})
            return

        if result.returncode != 0:
            logger.error("docker compose up failed: %s", result.stderr[-2000:])
            self._send_json(500, {"error": result.stderr[-2000:]})
            return

        logger.info("docker compose up -d issued successfully")
        self._send_json(200, {"status": "starting"})


def main() -> int:
    port, secret = load_config()
    if not secret:
        logger.error("refusing to start with no WAKE_SECRET set in .env — set one and retry")
        return 1

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    logger.info("listening on 0.0.0.0:%d for %s", port, PROJECT_DIR)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
