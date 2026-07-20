# Client-side voice (native STT/TTS) — plan & status

> **Superseded — this direction was not pursued.** A later session kept
> LiveKit/WebRTC in both native apps (it was never dropped) and instead
> shipped a different feature: server-side voice recognition (recognizing a
> returning child by voice and greeting her by name — see the main README's
> "Voice recognition" section, `local_voice_ai/speaker_id.py` /
> `known_speakers.py`), plus a full Canvas-drawn animated mascot in
> `tab-app`/`phone-app` (`ui/Mascot.kt`, `ui/BalloonField.kt`). None of the
> `SpeechRecognizer`/on-device-`TextToSpeech`/WebSocket-relay architecture
> below was built, and Kokoro/LiveKit remain exactly as they were before
> this doc was written. Kept here for the historical reasoning (in case this
> direction is revisited later), not as a description of the current app.

Written because we're deep into a session (~74%+ of budget used when this
was started) and wanted a clear checkpoint: what's decided, what's built,
what's not, and exactly what to do next when picking this back up.

## The decision, in one paragraph

Shift both speech-to-text (STT) and text-to-speech (TTS) from the server to
the native Android apps (`tab-app`, `phone-app`). The server keeps doing
**only** the LLM. This means native-app sessions stop using LiveKit/WebRTC
entirely — no more `io.livekit:livekit-android` dependency (which was the
most fragile part of building the apps: JitPack repo, OkHttp version
conflict, Kotlin/serialization version mismatch, all debugged and working,
but all now dead weight for this direction) — replaced by one WebSocket
carrying JSON text both ways, plus Android's built-in `SpeechRecognizer`
(STT) and `TextToSpeech` (TTS), both zero extra dependencies.

**The web app is explicitly out of scope for all of this and must not
change.** It keeps using LiveKit + Kokoro/MMS exactly as it does today.

## Why (the actual reasoning, not just "faster")

- Moving TTS off the server frees real CPU for the LLM on this CPU-only
  box (`LLAMA_N_GPU_LAYERS=0`) — STT, LLM, and TTS currently compete for
  the same cores. That's the genuine source of any speedup, **not** network
  transport savings (WebRTC audio over LAN was never the bottleneck —
  Opus is tens of kbps, negligible on home Wi-Fi).
- Full symmetry (device does both ears and mouth) removes the need for
  LiveKit/WebRTC on native sessions at all, which is a real simplification,
  not just a performance tweak.
- Real risk, not yet resolved: `SpeechRecognizer`'s on-device/offline
  guarantee **varies by device and Android version** — some paths silently
  fall back to Google's cloud speech API. This project's whole premise is
  "nothing leaves the house." The plan is to explicitly request on-device
  recognition (`createOnDeviceSpeechRecognizer`, API 31+) and **fail loudly
  rather than silently fall back to cloud** — but whether the actual
  Samsung tablet/phone truly supports offline recognition needs real-device
  testing. **Not yet verified.**

## Architecture (target end state)

```
Native apps (tab-app, phone-app):
  mic → Android SpeechRecognizer (on-device) → text
      → WebSocket → server
  server → LLM (llama-server, same as today) → text, streamed per-sentence
      → WebSocket → app
  app → punctuation/symbol-aware translator → SSML → Android TextToSpeech → speaker

Web app (unchanged):
  mic → LiveKit/WebRTC → server STT (Nemotron/Whisper) → LLM → server TTS
      (Kokoro/MMS) → LiveKit/WebRTC → browser speaker
```

New server component: a plain FastAPI WebSocket endpoint (not yet built —
see Status below), separate from the existing LiveKit-based `/api/*`
routes. Per connection: holds conversation history in memory, reuses
`instructions_for()` as-is (character + language + custom_story +
story_examples — all already built, see below), streams the LLM's reply
**sentence by sentence** as each sentence finishes (not the whole reply at
once) — this preserves the same "start speaking before the full reply is
ready" pipelining property LiveKit's TTS streaming already gives the web
app today. Losing that would make the native app feel slower to first
sound even with lower total compute.

## The modulation "code language" (defined, not yet built into the translator)

The LLM is taught (via prompt instructions, see `_SHARED_RULES` in
`characters.py`) to use a **small, fixed, deliberate** set of symbols to
signal modulation — not just generic prose punctuation reinterpreted after
the fact. A deterministic translator (pure code, unit-testable without any
device or LLM) converts these into Android SSML. The translator is the
safety net: it always produces valid SSML even if the LLM forgets a
convention and just writes plain prose.

| Symbol | Meaning | SSML translation |
| --- | --- | --- |
| `.` | Normal sentence end | `<break time="350ms"/>` |
| `,` | Short breath | `<break time="150ms"/>` |
| `...` | Real dramatic pause — before something surprising/exciting/sweet | `<break time="800ms"/>` |
| `--` (double hyphen) | Short interruption / abrupt stop | `<break time="250ms"/>` |
| `!` | Excitement — wraps the sentence | `<prosody pitch="+15%" rate="110%">…</prosody>` |
| `?` | Question — wraps the sentence | `<prosody pitch="+10%">…</prosody>` (rising contour) |
| `*word*` | Deliberate emphasis on one word | `<emphasis level="strong">word</emphasis>` |
| Stretched spelling, e.g. `sooooo`, `waaay` | Drawn-out/slow delivery | `<prosody rate="70%">word</prosody>` (repeated-letter run collapsed back to normal spelling inside the tag) |

