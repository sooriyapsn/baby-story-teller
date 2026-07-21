"""Disk cache of pre-rendered TTS audio for gallery-story text (see
agent.py's Assistant.tts_node). WAV files on the models volume, keyed by
voice+text.
"""

from __future__ import annotations

import hashlib
import logging
import os
import wave
from pathlib import Path

from livekit import rtc

logger = logging.getLogger("gallery_audio_cache")

_CHUNK_MS = 20


def cache_dir() -> Path:
    return Path(os.getenv("STORY_GALLERY_AUDIO_CACHE_DIR", "/models/story-gallery-audio-cache"))


def _cache_path(voice: str, text: str) -> Path:
    key = hashlib.sha256(f"{voice}:{text}".encode()).hexdigest()
    return cache_dir() / f"{key}.wav"


def load(voice: str, text: str) -> list[rtc.AudioFrame] | None:
    path = _cache_path(voice, text)
    if not path.is_file():
        return None
    try:
        with wave.open(str(path), "rb") as wav:
            sample_rate = wav.getframerate()
            num_channels = wav.getnchannels()
            raw = wav.readframes(wav.getnframes())
    except (OSError, wave.Error, EOFError):
        logger.warning("could not read cached gallery audio %s, treating as a miss", path)
        return None

    bytes_per_sample = 2 * num_channels
    chunk_bytes = max(1, sample_rate * _CHUNK_MS // 1000) * bytes_per_sample
    frames = []
    for offset in range(0, len(raw), chunk_bytes):
        piece = raw[offset : offset + chunk_bytes]
        samples_per_channel = len(piece) // bytes_per_sample
        if samples_per_channel == 0:
            continue
        frames.append(
            rtc.AudioFrame(
                data=piece,
                sample_rate=sample_rate,
                num_channels=num_channels,
                samples_per_channel=samples_per_channel,
            )
        )
    return frames


def save_wav_bytes(voice: str, text: str, wav_bytes: bytes) -> None:
    """Write an already-encoded WAV response (e.g. straight from Kokoro's
    HTTP API during startup warm-up) directly to the cache, no re-encode."""
    path = _cache_path(voice, text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(wav_bytes)


def save(voice: str, text: str, frames: list[rtc.AudioFrame]) -> None:
    if not frames:
        return
    sample_rate = frames[0].sample_rate
    num_channels = frames[0].num_channels
    raw = b"".join(bytes(f.data) for f in frames)

    path = _cache_path(voice, text)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(num_channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(raw)
