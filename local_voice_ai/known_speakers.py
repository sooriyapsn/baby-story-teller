"""Known-speaker registry: a name plus a voice embedding per enrolled child,
persisted to the same volume as model weights so it survives container
restarts. Mirrors parent_settings.py's storage idiom exactly.

Embeddings never leave this process — the parent-facing API in api.py only
ever exposes names/timestamps, never the raw vectors.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger("known_speakers")

# Best-effort, not tuned against real recordings yet — titanet's embeddings
# are trained mostly on adult voices, so accuracy on a child's voice is
# unverified. A false non-match just means she gets asked her name again,
# which is an acceptable soft failure for this feature.
MATCH_THRESHOLD = 0.72


def _store_path() -> Path:
    # Read lazily (not at import time) so tests can monkeypatch the env var
    # per-case instead of sharing one real path across the whole suite.
    return Path(os.getenv("KNOWN_SPEAKERS_PATH", "/models/known-speakers.json"))


@dataclass
class KnownSpeaker:
    name: str
    embedding: list[float]
    enrolled_at: float = 0.0


def load_speakers() -> list[KnownSpeaker]:
    path = _store_path()
    if path.is_file():
        try:
            raw = json.loads(path.read_text())
            fields = KnownSpeaker.__dataclass_fields__
            return [
                KnownSpeaker(**{k: entry[k] for k in fields if k in entry})
                for entry in raw
                if isinstance(entry, dict) and "name" in entry and "embedding" in entry
            ]
        except (json.JSONDecodeError, OSError, TypeError):
            logger.warning("could not read known speakers, starting empty")
    return []


def save_speakers(speakers: list[KnownSpeaker]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(s) for s in speakers]))


def enroll(name: str, embedding: list[float]) -> None:
    """Add or replace (by name) a known speaker and persist immediately."""
    speakers = [s for s in load_speakers() if s.name.lower() != name.lower()]
    speakers.append(KnownSpeaker(name=name, embedding=embedding, enrolled_at=time.time()))
    save_speakers(speakers)


def forget(name: str) -> bool:
    """Remove a known speaker by name. Returns whether anything was removed."""
    speakers = load_speakers()
    remaining = [s for s in speakers if s.name.lower() != name.lower()]
    if len(remaining) == len(speakers):
        return False
    save_speakers(remaining)
    return True


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def find_best_match(
    embedding: list[float], speakers: list[KnownSpeaker] | None = None
) -> KnownSpeaker | None:
    candidates = load_speakers() if speakers is None else speakers
    best: KnownSpeaker | None = None
    best_score = MATCH_THRESHOLD
    for speaker in candidates:
        score = cosine_similarity(embedding, speaker.embedding)
        if score >= best_score:
            best = speaker
            best_score = score
    return best
