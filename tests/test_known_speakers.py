"""Tests for local_voice_ai/known_speakers.py's load/save/match round trip."""

from __future__ import annotations

import pathlib

import pytest

from local_voice_ai import known_speakers as ks


@pytest.fixture(autouse=True)
def _store_path(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.setenv("KNOWN_SPEAKERS_PATH", str(tmp_path / "known-speakers.json"))


class TestLoadSave:
    def test_load_with_no_file_returns_empty(self) -> None:
        assert ks.load_speakers() == []

    def test_enroll_then_load_round_trips(self) -> None:
        ks.enroll("Emma", [1.0, 0.0, 0.0])
        speakers = ks.load_speakers()
        assert len(speakers) == 1
        assert speakers[0].name == "Emma"
        assert speakers[0].embedding == [1.0, 0.0, 0.0]
        assert speakers[0].enrolled_at > 0

    def test_enroll_same_name_replaces_not_duplicates(self) -> None:
        ks.enroll("Emma", [1.0, 0.0, 0.0])
        ks.enroll("emma", [0.0, 1.0, 0.0])  # case-insensitive replace
        speakers = ks.load_speakers()
        assert len(speakers) == 1
        assert speakers[0].embedding == [0.0, 1.0, 0.0]

    def test_corrupt_file_falls_back_to_empty(self, tmp_path: pathlib.Path) -> None:
        path = pathlib.Path(__import__("os").environ["KNOWN_SPEAKERS_PATH"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json")
        assert ks.load_speakers() == []


class TestForget:
    def test_forget_removes_by_name(self) -> None:
        ks.enroll("Emma", [1.0, 0.0, 0.0])
        ks.enroll("Noah", [0.0, 1.0, 0.0])
        assert ks.forget("Emma") is True
        remaining = [s.name for s in ks.load_speakers()]
        assert remaining == ["Noah"]

    def test_forget_unknown_name_returns_false(self) -> None:
        assert ks.forget("Nobody") is False


class TestFindBestMatch:
    def test_matches_closest_above_threshold(self) -> None:
        ks.enroll("Emma", [1.0, 0.0, 0.0])
        ks.enroll("Noah", [0.0, 1.0, 0.0])
        match = ks.find_best_match([0.99, 0.05, 0.0])
        assert match is not None
        assert match.name == "Emma"

    def test_no_match_below_threshold(self) -> None:
        ks.enroll("Emma", [1.0, 0.0, 0.0])
        assert ks.find_best_match([0.0, 0.0, 1.0]) is None

    def test_no_speakers_returns_none(self) -> None:
        assert ks.find_best_match([1.0, 0.0, 0.0]) is None
