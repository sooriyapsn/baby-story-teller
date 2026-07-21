"""Tests for local_voice_ai/agent.py's LLM-skipping gallery-story shortcut."""

from __future__ import annotations

import pathlib

import pytest
from livekit.agents import llm

from local_voice_ai import agent, story_gallery_state
from local_voice_ai.characters import CHARACTERS
from local_voice_ai.story_examples import StoryExample

FOX = StoryExample(category="Animals", title="The Fox", language="en", body="Once upon a fox, in a den...")
BEAR = StoryExample(category="Animals", title="The Bear", language="en", body="Once upon a bear, in a cave...")


@pytest.fixture(autouse=True)
def _store_path(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.setenv("STORY_GALLERY_STATE_PATH", str(tmp_path / "story-gallery-state.json"))


def _chat_ctx(user_text: str) -> llm.ChatContext:
    ctx = llm.ChatContext()
    ctx.add_message(role="user", content=user_text)
    return ctx


def _assistant(monkeypatch: pytest.MonkeyPatch, stories: list[StoryExample], language: str = "en") -> agent.Assistant:
    monkeypatch.setattr(agent, "load_story_examples", lambda: stories)
    return agent.Assistant(CHARACTERS["red"], language=language)


class TestIsGenericStoryRequest:
    @pytest.mark.parametrize(
        "text",
        [
            "tell me a story",
            "Tell me a story!",
            "tell me another story",
            "can you tell me a story please",
            "story time",
            "read me a story",
            "one more story",
        ],
    )
    def test_generic_asks_match(self, text: str) -> None:
        assert agent._is_generic_story_request(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "tell me a story about a dragon",
            "tell me about space",
            "tell me a story with a fox in it",
            "what's your favorite color",
            "",
            "who are you",
        ],
    )
    def test_specific_or_unrelated_do_not_match(self, text: str) -> None:
        assert agent._is_generic_story_request(text) is False


class TestPickGalleryStory:
    def test_generic_ask_picks_a_story(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assistant = _assistant(monkeypatch, [FOX, BEAR])
        story = assistant._pick_gallery_story(_chat_ctx("tell me a story"))
        assert story in (FOX, BEAR)

    def test_specific_ask_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assistant = _assistant(monkeypatch, [FOX, BEAR])
        assert assistant._pick_gallery_story(_chat_ctx("tell me a story about dragons")) is None

    def test_non_english_session_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assistant = _assistant(monkeypatch, [FOX, BEAR], language="te")
        assert assistant._pick_gallery_story(_chat_ctx("tell me a story")) is None

    def test_no_stories_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assistant = _assistant(monkeypatch, [])
        assert assistant._pick_gallery_story(_chat_ctx("tell me a story")) is None

    def test_does_not_repeat_within_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assistant = _assistant(monkeypatch, [FOX])
        first = assistant._pick_gallery_story(_chat_ctx("tell me a story"))
        assert first is FOX
        second = assistant._pick_gallery_story(_chat_ctx("tell me another story"))
        assert second is None

    def test_prefers_least_told_globally(self, monkeypatch: pytest.MonkeyPatch) -> None:
        story_gallery_state.record_told(agent._gallery_key(FOX))
        story_gallery_state.record_told(agent._gallery_key(FOX))
        assistant = _assistant(monkeypatch, [FOX, BEAR])
        story = assistant._pick_gallery_story(_chat_ctx("tell me a story"))
        assert story is BEAR

    def test_records_told_count(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assistant = _assistant(monkeypatch, [FOX])
        assistant._pick_gallery_story(_chat_ctx("tell me a story"))
        assert story_gallery_state.load_counts()[agent._gallery_key(FOX)] == 1


class TestLlmNodeShortcut:
    async def test_generic_ask_yields_gallery_story_without_llm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assistant = _assistant(monkeypatch, [FOX])
        chunks = [c async for c in assistant.llm_node(_chat_ctx("tell me a story"), [], None)]
        assert len(chunks) == 1
        assert FOX.body in chunks[0]
        assert chunks[0] != FOX.body  # a gallery intro line was prepended

    async def test_specific_ask_falls_through_to_default_llm_node(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assistant = _assistant(monkeypatch, [FOX])

        async def _fake_default_llm_node(agent_self, chat_ctx, tools, model_settings):
            yield "fell through to the llm"

        monkeypatch.setattr(agent.Agent.default, "llm_node", _fake_default_llm_node)
        chunks = [
            c async for c in assistant.llm_node(_chat_ctx("tell me a story about dragons"), [], None)
        ]
        assert chunks == ["fell through to the llm"]