Parsing order matters: stretched-spelling and `*emphasis*` are word-level
and apply first (innermost), sentence-level wrappers (`!`/`?`) apply around
the whole sentence after that, and pause symbols (`.`/`,`/`...`/`--`)
insert `<break>` between segments rather than wrapping anything.

## Status: what's actually built vs. only planned

**Built, tested, working (verify with `uv run pytest tests/ -q` — 113
passing as of this doc):**
- `story_examples.py` — parser for `story_examples.md` (categories,
  per-story language tags `[te]`/`[mr]`, capped sampling: 1 story per
  category, max 4 categories per session, so prompt size stays bounded
  regardless of how many stories get added).
- `story_examples.md` — 13 original stories (not copied from anywhere —
  the moonzia.com request and the `kindergarten_150_stories.pdf` request
  were both declined for copyright reasons; these are freshly written,
  covering Animals & Nature, Silly & Funny, Adventure & Exploring, Gentle
  Bedtime, Sharing & Kindness, Feelings & Patience, Helping Friends,
  Listening & Following Directions). Telugu/Marathi translations exist for
  the first category only (Animals & Nature) — **not yet done for the
  other seven categories**, since translating original work is fine
  (it's ours) but is real effort per story, deprioritized when the
  conversation moved to the client-TTS architecture work.
- `characters.py` — `instructions_for()` now takes `story_examples`,
  builds the "ask which category, then be creative, don't repeat"
  directive. TTS pacing/expressiveness rules added to `_SHARED_RULES`
  (short bursts, deliberate `...`, varied sentence length) — this part
  already benefits the **web app too** (it's prompt-level, not
  architecture-level, so Kokoro's output should already sound less flat).
- `agent.py` — wired to actually call `sample_story_examples(language)`
  and pass it through to `Assistant()` (this was missing until just now —
  the parser and prompt-builder existed but nothing called them).
- `docker-compose.yml` — `story_examples.md` bind-mounted read-only into
  the container (also missing until just now) so edits take effect on the
  next session with no rebuild.
- 3-character roster (Red One, Blue Bolt, Rosie) — **still 3, not yet
  the discussed 10**. Expanding this needs 7 new personas + a `voice_type`
  field (male/female/child) added to the `Character` dataclass, used by
  native apps to pick a matching on-device system voice.
- `wake-listener/` — host-side systemd service, apps can remotely
  `docker compose up -d`. Unrelated to voice but built this session.
- HTTPS via Caddy, `tab-app`/`phone-app` (LiveKit-based, pre-shift
  architecture) — all built and verified working this session, on the
  `native-speach` branch.

**Planned, NOT built yet:**
- ~~The punctuation→SSML translator itself~~ — this part actually exists
  (`local_voice_ai/voice_modulation.py`, 27 passing tests), just never
  wired into anything: nothing in `agent.py`/`characters.py` calls it, since
  the WebSocket/native-TTS architecture it was meant to feed was never built.
  An orphaned module, not a bug — safe to either delete or repurpose later.
- The new WebSocket endpoint on the server.
- `voice_type` field + 7 additional characters.
- Native app changes: `SpeechRecognizer` integration, `TextToSpeech`
  integration, WebSocket client, dropping the LiveKit SDK dependency.
- Any real-device verification of anything in this doc — none of it has
  been heard yet.

## Next steps, in order

1. Build the translator (`local_voice_ai/voice_modulation.py` or similar)
   implementing the symbol table above, with unit tests covering each
   symbol and combinations — pure string transforms, fully testable here,
   no device needed. **This is the safe, small, immediately-actionable
   next task.**
2. Define the 7 additional characters + `voice_type` field.
3. Build the WebSocket endpoint (reuses `instructions_for()`, adds
   per-sentence streaming and per-connection history/time-limit).
4. Native app side: `SpeechRecognizer` + `TextToSpeech` + WebSocket client,
   built in `tab-app` first, verified compiling the same way the LiveKit
   version was (Gradle + decompiled-API-verification approach), but
   **real audio behavior can only be confirmed on an actual device** —
   that verification is explicitly the user's to do, not something
   achievable in this environment (no Android SDK audio hardware, no
   emulator with reliable audio, confirmed earlier this session).
5. Once verified sounding right on one app, mirror to the second.

## Open questions for whoever picks this up

- Does the actual Samsung tablet/phone support genuine on-device
  `SpeechRecognizer`, or does it fall back to cloud? (Blocks the whole
  premise if it silently falls back — needs to fail loudly instead.)
- Does Samsung's TTS engine actually honor the SSML tags above
  (`<break>`, `<prosody>`, `<emphasis>`)? Google's engine generally does;
  Samsung's is unverified.
- 7 new character personas — need actual names/personalities decided
  (not yet discussed beyond "male/female/child" voice-type buckets).
