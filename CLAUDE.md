# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Story Teller: a voice storyteller app for young children (STT → LLM → TTS) that runs as **one container supervised by a single Python parent process**. There is no microservices orchestration layer — `local_voice_ai/supervisor.py` spawns and health-checks everything as plain subprocesses on loopback. Three fixed characters, English/Telugu/Marathi TTS, and a PIN-gated parent dashboard (session time limit, a custom story/lesson pasted in or extracted from a PDF) sit on top of that base. The Python package/module is still named `local_voice_ai` — only the project's external name changed.

For the system diagram, session-flow walkthrough, and the reasoning behind the major architecture calls, see [ARCH.md](ARCH.md) — this file covers dev commands and non-obvious gotchas, not design rationale.

## Commands

### Python (supervisor, agent, services)

```bash
uv pip install -e ".[ml,dev]"      # ml = torch/nemo/kokoro (heavy), dev = pytest/ruff
python -m local_voice_ai serve     # run the full supervised stack
python -m local_voice_ai console   # run just the agent worker in interactive console mode
python -m local_voice_ai download-models  # pre-download VAD/turn-detector/Nemotron weights

uv run pytest tests/ -q            # full test suite (matches CI)
uv run pytest tests/test_supervisor.py -q          # single file
uv run pytest tests/test_supervisor.py::test_name  # single test
ruff check .                       # lint (line-length 100, py310 target, E501 ignored)
```

CI runs against Python 3.11 specifically (`uv sync --frozen --extra dev -p 3.11`) — the lockfile targets 3.11 because 3.10 lacks wheels for some pins, even though `requires-python = ">=3.11"` and ruff's `target-version` is `py310`.

Local dev without Docker also needs the `livekit-server` and `llama-server` binaries on `PATH` (macOS: `brew install livekit llama.cpp`).

### Frontend (`frontend/`)

```bash
cd frontend
pnpm install
pnpm run dev              # next dev --turbopack
pnpm run build             # required to pass CI; also what produces the static export the supervisor serves
pnpm run lint
pnpm run format             # prettier --write .
pnpm run format:check
```

### Docker

```bash
docker compose up --build                                       # CPU build
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build   # NVIDIA overlay (CUDA llama.cpp + torch, GPU_LAYERS=999)
```

## Architecture

Everything is a child of `python -m local_voice_ai serve` (`local_voice_ai/__main__.py`):

```
python -m local_voice_ai serve
├── child: livekit-server      (Go binary; skipped if LIVEKIT_URL is non-loopback)
├── child: llama-server        (C++ binary; skipped if LLAMA_BASE_URL is non-loopback)
├── child: nemotron | whisper  (Python uvicorn; skipped if STT_BASE_URL is non-loopback)
├── child: kokoro              (Python uvicorn; skipped if TTS_BASE_URL is non-loopback)
├── child: livekit-agents worker (local_voice_ai/agent.py)
└── in-process: FastAPI on :8080
      ├── POST /api/connection-details  (LiveKit token minting)
      ├── GET  /api/status               (per-child readiness, for first-boot UI)
      └── GET  /*                        (serves the static Next.js export)
```

All children talk HTTP over `127.0.0.1` only. Four ports are exposed: `8080` (web), `7880`/`7881` (LiveKit signaling/TCP), `7882/udp` (WebRTC media).

### The "manage" pattern (`local_voice_ai/config.py`)

- Each service's `*_BASE_URL` decides ownership: loopback → supervisor spawns/owns the subprocess; remote → subprocess skipped, URL used directly (e.g. `LLAMA_BASE_URL` → OpenAI).
- `MANAGE_LIVEKIT` / `MANAGE_LLAMA` / `MANAGE_STT` / `MANAGE_TTS` override the auto-detection explicitly.
- `Config.from_env()` is the single source of truth for defaults — read it before touching any env-var-driven behavior.

### Key files

