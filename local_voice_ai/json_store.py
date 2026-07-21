"""Shared small-JSON-file-on-disk idiom, factored out of what
known_speakers.py, parent_settings.py, and story_gallery_state.py were each
implementing independently.
"""

from __future__ import annotations

import fcntl
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

logger = logging.getLogger("json_store")

T = TypeVar("T")


def load(path: Path, default: T, *, validate: Callable[[object], T] | None = None) -> T:
    if not path.is_file():
        return default
    try:
        raw = json.loads(path.read_text())
        return validate(raw) if validate is not None else raw  # type: ignore[return-value]
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        logger.warning("could not read %s, using default", path)
        return default


def save(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def update(
    path: Path,
    default: T,
    mutate: Callable[[T], T],
    *,
    validate: Callable[[object], T] | None = None,
) -> T:
    """Locked read-modify-write: mutate(current) -> new, saved while holding
    an exclusive lock on a sibling `.lock` file, so concurrent callers (e.g.
    two devices in the same household) can't race and silently lose a write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            current = load(path, default, validate=validate)
            new = mutate(current)
            save(path, new)
            return new
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
