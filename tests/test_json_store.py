"""Tests for local_voice_ai/json_store.py's load/save/update round trip."""

from __future__ import annotations

import pathlib

from local_voice_ai import json_store


def test_load_with_no_file_returns_default(tmp_path: pathlib.Path) -> None:
    assert json_store.load(tmp_path / "missing.json", {"x": 1}) == {"x": 1}


def test_save_then_load_round_trips(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "data.json"
    json_store.save(path, {"a": 1, "b": 2})
    assert json_store.load(path, {}) == {"a": 1, "b": 2}


def test_corrupt_file_falls_back_to_default(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "data.json"
    path.write_text("not json")
    assert json_store.load(path, {"fallback": True}) == {"fallback": True}


def test_load_applies_validate(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "data.json"
    json_store.save(path, {"a": "1", "b": "not a number"})
    result = json_store.load(
        path, {}, validate=lambda raw: {k: int(v) for k, v in raw.items() if str(v).isdigit()}
    )
    assert result == {"a": 1}


def test_update_locked_read_modify_write(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "counts.json"

    def _increment(counts: dict[str, int]) -> dict[str, int]:
        counts["x"] = counts.get("x", 0) + 1
        return counts

    result1 = json_store.update(path, {}, _increment)
    result2 = json_store.update(path, {}, _increment)
    assert result1 == {"x": 1}
    assert result2 == {"x": 2}
    assert json_store.load(path, {}) == {"x": 2}
