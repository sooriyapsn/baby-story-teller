"""LiveKit Agents worker: a storyteller companion for a young child.

Default base URLs are loopback (``127.0.0.1``) instead of Docker service
names — the supervisor spawns the inference children on loopback ports, so
this is correct for both single-image deployment and bare-metal local runs.
"""

import asyncio
import json
import logging
import os
import random
import re
import threading
import time
from collections.abc import AsyncIterable, Callable
from typing import TypeVar

import httpx
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    ModelSettings,
    cli,
    function_tool,
    llm,
)
from livekit.plugins import openai, silero
from livekit.plugins.turn_detector.english import EnglishModel

from . import gallery_audio_cache, known_speakers, speaker_id, story_gallery_state
from .characters import CHARACTERS, Character, get_character, instructions_for
from .parent_settings import load_settings
from .story_examples import StoryExample, load_story_examples, sample_story_examples

logger = logging.getLogger("agent")

load_dotenv(".env.local")

T = TypeVar("T")

# Every word must be on this allowlist to count as a bare story ask —
# unrecognized words (topics, questions, "don't") fall through to the LLM.
_TOPIC_HINT_RE = re.compile(
    r"\b(about|regarding|involving|with|where|who|starring|featuring|like)\b", re.IGNORECASE
)
_STORY_FILLER_WORDS = {
    "hey", "hi", "hello", "okay", "ok", "so", "well", "um", "umm", "uh",
    "please", "can", "you", "could", "will", "would", "do", "me", "i",
    "want", "wanna", "to", "hear", "have", "got", "a", "an", "the",
    "another", "one", "more", "new", "for", "let's", "lets", "us", "now",
    "time", "storytime", "story",
    "tell", "read", "say", "give", "share", "start",
}  # fmt: skip
_CHARACTER_NAME_WORDS = {
    word for c in CHARACTERS.values() for word in (*c.name.lower().split(), c.id)
}


def _is_generic_story_request(text: str) -> bool:
    text = text.strip()
    if not text or _TOPIC_HINT_RE.search(text):
        return False
    words = re.findall(r"[a-z']+", text.lower())
    if "story" not in words and "storytime" not in words:
        return False
    allowed = _STORY_FILLER_WORDS | _CHARACTER_NAME_WORDS
    return all(w in allowed for w in words)


def _latest_user_text(chat_ctx: llm.ChatContext) -> str | None:
    for item in reversed(chat_ctx.items):
        if item.type != "message":
            continue
        return item.text_content if item.role == "user" else None
    return None


def _gallery_key(story: StoryExample) -> str:
    return f"{story.language}:{story.title}"


async def _frames_to_async_iter(frames: list[rtc.AudioFrame]) -> AsyncIterable[rtc.AudioFrame]:
    for frame in frames:
        yield frame


# Stated, never asked as a question — she shouldn't have to choose.
GALLERY_INTROS: dict[str, list[str]] = {
    "red": [
        "Hmph. Let me dig up one of my favorite stories from the gallery for you.",
        "Fine, fine — I've got a good one saved up in my gallery. Here we go.",
    ],
    "blue": [
        "Ooh, ooh! Let me grab one of my favorite stories from the gallery!",
        "I know just the one — pulling it straight from my story gallery!",
    ],
    "pink": [
        "Let me pick one of my favorite stories from the gallery for you.",
        "Oh, I have just the story saved in my gallery for you, sweet friend.",
    ],
}

# (short filler, longer filler) played if the real LLM takes >3s / >5s to
# start replying — pre-rendered to cached audio at startup (_warm_up_filler_audio)
# so playing one is instant, not another TTS call.
FILLER_DELAYS = (3.0, 5.0)
FILLER_LINES: dict[str, tuple[str, str]] = {
    "red": (
        "Hmph... let me think.",
        "Hmph, that is a tricky one... let me think, let me think... fine, I will "
        "have an even better story for you in just a moment.",
    ),
    "blue": (
        "Ooh, let me think!",
        "Whoa, that's a tricky one! Let me think, let me think... hang on, I'm "
        "cooking up something even better for you!",
    ),
    "pink": (
        "Hmm, let me think, sweet friend.",
        "Oh, that's a wonderful but tricky one... let me think, let me think... "
        "I promise, an even better story is coming.",
    ),
}


