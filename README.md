<div align="center">
  <h1>Story Teller</h1>
  <p>A self-hosted, local-only voice storyteller for kids — three characters to pick from, English/Telugu/Marathi, and a PIN-gated parent dashboard for time limits and custom lessons.</p>
  <p>Real-time voice AI — STT, LLM, TTS — running entirely in <strong>one container</strong> on your own network, supervised by a single Python parent process. Powered by <a href="https://docs.livekit.io/agents">LiveKit Agents</a>.</p>
</div>

## What this is for

Story Teller is built for one purpose: giving a young child (think preschool /
early-elementary age) a safe, screen-light way to hear stories and have simple
voice conversations with a character she picks — without a live person, a
cloud account, or an open-ended chatbot on the other end.

- **Kid-facing, voice-only.** No typing, no chat window, no video, no camera —
  she talks, a character talks back. Three fixed personalities (a grumpy-but-
  sweet bear, an energetic kid, and a gentle storyteller) each with their own
  voice, so it stays predictable and easy for a small child to navigate.
- **Bilingual by design.** English, Telugu, and Marathi — meant to help a kid
  hear and pick up a home language, not just default to English.
- **Parents stay in control.** A PIN-gated dashboard sets a play-time limit
  (the session ends itself), and lets a parent paste in or upload a specific
  story/lesson for the character to teach, so the content isn't just "whatever
  a generic LLM feels like saying."
