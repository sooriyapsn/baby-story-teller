"""Per-story told-counts for agent.py's gallery-story shortcut, persisted
the same way known_speakers.py/parent_settings.py are (small JSON file, no
database needed).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("story_gallery_state")


def _store_path() -> Path:
    # Read lazily (not at import time) so tests can monkeypatch the env var
    # per-case instead of sharing one real path across the whole suite.
    return Path(os.getenv("STORY_GALLERY_STATE_PATH", "/models/story-gallery-state.json"))


def load_counts() -> dict[str, int]:
    path = _store_path()
    if path.is_file():
        try:
            raw = json.loads(path.read_text())
            if isinstance(raw, dict):
                return {str(k): int(v) for k, v in raw.items() if isinstance(v, (int, float))}
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            logger.warning("could not read story gallery state, starting empty")
    return {}


def save_counts(counts: dict[str, int]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(counts))


def record_told(key: str) -> None:
    """Increment and persist a story's told-count immediately."""
    counts = load_counts()
    counts[key] = counts.get(key, 0) + 1
    save_counts(counts)