class VoiceIdState:
    """Session-scoped bridge between the raw-audio tap in my_agent() (which
    computes an embedding per utterance) and the Assistant's remember_name
    tool below (which is what actually knows the name to save it under).
    The LLM never sees the embedding itself — only that a name was given."""

    def __init__(self) -> None:
        self.latest_embedding: list[float] | None = None


class Assistant(Agent):
    def __init__(
        self,
        character: Character,
        language: str = "en",
        custom_story: str = "",
        story_examples: list[StoryExample] | None = None,
        voice_id: VoiceIdState | None = None,
    ) -> None:
        super().__init__(
            instructions=instructions_for(character, language, custom_story, story_examples)
        )
        self._voice_id = voice_id
        self._character = character
        self._language = language
        self._custom_story = custom_story
        self._told_gallery_stories: set[tuple[str, str]] = set()
        # Keyed by text, not a single scalar, so overlapping preemptive generations can't cross-contaminate.
        self._pending_gallery_stories: dict[str, StoryExample] = {}
        # Set by _wire_voice_id on a recognized returning child; makes the next turn use the real LLM.
        self._pending_recognition_greeting = False

    @function_tool
    async def remember_name(self, name: str) -> str:
        """Call this the moment she states or confirms her name for the
        first time in this conversation, so her voice can be recognized and
        she can be greeted by name next time. Pass exactly the name she
        gave, nothing else."""
        name = name.strip()
        if self._voice_id is not None and self._voice_id.latest_embedding is not None and name:
            known_speakers.enroll(name, self._voice_id.latest_embedding)
            logger.info("enrolled voice for name=%s", name)
        return f"Got it — I'll remember {name}."

    async def _pick_gallery_story(self, chat_ctx: llm.ChatContext) -> StoryExample | None:
        # A custom story or a pending recognition greeting must reach the real LLM, never shortcut.
        if self._language != "en" or self._custom_story:
            return None
        if self._pending_recognition_greeting:
            self._pending_recognition_greeting = False
            return None
        text = _latest_user_text(chat_ctx)
        matched = text is not None and _is_generic_story_request(text)
        logger.info("gallery_story_check text=%r matched=%s", text, matched)
        if not matched:
            return None
        examples = await asyncio.to_thread(load_story_examples)
        candidates = [
            s
            for s in examples
            if s.language == "en" and (s.language, s.title) not in self._told_gallery_stories
        ]
        if not candidates:
            return None
        # Least-told-overall first (persisted, see story_gallery_state.py); ties random.
        counts = await asyncio.to_thread(story_gallery_state.load_counts)
        least_told = min(counts.get(_gallery_key(s), 0) for s in candidates)
        least_told_candidates = [s for s in candidates if counts.get(_gallery_key(s), 0) == least_told]
        return random.choice(least_told_candidates)

    async def llm_node(
        self,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool],
        model_settings: ModelSettings,
    ) -> AsyncIterable[str]:
        """Bare story ask: skip the LLM, recite a gallery story. Anything else: normal LLM turn."""
        story = await self._pick_gallery_story(chat_ctx)
        if story is None:
            async for chunk in self._llm_node_with_fillers(chat_ctx, tools, model_settings):
                yield chunk
            return

        intro = random.choice(
            GALLERY_INTROS.get(
                self._character.id,
                ["Let me pick one of my favorite stories from the gallery for you."],
            )
        )
        text = f"{intro}\n\n{story.body}"
        # Not "told" yet — tts_node marks it once actually synthesized (see below).
        self._pending_gallery_stories[text] = story
        yield text

    async def tts_node(
        self, text: AsyncIterable[str], model_settings: ModelSettings
    ) -> AsyncIterable[rtc.AudioFrame]:
        """Replay cached audio for gallery text (see llm_node) instead of
        re-synthesizing it every time it's told. Anything else: normal TTS.

        Matches purely on the text this call actually receives, not on
        shared instance state set by a possibly-unrelated llm_node call, so
        overlapping preemptive generations can't cross-contaminate which
        turn's audio gets played.
        """
        it = text.__aiter__()
        try:
            first_chunk = await it.__anext__()
        except StopAsyncIteration:
            return

        story = self._pending_gallery_stories.pop(first_chunk, None)
        if story is None:

            async def _rechain() -> AsyncIterable[str]:
                yield first_chunk
                async for chunk in it:
                    yield chunk

            async for frame in Agent.default.tts_node(self, _rechain(), model_settings):
                yield frame
            return

        self._told_gallery_stories.add((story.language, story.title))
        await asyncio.to_thread(story_gallery_state.record_told, _gallery_key(story))

        voice = self._character.tts_voice
        cached = await asyncio.to_thread(gallery_audio_cache.load, voice, first_chunk)
        if cached is not None:
            logger.info("gallery audio cache hit")
            for frame in cached:
                yield frame
            return

        logger.info("gallery audio cache miss; synthesizing and caching")

        async def _one_chunk() -> AsyncIterable[str]:
            yield first_chunk

        frames: list[rtc.AudioFrame] = []
        async for frame in self._race_first_item_with_fillers(
            Agent.default.tts_node(self, _one_chunk(), model_settings)
        ):
            frames.append(frame)
            yield frame
        await asyncio.to_thread(gallery_audio_cache.save, voice, first_chunk, frames)

    async def _race_first_item_with_fillers(self, agen: AsyncIterable[T]) -> AsyncIterable[T]:
        """Yield everything from agen, but say a cached filler line (see
        FILLER_LINES) if the first item hasn't arrived by 3s/5s, so she
        isn't hearing dead air. Shared by the real-LLM path (racing the
        first text chunk) and a gallery cache-miss (racing the first audio
        frame from Kokoro) — both are "something slow is about to start
        speaking" the same way."""
        it = agen.__aiter__()
        start = time.monotonic()
        deadlines = [start + delay for delay in FILLER_DELAYS]
        stage = 0
        task = asyncio.ensure_future(it.__anext__())
        try:
            while True:
                timeout = max(0.0, deadlines[stage] - time.monotonic()) if stage < len(deadlines) else None
                try:
                    first_item = (
                        await task if timeout is None else await asyncio.wait_for(asyncio.shield(task), timeout)
                    )
                    break
                except asyncio.TimeoutError:
                    self._say_filler(stage)
                    stage += 1
                except StopAsyncIteration:
                    return
        finally:
            if not task.done():
                task.cancel()

        yield first_item
        async for item in it:
            yield item

    async def _llm_node_with_fillers(
        self,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool],
        model_settings: ModelSettings,
    ) -> AsyncIterable[str]:
        """Real LLM turn, with filler coverage — see _race_first_item_with_fillers."""
        gen = Agent.default.llm_node(self, chat_ctx, tools, model_settings)
        async for chunk in self._race_first_item_with_fillers(gen):
            yield chunk

    def _say_filler(self, stage: int) -> None:
        lines = FILLER_LINES.get(self._character.id, ())
        if stage >= len(lines):
            return
        text = lines[stage]
        cached = gallery_audio_cache.load(self._character.tts_voice, text)
        audio_kwargs = {"audio": _frames_to_async_iter(cached)} if cached is not None else {}
        self.session.say(text, allow_interruptions=True, add_to_chat_ctx=False, **audio_kwargs)


