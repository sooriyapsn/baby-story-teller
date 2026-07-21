"""Tests for local_voice_ai/story_gallery_state.py's load/save/record round trip."""

from __future__ import annotations

import os
import pathlib

import pytest

from local_voice_ai import story_gallery_state as sgs


@pytest.fixture(autouse=True)
def _store_path(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.setenv("STORY_GALLERY_STATE_PATH", str(tmp_path / "story-gallery-state.json"))


def test_load_with_no_file_returns_empty() -> None:
    assert sgs.load_counts() == {}


def test_record_told_then_load_round_trips() -> None:
    sgs.record_told("en:The Fox")
    assert sgs.load_counts() == {"en:The Fox": 1}


def test_record_told_increments_existing_key() -> None:
    sgs.record_told("en:The Fox")
    sgs.record_told("en:The Fox")
    sgs.record_told("en:The Bear")
    assert sgs.load_counts() == {"en:The Fox": 2, "en:The Bear": 1}


def test_corrupt_file_falls_back_to_empty() -> None:
    path = pathlib.Path(os.environ["STORY_GALLERY_STATE_PATH"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json")
    assert sgs.load_counts() == {}
