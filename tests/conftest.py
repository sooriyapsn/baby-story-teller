"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest


_OUR_ENV_PREFIXES = (
    "LIVEKIT_", "LLAMA_", "STT_", "TTS_", "MANAGE_", "WEB_",
    "DEVICE", "NEMOTRON_", "WHISPER_", "WAKE_WORD", "FRONTEND_DIR", "KOKORO_", "LOG_LEVEL",
    "VOICE_ID_", "KNOWN_SPEAKERS_", "STORY_GALLERY_", "DEBUG_",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wipe project-owned env vars before each test so defaults are predictable."""
    for key in list(os.environ):
        if key.startswith(_OUR_ENV_PREFIXES):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def _reset_pin_lockout() -> None:
    """PIN-attempt lockout state is module-level (see parent_settings.check_pin)
    so it survives across a real supervisor's lifetime — reset it per test so
    one test's wrong-PIN attempts can't lock out another's correct one."""
    from local_voice_ai import parent_settings

    parent_settings._failed_pin_attempts.clear()
