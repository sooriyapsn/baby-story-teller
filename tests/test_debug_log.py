"""Tests for local_voice_ai/debug_log.py's opt-in conversation debug log."""

from __future__ import annotations

import pathlib

import pytest

from local_voice_ai import debug_log


@pytest.fixture(autouse=True)
def _log_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.setenv("DEBUG_LOG_DIR", str(tmp_path / "logs"))


def test_disabled_by_default() -> None:
    assert debug_log.enabled() is False


def test_maybe_open_returns_none_when_disabled(tmp_path: pathlib.Path) -> None:
    assert debug_log.maybe_open("room1") is None
    assert not (tmp_path / "logs").exists()


@pytest.mark.parametrize("value", ["1", "true", "True", "yes", "on"])
def test_enabled_recognizes_truthy_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("DEBUG_CONVERSATION_LOG", value)
    assert debug_log.enabled() is True


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off"])
def test_enabled_recognizes_falsy_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("DEBUG_CONVERSATION_LOG", value)
    assert debug_log.enabled() is False


def test_maybe_open_creates_dir_and_file_when_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    monkeypatch.setenv("DEBUG_CONVERSATION_LOG", "true")
    logger = debug_log.maybe_open("voice_assistant_room_123")
    assert logger is not None
    log_dir = tmp_path / "logs"
    assert log_dir.is_dir()
    assert len(list(log_dir.glob("*voice_assistant_room_123.log"))) == 1


def test_log_user_writes_a_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBUG_CONVERSATION_LOG", "true")
    logger = debug_log.maybe_open("room1")
    assert logger is not None
    logger.log_user("tell me a story")
    contents = logger._path.read_text()
    assert "USER" in contents
    assert "tell me a story" in contents


def test_log_agent_includes_latency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBUG_CONVERSATION_LOG", "true")
    logger = debug_log.maybe_open("room1")
    assert logger is not None
    logger.log_agent("Once upon a time...", 1.23)
    contents = logger._path.read_text()
    assert "AGENT" in contents
    assert "1.23s" in contents
    assert "Once upon a time..." in contents


def test_log_agent_handles_missing_latency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBUG_CONVERSATION_LOG", "true")
    logger = debug_log.maybe_open("room1")
    assert logger is not None
    logger.log_agent("Hello!", None)
    assert "n/a" in logger._path.read_text()


def test_multiple_lines_append_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBUG_CONVERSATION_LOG", "true")
    logger = debug_log.maybe_open("room1")
    assert logger is not None
    logger.log_user("first")
    logger.log_agent("second", 0.5)
    lines = logger._path.read_text().strip().splitlines()
    assert len(lines) == 2
    assert "first" in lines[0]
    assert "second" in lines[1]