server = AgentServer()

# Keeps fire-and-forget tasks (e.g. the time-limit cutoff below) alive —
# asyncio only holds a weak ref otherwise.
_background_tasks: set[asyncio.Task] = set()


# Generous: covers a slow first-run model download, not just a normal warm-up.
_STALE_LOCK_AFTER_SECONDS = 600.0


def _run_once_across_processes(lock_name: str, fn: Callable[[], None]) -> None:
    """Run fn() at most once across LiveKit's several prewarmed worker
    processes (they share the models volume, so one succeeding is enough).
    Self-heals a lock left behind by a process killed mid-run — otherwise a
    single hard kill would permanently disable this warm-up on that volume.
    """
    lock_path = gallery_audio_cache.cache_dir() / lock_name
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if time.time() - lock_path.stat().st_mtime > _STALE_LOCK_AFTER_SECONDS:
            lock_path.unlink(missing_ok=True)
    except FileNotFoundError:
        pass

    try:
        os.close(os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except FileExistsError:
        return

    try:
        fn()
    finally:
        lock_path.unlink(missing_ok=True)


def _warm_up_llm() -> None:
    """Prime llama-server's prompt cache with each character's system prompt.

    Measured on a persona-length system prompt: a cold KV cache costs ~3-6s
    of prompt processing before the first token, entirely from re-reading the
    system prompt — llama-server caches prompt prefixes per slot, so sending
    each one once here means whichever character the child picks, the real
    first greeting only pays for the few new tokens in the actual request.
    Skipped for non-loopback LLAMA_BASE_URL (a remote/cloud LLM has no local
    cold-cache problem and this would just spend real API calls for nothing).
    """
    llama_base_url = os.getenv("LLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
    if not any(host in llama_base_url for host in ("127.0.0.1", "localhost")):
        return

    def _do() -> None:
        llama_model = os.getenv("LLAMA_MODEL", "gemma-4-e2b")
        llama_api_key = os.getenv("LLAMA_API_KEY", "no-key-needed")

        deadline = time.monotonic() + 180.0
        for character in CHARACTERS.values():
            while time.monotonic() < deadline:
                try:
                    httpx.post(
                        f"{llama_base_url}/chat/completions",
                        json={
                            "model": llama_model,
                            "messages": [
                                {"role": "system", "content": character.instructions},
                                {"role": "user", "content": "Hi"},
                            ],
                            "max_tokens": 1,
                        },
                        headers={"Authorization": f"Bearer {llama_api_key}"},
                        timeout=30.0,
                    ).raise_for_status()
                    logger.info("llm warm-up complete: %s", character.id)
                    break
                except httpx.HTTPError:
                    time.sleep(1.0)
            else:
                logger.warning("llm warm-up gave up waiting for the LLM server")
                return

    _run_once_across_processes(".llm-warmup.lock", _do)


def _warm_up_filler_audio() -> None:
    """Pre-render each character's FILLER_LINES to gallery_audio_cache so
    _say_filler never has to synthesize live. Skipped for non-loopback
    TTS_BASE_URL, same reasoning as _warm_up_llm.
    """
    tts_base_url = os.getenv("TTS_BASE_URL", "http://127.0.0.1:8880/v1")
    if not any(host in tts_base_url for host in ("127.0.0.1", "localhost")):
        return

    def _do() -> None:
        tts_api_key = os.getenv("TTS_API_KEY", "no-key-needed")
        tts_speed = float(os.getenv("TTS_SPEED", "0.9"))

        # One shared budget across all lines, not per-line — a line that
        # times out just gets skipped (retried next boot) instead of
        # abandoning every line after it.
        deadline = time.monotonic() + 300.0
        for character in CHARACTERS.values():
            for text in FILLER_LINES.get(character.id, ()):
                if gallery_audio_cache.load(character.tts_voice, text) is not None:
                    continue
                while time.monotonic() < deadline:
                    try:
                        resp = httpx.post(
                            f"{tts_base_url}/audio/speech",
                            json={
                                "model": "tts-1",
                                "input": text,
                                "voice": character.tts_voice,
                                "response_format": "wav",
                                "speed": tts_speed,
                            },
                            headers={"Authorization": f"Bearer {tts_api_key}"},
                            timeout=30.0,
                        )
                        resp.raise_for_status()
                        gallery_audio_cache.save_wav_bytes(character.tts_voice, text, resp.content)
                        break
                    except httpx.HTTPError:
                        time.sleep(1.0)
                else:
                    logger.warning("filler audio warm-up gave up on %r for %s", text, character.id)
        logger.info("filler audio warm-up finished")

    _run_once_across_processes(".filler-warmup.lock", _do)


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()
    # Warming up all 3 characters can take well past livekit-agents' own
    # process-pool init timeout (each cold llama-server request costs
    # several seconds — see _warm_up_llm's docstring), which was causing
    # prewarmed worker processes to be killed and endlessly respawned before
    # ever reporting ready. Run it on a background thread instead: VAD
    # loading alone is fast enough that the pool handshake completes
    # normally, and the LLM cache still ends up warm shortly after.
    threading.Thread(target=_warm_up_llm, daemon=True).start()
    threading.Thread(target=_warm_up_filler_audio, daemon=True).start()


server.setup_fnc = prewarm


def _wire_voice_id(
    ctx: JobContext,
    assistant: "Assistant",
    voice_id_state: VoiceIdState,
    character: Character,
) -> None:
    """Tap the child's raw mic audio in parallel with (not instead of) the
    normal STT/VAD pipeline, to compute a voice embedding per utterance —
    see local_voice_ai/speaker_id.py. A second, independent
    ``rtc.AudioStream``/``VADStream`` on the same track is exactly the
    pattern livekit-agents' own RoomIO uses internally to feed STT, so this
    doesn't disturb or duplicate anything in the existing pipeline.

    Only the very first utterance of the session is checked against known
    voices (recognition); every utterance after that just refreshes
    ``voice_id_state.latest_embedding`` so Assistant.remember_name has
    something fresh to enroll under whatever name she gives.
    """
    state = {"checked_first_utterance": False}
    # asyncio only holds a weak reference to a task once nothing else does,
    # which can garbage-collect it mid-run — this keeps a live reference for
    # as long as the per-utterance consumer task is running.
    background_tasks: set[asyncio.Task] = set()

    async def _consume_utterances(track: rtc.Track) -> None:
        from livekit.agents import vad as vad_module

        vad_stream = ctx.proc.userdata["vad"].stream()

        async def _feed() -> None:
            audio_stream = rtc.AudioStream.from_track(
                track=track, sample_rate=16000, num_channels=1
            )
            try:
                async for event in audio_stream:
                    vad_stream.push_frame(event.frame)
            finally:
                vad_stream.end_input()

        feed_task = asyncio.create_task(_feed())
        try:
            async for event in vad_stream:
                if event.type != vad_module.VADEventType.END_OF_SPEECH:
                    continue
                embedding = speaker_id.frames_to_embedding(event.frames)
                if embedding is None:
                    continue
                voice_id_state.latest_embedding = embedding

                if state["checked_first_utterance"]:
                    continue
                state["checked_first_utterance"] = True
                match = known_speakers.find_best_match(embedding)
                if match is None:
                    continue
                logger.info("recognized returning voice: %s", match.name)
                new_ctx = assistant.chat_ctx.copy()
                new_ctx.add_message(
                    role="system",
                    content=(
                        f"You recognize her voice from a previous visit — her name "
                        f"is {match.name}. Warmly greet her by name and reference "
                        f"that she's back, staying fully in character as "
                        f"{character.name}. Do not ask for her name again."
                    ),
                )
                assistant.update_chat_ctx(new_ctx)
                assistant._pending_recognition_greeting = True
        finally:
            feed_task.cancel()

    def _on_track_subscribed(
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        if publication.source != rtc.TrackSource.SOURCE_MICROPHONE:
            return
        task = asyncio.create_task(_consume_utterances(track))
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)

    ctx.room.on("track_subscribed", _on_track_subscribed)


async def _enforce_time_limit(
    ctx: JobContext,
    session: AgentSession,
    character: Character,
    language: str,
    time_limit_minutes: int,
) -> None:
    """Server-side backstop for the parent time limit — the client's own
    countdown timer is cooperative only; this ends the room regardless."""
    try:
        await asyncio.sleep(time_limit_minutes * 60)
    except asyncio.CancelledError:
        return

    language_names = {"te": "Telugu", "mr": "Marathi"}
    goodbye_language_hint = (
        f" Say this goodbye itself in {language_names[language]}, not English."
        if language in language_names
        else ""
    )
    try:
        handle = session.generate_reply(
            instructions=(
                "Playtime is over for now. Warmly say a short, gentle goodbye, "
                f"staying fully in character as {character.name} — one or two "
                "sentences, like tucking her in for later, not an abrupt "
                f"announcement.{goodbye_language_hint}"
            )
        )
        await asyncio.wait_for(handle.wait_for_playout(), timeout=20.0)
    except Exception:
        logger.exception("time-limit goodbye failed; ending the session anyway")

    logger.info("session time limit (%s min) reached; deleting room", time_limit_minutes)
    await ctx.delete_room()


@server.rtc_session()
async def my_agent(ctx: JobContext) -> None:
    ctx.log_context_fields = {"room": ctx.room.name}

    # The frontend's character picker sends its choice as JSON room metadata
    # (see api.py::_mint_token). ctx.job.room reflects the room as created at
    # token-mint time, so this is available before ctx.connect(). No metadata
    # (e.g. `console` mode) falls back to the default character.
    room_metadata: dict[str, str] = {}
    raw_metadata = getattr(ctx.job.room, "metadata", "") or ""
    if raw_metadata:
        try:
            room_metadata = json.loads(raw_metadata)
        except (json.JSONDecodeError, TypeError):
            logger.warning("could not parse room metadata: %r", raw_metadata)

    character_id = room_metadata.get("character")
    character = get_character(character_id)
    # Language selection (e.g. "te", "mr"). STT stays English/Nemotron
    # regardless for now — she's learning Telugu/Marathi by hearing it, not
    # necessarily speaking it yet — only the LLM's output language and TTS
    # voice change.
    language = room_metadata.get("language", "en")
    custom_story = room_metadata.get("story", "")
    logger.info("character=%s language=%s custom_story=%s", character.id, language, bool(custom_story))

    llama_model = os.getenv("LLAMA_MODEL", "gemma-4-e2b")
    llama_base_url = os.getenv("LLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
    llama_api_key = os.getenv("LLAMA_API_KEY", "no-key-needed")

    stt_provider = os.getenv("STT_PROVIDER", "nemotron").lower()
    if stt_provider == "whisper":
        default_stt_base_url = "http://127.0.0.1:8000/v1"
        default_stt_model = "Systran/faster-whisper-small"
    else:
        default_stt_base_url = "http://127.0.0.1:8000/v1"
        default_stt_model = "nemotron-speech-streaming"

    stt_base_url = os.getenv("STT_BASE_URL", default_stt_base_url)
    stt_model = os.getenv("STT_MODEL", default_stt_model)
    stt_api_key = os.getenv("STT_API_KEY", "no-key-needed")

    indic_tts_enabled = os.getenv("ENABLE_INDIC_TTS", "").strip().lower() in {"1", "true", "yes", "on"}
    if language in ("te", "mr") and indic_tts_enabled:
        # MMS ships one base voice per language; indic_tts pitch-shifts it
        # per character (see services/indic_tts's PITCH_SHIFTS_SEMITONES) so
        # Red/Blue/Rosie still sound distinct.
        tts_base_url = os.getenv("INDIC_TTS_BASE_URL", "http://127.0.0.1:8881/v1")
        tts_voice = f"{language}-{character.id}"
    else:
        if language in ("te", "mr"):
            logger.warning(
                "language=%s requested but ENABLE_INDIC_TTS is off; falling back to English TTS",
                language,
            )
            language = "en"
        tts_base_url = os.getenv("TTS_BASE_URL", "http://127.0.0.1:8880/v1")
        # A character picked via the frontend always wins; TTS_VOICE only
        # matters as a fallback when there's no room metadata to pick a
        # character from (e.g. `console` mode).
        tts_voice = (
            character.tts_voice if character_id else os.getenv("TTS_VOICE", character.tts_voice)
        )
    tts_api_key = os.getenv("TTS_API_KEY", "no-key-needed")
    # Kokoro's default pace reads a little quick/flat for storytelling —
    # slightly slower gives pauses and drawn-out words (see characters.py's
    # "sounding human" rules) more room to actually land.
    tts_speed = float(os.getenv("TTS_SPEED", "0.9"))

    logger.info(
        "agent session: character=%s language=%s stt=%s/%s llm=%s/%s tts=%s/%s",
        character.id, language, stt_provider, stt_model, llama_base_url, llama_model,
        tts_base_url, tts_voice,
    )

    wake_word = os.getenv("WAKE_WORD", "").strip().lower() in {"1", "true", "yes", "on"}
    wake_word_model = os.getenv("WAKE_WORD_MODEL", "/app/models/wakeword/hey_livekit.onnx")
    wake_word_threshold = float(os.getenv("WAKE_WORD_THRESHOLD", "0.5"))

    # On by default (unlike WAKE_WORD/ENABLE_INDIC_TTS) — recognizing a
    # returning child and greeting her by name is the whole point of this
    # feature, so it should just work out of the box; still overridable.
    voice_id_enabled = os.getenv("VOICE_ID_ENABLED", "true").strip().lower() in {
        "1", "true", "yes", "on",
    }

    session = AgentSession(
        stt=openai.STT(base_url=stt_base_url, model=stt_model, api_key=stt_api_key),
        llm=openai.LLM(base_url=llama_base_url, model=llama_model, api_key=llama_api_key),
        # The model name selects the wire protocol the openai TTS plugin uses:
        # only {"tts-1", "tts-1-hd"} use the raw-audio-bytes stream that the
        # Kokoro server speaks. Any other name (e.g. "kokoro") routes the plugin
        # into the gpt-4o-mini-tts SSE reader, which parses Kokoro's binary audio
        # body as text, pushes zero frames, and raises "no audio frames were
        # pushed". Kokoro ignores the model field, so "tts-1" is purely a
        # protocol selector here. response_format=wav skips Kokoro's lossy mp3
        # encode step (measured ~140ms saved per utterance, no quality cost
        # over a LAN).
        tts=openai.TTS(
            base_url=tts_base_url,
            model="tts-1",
            voice=tts_voice,
            api_key=tts_api_key,
            response_format="wav",
            speed=tts_speed,
        ),
        # English-only model: smaller and faster than MultilingualModel, and
        # STT stays English/Nemotron regardless of the agent's reply
        # language (see the language comment above), so the child's turns
        # are always English.
        turn_detection=EnglishModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    story_examples = sample_story_examples(language)
    voice_id_state = VoiceIdState() if voice_id_enabled else None
    assistant = Assistant(character, language, custom_story, story_examples, voice_id=voice_id_state)
    await session.start(agent=assistant, room=ctx.room)
    await ctx.connect()

    # See _enforce_time_limit — hard server-side cutoff, not just the
    # client's countdown.
    time_limit_minutes = load_settings().time_limit_minutes
    if time_limit_minutes and time_limit_minutes > 0:
        time_limit_task = asyncio.create_task(
            _enforce_time_limit(ctx, session, character, language, time_limit_minutes)
        )
        _background_tasks.add(time_limit_task)
        time_limit_task.add_done_callback(_background_tasks.discard)

    # Restated here, not just in the system prompt: the model otherwise
    # tends to match the (English) language of this very instruction for
    # the greeting specifically, opening in English before switching to the
    # target language mid-reply.
    language_names = {"te": "Telugu", "mr": "Marathi"}
    greeting_language_hint = (
        f" Say this greeting itself in {language_names[language]}, not English."
        if language in language_names
        else ""
    )

    # Native apps (tab-app, phone-app) send a small "check_in" data message
    # after their own client-side idle timer fires (they can't tell on their
    # own whether she's just quiet vs. actually gone — only the server sees
    # real speech activity via STT/VAD). Only the agent verbally asking
    # counts as a real check — a client-only silent prompt wouldn't need
    # this at all.
    @ctx.room.on("data_received")
    def _on_data_received(packet) -> None:
        if packet.topic != "check_in":
            return
        session.generate_reply(
            instructions=(
                "It's been quiet for a while. Warmly and briefly check if "
                f"she's still there, staying fully in character as "
                f"{character.name} — one short sentence, like a caring "
                f"friend checking in, not an alarm.{greeting_language_hint}"
            )
        )

    if voice_id_state is not None:
        _wire_voice_id(ctx, assistant, voice_id_state, character)

    if wake_word:
        # Join deaf, wait for the wake phrase, then wake up and greet.
        from .wakeword import wait_for_wake_word

        session.input.set_audio_enabled(False)
        participant = await ctx.wait_for_participant()
        try:
            await wait_for_wake_word(participant, wake_word_model, wake_word_threshold)
        except Exception:
            # Fail open: a broken detector shouldn't brick the assistant.
            logger.exception("wake word detection failed; enabling audio input")
        session.input.set_audio_enabled(True)
        session.generate_reply(
            instructions=(
                "You just woke up because she said the wake phrase. Greet her very "
                f"briefly, staying fully in character as {character.name}, and ask "
                f"if she'd like to hear a story.{greeting_language_hint}"
            )
        )
    else:
        # Speak first so the user knows the audio path works.
        session.generate_reply(
            instructions=(
                "Greet the child warmly in one short, cheerful sentence, staying "
                f"fully in character as {character.name}, and ask if she'd like to "
                f"hear a story.{greeting_language_hint}"
            )
        )


if __name__ == "__main__":
    cli.run_app(server)
