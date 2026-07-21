"""Tests for local_voice_ai/gallery_audio_cache.py's WAV load/save round trip."""

from __future__ import annotations

import pathlib

import pytest
from livekit import rtc

from local_voice_ai import gallery_audio_cache as gac


@pytest.fixture(autouse=True)
def _cache_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.setenv("STORY_GALLERY_AUDIO_CACHE_DIR", str(tmp_path / "gallery-audio"))


def _frame(data: bytes, sample_rate: int = 24000, num_channels: int = 1) -> rtc.AudioFrame:
    return rtc.AudioFrame(
        data=data,
        sample_rate=sample_rate,
        num_channels=num_channels,
        samples_per_channel=len(data) // (2 * num_channels),
    )


def test_load_with_no_cached_file_returns_none() -> None:
    assert gac.load("am_fenrir", "Once upon a time...") is None


def test_save_then_load_round_trips_audio() -> None:
    original = [_frame(b"\x01\x00" * 480), _frame(b"\x02\x00" * 480)]
    gac.save("am_fenrir", "Once upon a time...", original)

    loaded = gac.load("am_fenrir", "Once upon a time...")
    assert loaded is not None
    assert b"".join(bytes(f.data) for f in loaded) == b"".join(bytes(f.data) for f in original)
    assert all(f.sample_rate == 24000 and f.num_channels == 1 for f in loaded)


def test_different_voice_or_text_is_a_separate_cache_entry() -> None:
    gac.save("am_fenrir", "Once upon a time...", [_frame(b"\x01\x00" * 480)])
    assert gac.load("am_puck", "Once upon a time...") is None
    assert gac.load("am_fenrir", "A different story...") is None


def test_save_with_no_frames_is_a_no_op() -> None:
    gac.save("am_fenrir", "Once upon a time...", [])
    assert gac.load("am_fenrir", "Once upon a time...") is None


def test_corrupt_cache_file_falls_back_to_none() -> None:
    path = gac._cache_path("am_fenrir", "Once upon a time...")
    path.parent.mkdir(parents=True)
    path.write_text("not a wav file")
    assert gac.load("am_fenrir", "Once upon a time...") is None
