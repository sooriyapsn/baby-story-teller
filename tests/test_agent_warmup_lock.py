"""Tests for local_voice_ai/agent.py's _run_once_across_processes lock helper."""

from __future__ import annotations

import os
import pathlib
import time

import pytest

from local_voice_ai import agent


@pytest.fixture(autouse=True)
def _cache_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.setenv("STORY_GALLERY_AUDIO_CACHE_DIR", str(tmp_path / "gallery-audio"))


def test_runs_fn_once() -> None:
    calls = []
    agent._run_once_across_processes("test.lock", lambda: calls.append(1))
    assert calls == [1]


def test_lock_released_after_running() -> None:
    agent._run_once_across_processes("test.lock", lambda: None)
    lock_path = agent.gallery_audio_cache.cache_dir() / "test.lock"
    assert not lock_path.exists()


def test_second_concurrent_caller_is_skipped_while_lock_held() -> None:
    lock_path = agent.gallery_audio_cache.cache_dir() / "test.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch()  # simulate another process already holding a fresh lock

    calls = []
    agent._run_once_across_processes("test.lock", lambda: calls.append(1))
    assert calls == []


def test_stale_lock_is_cleared_and_fn_still_runs() -> None:
    lock_path = agent.gallery_audio_cache.cache_dir() / "test.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch()
    old_time = time.time() - agent._STALE_LOCK_AFTER_SECONDS - 1
    os.utime(lock_path, (old_time, old_time))

    calls = []
    agent._run_once_across_processes("test.lock", lambda: calls.append(1))
    assert calls == [1]


def test_exception_in_fn_still_releases_lock() -> None:
    lock_path = agent.gallery_audio_cache.cache_dir() / "test.lock"

    def _boom() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        agent._run_once_across_processes("test.lock", _boom)
    assert not lock_path.exists()
