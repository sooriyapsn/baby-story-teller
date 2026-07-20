"""Voice-recognition embeddings, backed by NeMo's speaker-verification model
(titanet) — already a dependency of this project via the ``ml`` extra (used
for Nemotron STT), so this adds no new ML library.

Model loading is deliberately lazy and cached in a module-level global rather
than done at import time: importing this module must stay cheap for
processes that never touch voice recognition (e.g. the FastAPI process,
which only reads/writes known_speakers.py's JSON store and never computes
embeddings itself).
"""

from __future__ import annotations

import logging
import os

import numpy as np
from livekit import rtc

logger = logging.getLogger("speaker_id")

_MODEL_NAME = os.getenv("VOICE_ID_MODEL", "titanet_small")
_TARGET_SAMPLE_RATE = 16000

_model = None


def _load_model():
    global _model
    if _model is None:
        # Imported lazily too: nemo.collections.asr pulls in torch, which is
        # only present under the `ml` extra and otherwise unnecessary weight
        # for anything that just reads/writes the known-speakers JSON file.
        import nemo.collections.asr as nemo_asr

        logger.info("loading speaker-id model: %s", _MODEL_NAME)
        _model = nemo_asr.models.EncDecSpeakerLabelModel.from_pretrained(_MODEL_NAME)
        _model.eval()
        logger.info("speaker-id model ready")
    return _model


def frames_to_embedding(frames: list[rtc.AudioFrame]) -> list[float] | None:
    """One embedding for a whole utterance's worth of raw mic frames.

    Returns None for a segment too short to embed meaningfully (titanet's
    docs recommend at least ~1s of speech for a stable embedding) rather
    than raising — a skipped enrollment/match attempt is harmless, whereas
    surfacing an exception here would take down the whole session.
    """
    if not frames:
        return None

    from nemo.collections.asr.parts.preprocessing.segment import AudioSegment

    sample_rate = frames[0].sample_rate
    chunks = [np.frombuffer(f.data, dtype=np.int16) for f in frames]
    samples_i16 = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
    samples = samples_i16.astype(np.float32) / 32768.0

    if len(samples) < sample_rate * 0.75:
        return None

    segment = AudioSegment(samples, sample_rate=sample_rate, target_sr=_TARGET_SAMPLE_RATE)

    try:
        model = _load_model()
        embedding, _logits = model.infer_segment(segment.samples)
    except Exception:
        logger.exception("speaker embedding failed")
        return None

    return embedding.squeeze().detach().cpu().numpy().tolist()
