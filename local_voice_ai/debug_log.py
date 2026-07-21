"""Optional per-turn conversation transcript + latency log — debugging only.
Off by default (DEBUG_CONVERSATION_LOG); when off, nothing in this module
touches the filesystem at all, not even to create the log directory.
"""

from __future__ import annotations

import datetime
import logging
import os
from pathlib import Path

logger = logging.getLogger("debug_log")


def enabled() -> bool:
    return os.getenv("DEBUG_CONVERSATION_LOG", "").strip().lower() in {"1", "true", "yes", "on"}


class ConversationDebugLogger:
    def __init__(self, room_name: str) -> None:
        log_dir = Path(os.getenv("DEBUG_LOG_DIR", "logs"))
        log_dir.mkdir(parents=True, exist_ok=True)
        started_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self._path = log_dir / f"{started_at}_{room_name}.log"
        self._path.touch()
        logger.info("conversation debug log: %s", self._path)

    def _write(self, line: str) -> None:
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")
        with self._path.open("a", encoding="utf-8") as f:
            f.write(f"{timestamp}  {line}\n")

    def log_user(self, text: str) -> None:
        self._write(f"USER            {text}")

    def log_agent(self, text: str, latency_seconds: float | None) -> None:
        latency = f"{latency_seconds:.2f}s" if latency_seconds is not None else "n/a"
        self._write(f"AGENT ({latency:>6})  {text}")


def maybe_open(room_name: str) -> ConversationDebugLogger | None:
    return ConversationDebugLogger(room_name) if enabled() else None