- **Remembers her by voice.** The agent recognizes a returning child from her
  voice alone (no login, no UI) and greets her by name — see
  [Voice recognition](#voice-recognition). Best-effort, not a security
  feature, and off/on is controlled the same way as every other optional
  piece here.
- **Fully local and private.** Everything — speech recognition, the language
  model, text-to-speech — runs on your own hardware in one container. No
  conversation audio or transcript ever leaves your network, and it keeps
  working with no internet connection once the models are downloaded.

## Project history

This started as a fork of [ShayneP/local-voice-ai](https://github.com/ShayneP/local-voice-ai)
(itself built on LiveKit's generic `agent-starter-python`/`agent-starter-react`
templates for a general-purpose voice AI assistant — video, screen share, text
chat, the works). It's since been rewritten into a single-purpose kids' app:
the character system, bilingual TTS, the parent dashboard, and the voice-only
interaction model are all new, and the generic-assistant features that don't
apply here (camera, screen share, typed chat) have been removed. Very little
of the original template's UI or feature set remains — see the commit history
for the specifics.

## Overview

Everything runs as managed children of one Python supervisor (`python -m local_voice_ai serve`):

- **LiveKit server** (Go binary subprocess) for WebRTC signaling — skipped if `LIVEKIT_URL` points at LiveKit Cloud.
- **llama.cpp** (`llama-server` binary subprocess) for the LLM — default model is Gemma 4 E2B (quantization-aware-trained 4-bit, ~2.6 GB); swap it with `LLAMA_HF_REPO=org/repo:quant`. Skipped if `LLAMA_BASE_URL` points elsewhere.
- **Nemotron STT** or **Whisper (faster-whisper)** — Python uvicorn child, OpenAI-compatible.
- **Kokoro TTS** — Python uvicorn child, OpenAI-compatible.
- **LiveKit Agents worker** — the orchestrator child.
- **FastAPI** in the supervisor itself, serving `POST /api/connection-details` (token minting) and the statically-exported Next.js frontend.

Children speak HTTP only over `127.0.0.1`. The image exposes four ports: `8080` (web), `7880`, `7881`, `7882/udp` (LiveKit WebRTC, only if running locally).

## System requirements

Everything below is CPU-only by default; a GPU is optional (see [GPU (NVIDIA)](#gpu-nvidia)). Numbers marked "measured" come from `docker stats` on a real running instance with every child warm (STT + LLM + Kokoro TTS + Telugu/Marathi TTS all loaded at once) — that's the ceiling, not the typical moment-to-moment load. Numbers marked "estimated" are reasoned from the architecture (four concurrent inference services), not lab-tested against a range of hardware, since this project only runs on one dev machine.

**Hardware**

| Resource | Minimum | Recommended |
| --- | --- | --- |
| CPU | 4 cores, x86_64 with **AVX2** (any Intel/AMD from ~2013 onward) or Apple Silicon | 8+ cores — llama.cpp runs several parallel inference slots, and STT/LLM/TTS all do real work on the same turn |
| RAM | 8 GB (English-only, `STT_PROVIDER=whisper` with a small model) | 16 GB — measured ~11.5 GB RSS with Nemotron STT + Telugu/Marathi TTS all loaded |
| Disk | 20 GB free | 25 GB+ — ~6.5 GB Docker image, plus ~8 GB model weights (English-only: Nemotron + Kokoro + the default LLM) growing to ~10 GB with `ENABLE_INDIC_TTS=1` (adds Telugu + Marathi models) |
| Network | None required — fully offline after first-boot model download | — |

GPU acceleration (`docker-compose.gpu.yml`) needs an NVIDIA GPU with the [container toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) installed; VRAM needs scale with how much of the LLM you offload (`LLAMA_N_GPU_LAYERS`, default `999` = full offload for the ~2.6 GB default model).

**Software**

- Docker Engine + the Compose plugin (`docker compose`, not the standalone `docker-compose`) — this is the only supported path; see [Local development](#local-development-no-docker) for the non-Docker alternative.
- Linux or macOS. On Apple Silicon the prebuilt image runs natively but CPU-only (Docker Desktop's VM has no Metal passthrough) — for GPU inference on a Mac, use [Local development](#local-development-no-docker) instead, where `llama-server` picks up Metal automatically.
- amd64 and arm64 images are both published; no architecture-specific setup needed either way.

## Getting started

Run the prebuilt image (amd64 + arm64):

```bash
docker run --rm -it \
  -p 8080:8080 -p 7880:7880 -p 7882:7882/udp \
  -v story-teller-models:/models \
  ghcr.io/sooriyapsn/story-teller:latest
```

Or build from source (also the path for GPU builds):

```bash
docker compose up --build
```

Open <http://localhost:8080>. The first boot downloads the Nemotron + LLM weights — the page shows per-service progress with download sizes, and the terminal logs a compact status heartbeat plus an unmissable “ready” banner when everything is up. Weights are cached in the `models` volume, so later boots are fast and work offline.

### GPU (NVIDIA)

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

The overlay swaps in the CUDA llama.cpp binary + CUDA torch wheels, grants the
GPU to the container, and offloads the whole LLM (`LLAMA_N_GPU_LAYERS=999`,
override to partially offload). Requires the [NVIDIA container toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) —
verify with `docker run --gpus all ubuntu nvidia-smi`.

### Apple Silicon

The prebuilt image runs natively (arm64), but **CPU-only** — Docker on macOS is a
VM with no Metal access. For GPU (Metal) inference, run bare-metal via
[Local development](#local-development-no-docker) below, where `llama-server`
picks up Metal automatically.

## HTTPS

Off by default (plain HTTP, matching `docker run`/`docker compose up` above). For
a LAN deployment (laptop + a tablet on the same Wi-Fi — no public domain needed),
set `ENABLE_HTTPS=1` in `.env` and rebuild:

```bash
ENABLE_HTTPS=1  # add to .env, then:
docker compose up --build
```

This adds [Caddy](https://caddyserver.com/) as another supervised child, running
its own local CA and terminating TLS in front of the web/API traffic and LiveKit's
signaling connection — both on the *same* port numbers as before (`WEB_PORT`,
`LIVEKIT_BIND_PORT`), just now speaking `https`/`wss`. Nothing else about your
setup changes: same URLs, same ports, same `docker compose` commands.

**What HTTPS does and doesn't cover here:** voice audio itself is already
end-to-end encrypted regardless (WebRTC always encrypts media via DTLS-SRTP) —
what this actually protects is the web page, the API, and the parent PIN, which
otherwise travel as plain HTTP on your home Wi-Fi. The WebRTC media port
(`LIVEKIT_UDP_PORT`, default `7882/udp`) can't be hidden behind a reverse proxy
either way — that's inherent to how WebRTC works, not a Caddy limitation — so it
stays published as plain UDP, same as always. The RTC-over-TCP fallback port
(`7881`) is dropped from external publishing in HTTPS mode, since it's rarely
needed on a healthy LAN once the browser is already reaching everything else
over `wss`.

**One-time step per device:** because this is a local CA (not a real, publicly
trusted one — there's no domain to validate against), each browser will show a
"not secure" warning until you trust Caddy's root certificate once:

```bash
docker compose exec app cat /data/caddy/pki/authorities/local/root.crt
```

Copy that output to each device (laptop, tablet) and add it to the OS/browser's
trusted root certificates. After that, `https://<this-machine's-address>:8091`
(or your `WEB_PORT`) shows a normal, trusted padlock on every device — no more
warnings, and no per-restart re-trust needed (the CA persists in the `caddy_data`
volume).

If you'd rather have a real, publicly-trusted certificate with zero manual trust
steps anywhere, that needs a domain name pointed at this machine and port `443`
reachable from the internet — a materially different (and, for a home app,
usually unnecessary) setup than what's documented here.

### Reaching it by a hostname instead of a raw IP address

The tablet/phone apps and the web UI both work fine pointed at a raw LAN IP
(`https://192.168.1.203:8091`), but a hostname is more robust for two
independent reasons: it survives the server's IP ever changing (DHCP), and —
more subtly — some HTTP clients simply don't send TLS SNI when connecting to
a literal IP address (SNI is defined for hostnames; Android's OkHttp is one
such client, confirmed while debugging the native apps), which can affect
which certificate a TLS server picks. A hostname sidesteps that class of
problem entirely, since SNI is reliably sent for hostnames by every client.

Setting one up is two steps on your router (exact menu names vary by
brand/firmware — look for these two *concepts*, not these exact words):

1. **Reserve a static IP for this machine** — usually under "DHCP
   reservation" or "Address reservation," tied to this machine's MAC
   address. Without this, the IP can drift after a DHCP lease renewal and
   break anything pointed at the old one (the app's server address, any
   `default_sni` config, etc.).
2. **Add a local DNS / hostname entry** pointing that reserved IP at a name
   of your choosing (e.g. `storyteller.home` or `storyteller.local`) —
   look for "Local DNS," "DNS rebind protection," "Static DNS," or similar.
   Not every router supports this; if yours doesn't, the reserved IP alone
   (step 1) is still worth doing even without a hostname, since it at least
   makes the raw-IP address stable.

Once set up, use `https://storyteller.home:8091` (or whatever you chose) as
the server address everywhere instead of the IP — no other config changes
needed, since Caddy's `tls internal { on_demand }` issues a certificate for
whatever identity a client's SNI actually asks for.

## Swapping in cloud providers

Each service has a single "manage" decision driven by its base URL — point it at a remote endpoint and the local subprocess is skipped:

| Goal                              | Set                                                                                  |
| --------------------------------- | ------------------------------------------------------------------------------------ |
| Use LiveKit Cloud                 | `LIVEKIT_URL=wss://your-project.livekit.cloud` (+ `LIVEKIT_API_KEY` / `…_SECRET`)   |
| Use OpenAI for the LLM            | `LLAMA_BASE_URL=https://api.openai.com/v1`, `LLAMA_MODEL=gpt-4o-mini`, `LLAMA_API_KEY=sk-…` |
| Use a remote OpenAI-compatible STT| `STT_BASE_URL=…`, `STT_MODEL=…`, `STT_API_KEY=…`                                     |
| Use a remote OpenAI-compatible TTS| `TTS_BASE_URL=…`, `TTS_API_KEY=…`                                                    |

The supervisor logs which children it manages on startup.

## Voice recognition

On by default. The agent asks a new child's name once, then recognizes her
by voice alone on later calls and greets her by name — no login, no app UI
involved, purely a backend feature (see `local_voice_ai/speaker_id.py` and
`known_speakers.py`). It's built on NVIDIA NeMo's `titanet_small`
speaker-verification model, already a dependency via the `ml` extra (used
for Nemotron STT), so this adds no new ML library.

This is explicitly best-effort, not an authentication system: `titanet` is
trained mostly on adult voices, so accuracy on a child's higher-pitched,
more variable speech is unverified and likely imperfect. A false "doesn't
recognize her" just means she gets asked her name again — a soft failure,
not a bug to chase down.

- `VOICE_ID_ENABLED` (default `true`) / `VOICE_ID_MODEL` (default
  `titanet_small`) — turn it off, or swap in NeMo's larger/more accurate
  `titanet_large`, respectively.
- `KNOWN_SPEAKERS_PATH` (default `/models/known-speakers.json`) — where the
  enrolled `{name, voice embedding, enrolled-at}` entries persist, same
  volume as model weights.
- `GET /api/parent/known-speakers` (PIN-gated, `X-Parent-Pin` header) — list
  enrolled names/timestamps. Raw embeddings never leave the server, not even
  to this endpoint.
- `DELETE /api/parent/known-speakers/{name}` (PIN-gated) — forget a voice.

## Local development (no Docker)

Requires Python 3.11+, plus the `livekit-server` and `llama-server` binaries on
your PATH (macOS: `brew install livekit llama.cpp`).

```bash
# Python side
uv pip install -e ".[ml,dev]"
python -m local_voice_ai serve

# Frontend side, in another shell (only needed if you're editing the UI)
cd frontend && pnpm install && pnpm run dev
```

## Architecture

```
┌──────────────────────── single container ────────────────────────┐
│  python -m local_voice_ai serve                                  │
│  │                                                                │
│  ├── child: livekit-server     (skipped if LIVEKIT_URL external) │
│  ├── child: llama-server       (skipped if LLAMA_BASE_URL ext.)  │
│  ├── child: nemotron | whisper (skipped if STT_BASE_URL ext.)    │
│  ├── child: kokoro             (skipped if TTS_BASE_URL ext.)    │
│  ├── child: caddy              (only if ENABLE_HTTPS=1)          │
│  ├── child: livekit-agents worker                                │
│  └── in-process: FastAPI on :8080                                 │
│        ├── POST /api/connection-details  (token minting)         │
│        ├── GET  /api/status              (per-child readiness)   │
│        └── GET  /*                       (static frontend)       │
└───────────────────────────────────────────────────────────────────┘
```

## Project structure

```
.
├─ local_voice_ai/         # Python package: supervisor + agent + services
│  ├─ __main__.py          # python -m local_voice_ai serve
│  ├─ supervisor.py        # async process supervisor
│  ├─ config.py            # env-driven config + manage-X flags
│  ├─ api.py               # FastAPI: token route, status, static frontend
│  ├─ agent.py             # LiveKit Agents worker
│  ├─ speaker_id.py        # voice-recognition embeddings (NeMo titanet)
│  ├─ known_speakers.py    # enrolled {name, voice embedding} store
│  ├─ wakeword.py          # optional "hey livekit" gate for the agent
│  ├─ caddy/Caddyfile      # HTTPS front door (ENABLE_HTTPS=1 only)
│  └─ services/
│     ├─ nemotron/server.py
│     ├─ whisper/server.py
│     └─ kokoro/server.py
├─ frontend/               # Next.js (configured for static export)
├─ tab-app/                # Native Android client, tablet-oriented (Kotlin/Compose) — see tab-app/README.md
├─ phone-app/              # Native Android client, phone-oriented (Kotlin/Compose) — see phone-app/README.md
├─ tests/                  # pytest suite
├─ Dockerfile              # multi-stage build
├─ docker-compose.yml      # one service (CPU default)
├─ docker-compose.gpu.yml  # NVIDIA overlay: CUDA build + GPU reservation
├─ .github/workflows/      # CI: tests + multi-arch image publish to GHCR
└─ pyproject.toml          # one Python package, one venv
```

## Environment variables

See `.env` for the full list. The most important ones:

- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` — local-default; override for cloud.
- `LLAMA_BASE_URL`, `LLAMA_MODEL`, `LLAMA_HF_REPO`, `LLAMA_N_GPU_LAYERS`
- `LLAMA_OFFLINE` — offline LLM startup. Auto by default: once the model is cached, it starts with no internet (skips the Hugging Face lookup); the first run still downloads. Set `LLAMA_OFFLINE=1` to force it, or `0` to always re-check. `LLAMA_MODEL_PATH=/models/…​.gguf` loads a local file directly instead.
- `WAKE_WORD=1` — the agent joins deaf and only starts listening after it hears **“Hey LiveKit”** (on-device detection via [livekit-wakeword](https://github.com/livekit/livekit-wakeword), model baked into the image). `WAKE_WORD_THRESHOLD` (default `0.5`) tunes sensitivity; scores are logged at DEBUG for calibration.
- `STT_PROVIDER` (`nemotron`|`whisper`), `STT_BASE_URL`, `STT_MODEL`; `WHISPER_MODEL` picks the faster-whisper model for the whisper provider.
- `TTS_BASE_URL`, `TTS_VOICE`, `TTS_SPEED` (default `0.9` — Kokoro's default pace reads a little quick/flat for storytelling; slightly under `1.0` gives pauses and drawn-out words more room to land).
- `VOICE_ID_ENABLED` (default `true`), `VOICE_ID_MODEL` (default `titanet_small`), `KNOWN_SPEAKERS_PATH` — see [Voice recognition](#voice-recognition).
- `WEB_PORT` (default `8080`)
- `ENABLE_HTTPS=1` — fronts the web/API and LiveKit signaling with Caddy + a local CA (see [HTTPS](#https)). `PARENT_PIN` (default `1234`) gates the parent settings panel.
- `MANAGE_LIVEKIT`, `MANAGE_LLAMA`, `MANAGE_STT`, `MANAGE_TTS` — explicit overrides for the auto-detected "is the URL external?" logic.

## Debugging

General approach that's worked well building this: **reproduce with real
evidence before changing anything.** Guessing at a fix and shipping it
without confirming the actual failure mode wastes a rebuild cycle at best
and papers over the real bug at worst. Concretely:

- **Read the actual logs, not just the summary.** `docker compose logs app
  --since=5m` shows every child's real output — the specific error, not a
  guess at one. Most "it's not working" reports turn out to have a precise
  stack trace or connection error sitting in there already.
- **Reproduce the exact failure, not something adjacent.** If voice input
  is involved, a text-only test doesn't prove anything about the real path.
  One useful trick: synthesize a real spoken question via the server's own
  TTS (`curl -X POST http://127.0.0.1:8880/v1/audio/speech ...` from inside
  the container) and feed it to a browser as fake microphone input
  (Chromium's `--use-file-for-fake-audio-capture=<wav>` flag) — that
  exercises the real STT→LLM→TTS pipeline end to end instead of guessing
  from the outside.
- **Check the layer below the one that looks broken.** An app-level "can't
  connect" error is often actually a network/TLS/DNS problem one layer
  down. `openssl s_client -connect host:port` (with and without
  `-servername`) shows exactly what certificate a server presents and
  whether SNI changes the answer — this is how a "certificate not trusted"
  report on the native apps turned out to be Caddy serving the wrong
  certificate's identity for clients that omit SNI when connecting to a
  raw IP, not a trust or packaging problem at all. `lsusb -v` similarly
  shows the real USB device state below whatever `adb devices` reports.
- **Verify the fix the same way you found the bug.** Changing the prompt
  or the config and declaring victory isn't verification — rerun the exact
  reproduction (same synthesized audio, same `openssl s_client` check,
  same failing request) and confirm the *specific* symptom is actually
  gone, not just that something superficially changed.

If you hit something you can't get to the bottom of — or something in this
README turns out to be wrong or out of date — please
[open an issue](https://github.com/sooriyapsn/baby-story-teller/issues).
Real repro steps help a lot (what you ran, what you expected, what actually
happened, and any relevant log output) — but even a rough "this didn't work
and I'm not sure why" report is genuinely useful and worth filing rather
than sitting on.

## Credits

- LiveKit: <https://livekit.io/>
- LiveKit Agents: <https://docs.livekit.io/agents/>
- NVIDIA Nemotron Speech: <https://huggingface.co/nvidia/nemotron-speech-streaming-en-0.6b>
- NVIDIA NeMo (speaker-verification model, `titanet_small`, used for voice recognition): <https://github.com/NVIDIA/NeMo>
- llama.cpp: <https://github.com/ggml-org/llama.cpp>
- Gemma 4 (default LLM, Unsloth QAT GGUF): <https://huggingface.co/unsloth/gemma-4-E2B-it-qat-GGUF>
- Kokoro TTS: <https://github.com/hexgrad/kokoro>
- faster-whisper (Whisper fallback): <https://github.com/SYSTRAN/faster-whisper>
- livekit-wakeword ("hey livekit" detection): <https://github.com/livekit/livekit-wakeword>
