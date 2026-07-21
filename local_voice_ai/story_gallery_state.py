"""Per-story told-counts for agent.py's gallery-story shortcut, persisted
the same way known_speakers.py/parent_settings.py are (small JSON file, no
database needed) — via json_store.py's shared load/save/update idiom.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import json_store


def _store_path() -> Path:
    # Read lazily (not at import time) so tests can monkeypatch the env var
    # per-case instead of sharing one real path across the whole suite.
    return Path(os.getenv("STORY_GALLERY_STATE_PATH", "/models/story-gallery-state.json"))


def _validate(raw: object) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    return {str(k): int(v) for k, v in raw.items() if isinstance(v, (int, float))}


def load_counts() -> dict[str, int]:
    return json_store.load(_store_path(), {}, validate=_validate)


def save_counts(counts: dict[str, int]) -> None:
    json_store.save(_store_path(), counts)


def record_told(key: str) -> None:
    """Increment and persist a story's told-count immediately, locked
    against concurrent writers (e.g. two devices telling stories at once)."""

    def _increment(counts: dict[str, int]) -> dict[str, int]:
        counts[key] = counts.get(key, 0) + 1
        return counts

    json_store.update(_store_path(), {}, _increment, validate=_validate)
