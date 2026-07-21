"""Tests for local_voice_ai/agent.py's LLM-skipping gallery-story shortcut."""

from __future__ import annotations

import asyncio
import pathlib

import pytest
from livekit import rtc
from livekit.agents import llm

from local_voice_ai import agent, gallery_audio_cache, story_gallery_state
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


def _assistant(
    monkeypatch: pytest.MonkeyPatch,
    stories: list[StoryExample],
    language: str = "en",
    custom_story: str = "",
) -> agent.Assistant:
    monkeypatch.setattr(agent, "load_story_examples", lambda: stories)
    return agent.Assistant(CHARACTERS["red"], language=language, custom_story=custom_story)


class TestIsGenericStoryRequest:
    @pytest.mark.parametrize(
        "text",
        [
            "tell me a story",
            "Tell me a story!",
            "tell me another story",
            "can you tell me a story please",
            "story time",
            "storytime please",
            "read me a story",
            "one more story",
            "I want a story",
            "I want to hear a story",
            "got a story for me?",
            "have a story for me",
            "can I hear a story",
            "let's do a story",
            "story please",
            "a story please",
            "Red One, tell me a story",
            "hey Rosie, story time",
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
            "surprise me with a story",
            "what's your favorite color",
            "",
            "who are you",
            "I don't want a story",
            "no story",
            "another one",
        ],
    )
    def test_specific_or_unrelated_do_not_match(self, text: str) -> None:
        assert agent._is_generic_story_request(text) is False