- `local_voice_ai/supervisor.py` — generic async process supervisor: spawns children, prefixes their stdout/stderr into the parent logger, polls `ready_url` for readiness, restarts a child that dies after becoming ready (linear backoff, capped by `max_restarts`), propagates SIGTERM/SIGINT for clean shutdown. Has no project-specific knowledge — it operates on `ChildSpec` objects.
- `local_voice_ai/__main__.py` — `_build_specs()` turns `Config` into the list of `ChildSpec`s (this is where each service's actual CLI invocation lives); `_serve()` wires the supervisor and the FastAPI app together on one event loop, with the web server intentionally starting *before* children are ready so `/api/status` can serve first-boot download progress instead of a dead page.
- `local_voice_ai/config.py` — env-driven `Config` dataclass shared by supervisor, agent, and API routes. Ported 1:1 into `agent_env()` for the agent subprocess's environment.
- `local_voice_ai/agent.py` — the LiveKit Agents worker (STT/LLM/TTS session wiring, wake-word gating, greeting logic, voice-recognition wiring). Talks to the STT/LLM/TTS children purely via their OpenAI-compatible HTTP APIs — it doesn't know or care whether they're local subprocesses or remote providers.
- `local_voice_ai/speaker_id.py` — voice-recognition embeddings, via NeMo's `titanet_small` speaker-verification model (already a dependency through the `ml` extra, used for Nemotron STT — no separate ML library added). Model loading is lazy so importing this module stays cheap for processes (like the FastAPI one) that never compute an embedding themselves.
- `local_voice_ai/known_speakers.py` — the enrolled `{name, voice embedding, enrolled-at}` store, mirroring `parent_settings.py`'s exact JSON-file-on-the-models-volume persistence idiom.
- `local_voice_ai/api.py` — FastAPI app: token minting (`_mint_token`), the PIN-gated parent-settings endpoints, PIN-gated known-speaker list/delete endpoints, and static frontend serving (SPA fallback to `index.html`).
- `local_voice_ai/services/{nemotron,whisper,kokoro}/server.py` — OpenAI-compatible uvicorn servers for each local inference backend.
- `frontend/` — Next.js app configured for **static export**; the export output is what `Config.frontend_dir` points FastAPI at in the container. There's no separate frontend server in production.
- `tab-app/`, `phone-app/` — native Android (Kotlin/Compose) clients for the same backend; see their own READMEs. Their `Mascot.kt`/`LiveKitManager.kt`/`CallScreen.kt` files are shared line-for-line between the two (same content, package name swapped) — port a fix to both in the same pass rather than re-discovering it twice.

### Non-obvious gotchas worth knowing before touching related code

- In `agent.py`, the TTS plugin is instantiated with `model="tts-1"` even though Kokoro ignores that field — it's a protocol selector for the `openai.TTS` plugin (only `{"tts-1", "tts-1-hd"}` use the raw-audio-bytes stream Kokoro speaks; anything else routes into an SSE reader that breaks against Kokoro's binary body).
- `llama-server` is launched with `--reasoning off` deliberately: for a voice agent, a thinking model's reasoning tokens are dead air before TTS gets any text.
- `--offline` for llama-server is auto-enabled once `_llama_repo_cached()` detects the HF repo is already in the local cache, so restarts work with no network while the first run is still free to download (`LLAMA_OFFLINE=1`/`0` overrides this).
- LiveKit's dev server needs an explicit `--node-ip` (`LIVEKIT_NODE_IP`, default `127.0.0.1`); without it, the dev server advertises its container-internal IP in ICE candidates, which a browser on the host can't reach, so WebRTC media silently never connects even though the room joins.
- The `whisper` optional-dependency extra deliberately does *not* use `vox-box` — it pins `aiofiles==23.2.1`, which conflicts with `livekit-agents`, so it could never coexist with the `ml` extra.
- Voice recognition (`speaker_id.py`) taps the child's raw mic audio via a **second, independent** `rtc.AudioStream.from_track(...)` plus a **second** `proc.userdata["vad"].stream()`, registered in `agent.py`'s own `room.on("track_subscribed", ...)` handler — this is the exact same pattern `livekit-agents`' own `RoomIO` uses internally to feed STT, just done a second time in parallel. It doesn't disturb or duplicate the existing STT/VAD/turn-detection pipeline; there's no public "tee my raw audio to me" API beyond replicating this primitive yourself.
- `AgentSession`'s `lk.agent.state` (listening/thinking/speaking) is driven by the internal generation/TTS-playout lifecycle, not by whether audio actually gets *published* to the room — so `RoomOutputOptions(audio_enabled=False)` (relevant if a text-only/native-TTS output mode is ever built) wouldn't break state transitions on its own.

## Environment variables

- Full reference: `.env` and the README's "Environment variables" section.
- Tests wipe all project-owned env vars before each run (`tests/conftest.py::_clean_env`), matching prefixes: `LIVEKIT_`, `LLAMA_`, `STT_`, `TTS_`, `MANAGE_`, `WEB_`, `DEVICE`, `NEMOTRON_`, `WHISPER_`, `WAKE_WORD`, `FRONTEND_DIR`, `KOKORO_`, `LOG_LEVEL`, `VOICE_ID_`, `KNOWN_SPEAKERS_`, `STORY_GALLERY_`.
- New env var → add its prefix to that list if it falls in one of these families.

## CI

`.github/workflows/ci.yml` — two jobs gate merges: `test` (pytest on 3.11), `frontend` (`pnpm run build`). A `docker` + `docker-merge` job pair only runs on pushes to `main`/tags — it builds amd64 and arm64 natively (no QEMU, since the ML stack would take hours emulated) and stitches the digests into one multi-arch manifest pushed to `ghcr.io/sooriyapsn/story-teller`.

`.github/workflows/android.yml` — builds `phone-app`/`tab-app` debug APKs on any push touching either directory, then (on `main`) republishes both as assets on a single fixed-tag release (`debug-latest`), overwritten each time — see either app's README for the resulting download links.