class TestPickGalleryStory:
    async def test_generic_ask_picks_a_story(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assistant = _assistant(monkeypatch, [FOX, BEAR])
        story = await assistant._pick_gallery_story(_chat_ctx("tell me a story"))
        assert story in (FOX, BEAR)

    async def test_specific_ask_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assistant = _assistant(monkeypatch, [FOX, BEAR])
        assert await assistant._pick_gallery_story(_chat_ctx("tell me a story about dragons")) is None

    async def test_non_english_session_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assistant = _assistant(monkeypatch, [FOX, BEAR], language="te")
        assert await assistant._pick_gallery_story(_chat_ctx("tell me a story")) is None

    async def test_no_stories_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assistant = _assistant(monkeypatch, [])
        assert await assistant._pick_gallery_story(_chat_ctx("tell me a story")) is None

    async def test_custom_story_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A parent-set custom story must always win over the gallery
        shortcut, so a bare ask never silently substitutes a stock tale."""
        assistant = _assistant(monkeypatch, [FOX], custom_story="A gentle lesson about sharing toys.")
        assert await assistant._pick_gallery_story(_chat_ctx("tell me a story")) is None

    async def test_pending_recognition_greeting_returns_none_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A just-recognized returning child needs the real LLM to say her
        greeting — the shortcut must defer exactly once, then behave
        normally again."""
        assistant = _assistant(monkeypatch, [FOX])
        assistant._pending_recognition_greeting = True
        assert await assistant._pick_gallery_story(_chat_ctx("tell me a story")) is None
        assert assistant._pending_recognition_greeting is False
        assert await assistant._pick_gallery_story(_chat_ctx("tell me a story")) is FOX

    async def test_prefers_least_told_globally(self, monkeypatch: pytest.MonkeyPatch) -> None:
        story_gallery_state.record_told(agent._gallery_key(FOX))
        story_gallery_state.record_told(agent._gallery_key(FOX))
        assistant = _assistant(monkeypatch, [FOX, BEAR])
        story = await assistant._pick_gallery_story(_chat_ctx("tell me a story"))
        assert story is BEAR

    async def test_picking_alone_does_not_record_told(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Picking must be read-only — only tts_node actually synthesizing
        the matched text should persist a told-count (see TestTtsNodeCache),
        otherwise a discarded preemptive generation corrupts the state."""
        assistant = _assistant(monkeypatch, [FOX])
        await assistant._pick_gallery_story(_chat_ctx("tell me a story"))
        assert story_gallery_state.load_counts() == {}
        assert assistant._told_gallery_stories == set()


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

    async def test_specific_ask_leaves_no_pending_gallery_story(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assistant = _assistant(monkeypatch, [FOX])

        async def _fake_default_llm_node(agent_self, chat_ctx, tools, model_settings):
            yield "fell through to the llm"

        monkeypatch.setattr(agent.Agent.default, "llm_node", _fake_default_llm_node)
        async for _ in assistant.llm_node(_chat_ctx("tell me a story about dragons"), [], None):
            pass
        assert assistant._pending_gallery_stories == {}

    async def test_custom_story_bypasses_shortcut(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assistant = _assistant(monkeypatch, [FOX], custom_story="A gentle lesson about sharing toys.")

        async def _fake_default_llm_node(agent_self, chat_ctx, tools, model_settings):
            yield "the real llm, weaving in the custom story"

        monkeypatch.setattr(agent.Agent.default, "llm_node", _fake_default_llm_node)
        chunks = [c async for c in assistant.llm_node(_chat_ctx("tell me a story"), [], None)]
        assert chunks == ["the real llm, weaving in the custom story"]

    async def test_pending_recognition_greeting_bypasses_shortcut_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assistant = _assistant(monkeypatch, [FOX])
        assistant._pending_recognition_greeting = True

        async def _fake_default_llm_node(agent_self, chat_ctx, tools, model_settings):
            yield "greeting handled by the llm"

        monkeypatch.setattr(agent.Agent.default, "llm_node", _fake_default_llm_node)
        chunks = [c async for c in assistant.llm_node(_chat_ctx("tell me a story"), [], None)]
        assert chunks == ["greeting handled by the llm"]
        assert assistant._pending_recognition_greeting is False


def _frame(data: bytes = b"\x00\x00" * 480, sample_rate: int = 24000, num_channels: int = 1) -> rtc.AudioFrame:
    return rtc.AudioFrame(
        data=data,
        sample_rate=sample_rate,
        num_channels=num_channels,
        samples_per_channel=len(data) // (2 * num_channels),
    )


class TestTtsNodeCache:
    async def test_non_gallery_turn_delegates_to_default_tts_node(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assistant = _assistant(monkeypatch, [FOX])
        called = False

        async def _fake_default_tts_node(agent_self, text, model_settings):
            nonlocal called
            called = True
            async for _ in text:
                pass
            yield _frame()

        monkeypatch.setattr(agent.Agent.default, "tts_node", _fake_default_tts_node)

        async def _text() -> None:
            yield "hello"

        frames = [f async for f in assistant.tts_node(_text(), None)]
        assert called is True
        assert len(frames) == 1

    async def test_gallery_turn_cache_miss_synthesizes_and_saves(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        monkeypatch.setenv("STORY_GALLERY_AUDIO_CACHE_DIR", str(tmp_path / "gallery-audio"))
        assistant = _assistant(monkeypatch, [FOX])
        assistant._pending_gallery_stories["Once upon a fox..."] = FOX

        async def _fake_default_tts_node(agent_self, text, model_settings):
            yield _frame()
            yield _frame()

        monkeypatch.setattr(agent.Agent.default, "tts_node", _fake_default_tts_node)

        async def _text() -> None:
            yield "Once upon a fox..."

        frames = [f async for f in assistant.tts_node(_text(), None)]
        assert len(frames) == 2
        assert gallery_audio_cache.load(assistant._character.tts_voice, "Once upon a fox...") is not None
        # Told-state only persists once tts_node actually synthesizes the
        # matched text — see test_picking_alone_does_not_record_told above.
        assert story_gallery_state.load_counts()[agent._gallery_key(FOX)] == 1
        assert (FOX.language, FOX.title) in assistant._told_gallery_stories

    async def test_gallery_turn_cache_hit_skips_default_tts_node(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        monkeypatch.setenv("STORY_GALLERY_AUDIO_CACHE_DIR", str(tmp_path / "gallery-audio"))
        assistant = _assistant(monkeypatch, [FOX])
        gallery_audio_cache.save(assistant._character.tts_voice, "Once upon a fox...", [_frame(), _frame()])
        assistant._pending_gallery_stories["Once upon a fox..."] = FOX

        called = False

        async def _fake_default_tts_node(agent_self, text, model_settings):
            nonlocal called
            called = True
            yield _frame()

        monkeypatch.setattr(agent.Agent.default, "tts_node", _fake_default_tts_node)

        async def _text() -> None:
            yield "Once upon a fox..."

        frames = [f async for f in assistant.tts_node(_text(), None)]
        assert called is False
        assert len(frames) == 2

    async def test_tts_node_consumes_pending_gallery_story(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        monkeypatch.setenv("STORY_GALLERY_AUDIO_CACHE_DIR", str(tmp_path / "gallery-audio"))
        assistant = _assistant(monkeypatch, [FOX])
        assistant._pending_gallery_stories["Once upon a fox..."] = FOX

        async def _fake_default_tts_node(agent_self, text, model_settings):
            yield _frame()

        monkeypatch.setattr(agent.Agent.default, "tts_node", _fake_default_tts_node)

        async def _text() -> None:
            yield "Once upon a fox..."

        [f async for f in assistant.tts_node(_text(), None)]
        assert assistant._pending_gallery_stories == {}

    async def test_only_matching_text_is_treated_as_gallery(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        """This is the actual mechanism that fixes the preemptive-generation
        cross-talk bug: a pending entry for a DIFFERENT text than what this
        call receives must not be consumed, and must stay available for its
        own real turn."""
        monkeypatch.setenv("STORY_GALLERY_AUDIO_CACHE_DIR", str(tmp_path / "gallery-audio"))
        assistant = _assistant(monkeypatch, [FOX])
        assistant._pending_gallery_stories["Once upon a fox..."] = FOX

        called = False

        async def _fake_default_tts_node(agent_self, text, model_settings):
            nonlocal called
            called = True
            async for _ in text:
                pass
            yield _frame()

        monkeypatch.setattr(agent.Agent.default, "tts_node", _fake_default_tts_node)

        async def _text() -> None:
            yield "a completely different reply from the real LLM"

        frames = [f async for f in assistant.tts_node(_text(), None)]
        assert called is True
        assert len(frames) == 1
        assert assistant._pending_gallery_stories == {"Once upon a fox...": FOX}


class _FakeSession:
    def __init__(self) -> None:
        self.said: list[dict] = []

    def say(self, text: str, **kwargs) -> None:
        self.said.append({"text": text, **kwargs})


class TestLlmNodeFillers:
    def _assistant_with_session(
        self, monkeypatch: pytest.MonkeyPatch, stories: list[StoryExample]
    ) -> tuple[agent.Assistant, _FakeSession]:
        assistant = _assistant(monkeypatch, stories)
        fake_session = _FakeSession()
        monkeypatch.setattr(type(assistant), "session", property(lambda self: fake_session))
        return assistant, fake_session

    async def test_fast_llm_says_no_filler(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assistant, fake_session = self._assistant_with_session(monkeypatch, [FOX])
        monkeypatch.setattr(agent, "FILLER_DELAYS", (0.05, 0.1))

        async def _fast_llm(agent_self, chat_ctx, tools, model_settings):
            yield "quick reply"

        monkeypatch.setattr(agent.Agent.default, "llm_node", _fast_llm)
        chunks = [
            c async for c in assistant.llm_node(_chat_ctx("tell me a story about dragons"), [], None)
        ]
        assert chunks == ["quick reply"]
        assert fake_session.said == []

    async def test_slow_llm_triggers_both_fillers_in_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assistant, fake_session = self._assistant_with_session(monkeypatch, [FOX])
        monkeypatch.setattr(agent, "FILLER_DELAYS", (0.02, 0.05))

        async def _slow_llm(agent_self, chat_ctx, tools, model_settings):
            await asyncio.sleep(0.08)
            yield "finally, a reply"

        monkeypatch.setattr(agent.Agent.default, "llm_node", _slow_llm)
        chunks = [
            c async for c in assistant.llm_node(_chat_ctx("tell me a story about dragons"), [], None)
        ]
        assert chunks == ["finally, a reply"]
        assert [s["text"] for s in fake_session.said] == list(agent.FILLER_LINES["red"])

    async def test_medium_delay_triggers_only_first_filler(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assistant, fake_session = self._assistant_with_session(monkeypatch, [FOX])
        monkeypatch.setattr(agent, "FILLER_DELAYS", (0.02, 0.5))

        async def _medium_llm(agent_self, chat_ctx, tools, model_settings):
            await asyncio.sleep(0.05)
            yield "reply after one filler"

        monkeypatch.setattr(agent.Agent.default, "llm_node", _medium_llm)
        chunks = [
            c async for c in assistant.llm_node(_chat_ctx("tell me a story about dragons"), [], None)
        ]
        assert chunks == ["reply after one filler"]
        assert len(fake_session.said) == 1
        assert fake_session.said[0]["text"] == agent.FILLER_LINES["red"][0]

    async def test_filler_uses_cached_audio_when_available(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        monkeypatch.setenv("STORY_GALLERY_AUDIO_CACHE_DIR", str(tmp_path / "gallery-audio"))
        assistant, fake_session = self._assistant_with_session(monkeypatch, [FOX])
        monkeypatch.setattr(agent, "FILLER_DELAYS", (0.02, 100.0))
        gallery_audio_cache.save(assistant._character.tts_voice, agent.FILLER_LINES["red"][0], [_frame()])

        async def _slow_llm(agent_self, chat_ctx, tools, model_settings):
            await asyncio.sleep(0.05)
            yield "reply"

        monkeypatch.setattr(agent.Agent.default, "llm_node", _slow_llm)
        [c async for c in assistant.llm_node(_chat_ctx("tell me a story about dragons"), [], None)]
        assert "audio" in fake_session.said[0]

    async def test_filler_without_cache_omits_audio_kwarg(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assistant, fake_session = self._assistant_with_session(monkeypatch, [FOX])
        monkeypatch.setattr(agent, "FILLER_DELAYS", (0.02, 100.0))

        async def _slow_llm(agent_self, chat_ctx, tools, model_settings):
            await asyncio.sleep(0.05)
            yield "reply"

        monkeypatch.setattr(agent.Agent.default, "llm_node", _slow_llm)
        [c async for c in assistant.llm_node(_chat_ctx("tell me a story about dragons"), [], None)]
        assert "audio" not in fake_session.said[0]

    async def test_gallery_ask_never_triggers_fillers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assistant, fake_session = self._assistant_with_session(monkeypatch, [FOX])
        monkeypatch.setattr(agent, "FILLER_DELAYS", (0.0, 0.0))
        [c async for c in assistant.llm_node(_chat_ctx("tell me a story"), [], None)]
        assert fake_session.said == []


class TestGalleryCacheMissFillers:
    """A gallery cache-miss (first-ever telling of a story) synthesizes the
    whole story via Kokoro, which can take as long as a real LLM reply —
    it needs the same filler coverage, not just the real-LLM path."""

    async def test_slow_synthesis_on_cache_miss_triggers_filler(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        monkeypatch.setenv("STORY_GALLERY_AUDIO_CACHE_DIR", str(tmp_path / "gallery-audio"))
        assistant = _assistant(monkeypatch, [FOX])
        fake_session = _FakeSession()
        monkeypatch.setattr(type(assistant), "session", property(lambda self: fake_session))
        monkeypatch.setattr(agent, "FILLER_DELAYS", (0.02, 100.0))
        assistant._pending_gallery_stories["Once upon a fox..."] = FOX

        async def _slow_default_tts_node(agent_self, text, model_settings):
            await asyncio.sleep(0.05)
            yield _frame()

        monkeypatch.setattr(agent.Agent.default, "tts_node", _slow_default_tts_node)

        async def _text() -> None:
            yield "Once upon a fox..."

        frames = [f async for f in assistant.tts_node(_text(), None)]
        assert len(frames) == 1
        assert len(fake_session.said) == 1
        assert fake_session.said[0]["text"] == agent.FILLER_LINES["red"][0]

    async def test_fast_synthesis_on_cache_miss_triggers_no_filler(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        monkeypatch.setenv("STORY_GALLERY_AUDIO_CACHE_DIR", str(tmp_path / "gallery-audio"))
        assistant = _assistant(monkeypatch, [FOX])
        fake_session = _FakeSession()
        monkeypatch.setattr(type(assistant), "session", property(lambda self: fake_session))
        monkeypatch.setattr(agent, "FILLER_DELAYS", (5.0, 10.0))
        assistant._pending_gallery_stories["Once upon a fox..."] = FOX

        async def _fast_default_tts_node(agent_self, text, model_settings):
            yield _frame()

        monkeypatch.setattr(agent.Agent.default, "tts_node", _fast_default_tts_node)

        async def _text() -> None:
            yield "Once upon a fox..."

        [f async for f in assistant.tts_node(_text(), None)]
        assert fake_session.said == []
