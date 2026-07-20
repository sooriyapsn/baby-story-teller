# Story Teller — Android (native)

A native Kotlin/Jetpack Compose client for the same backend the web app talks
to (`local_voice_ai/api.py`), built specifically to get better voice quality
on a tablet than a mobile browser gives you: LiveKit's Android SDK drives
WebRTC through Android's native audio pipeline (hardware AEC/NS/AGC where the
device supports it, proper audio-focus and Bluetooth-routing integration)
instead of whatever a WebView happens to negotiate.

> **Disclaimers:** this is a hobby project's Android client, not a certified
> children's product — see the main README's
> [Disclaimers](../README.md#disclaimers) section for the full statement.
> Short version: it's still actively being developed and can break between
> builds, it's provided as-is with no warranty (MIT license), a parent should
> supervise rather than treat it as a childproofed app, and bugs should be
> [filed as issues](https://github.com/sooriyapsn/baby-story-teller/issues)
> rather than silently worked around — they get looked at and fixed on a
> best-effort basis.

## Status

Built, installed, and iterated on against a real Samsung tablet over
several rounds of on-device testing — not just a compile-and-hope build.
The call screen in particular has been through multiple real-device
debugging passes (see "Non-obvious gotchas" below for what that surfaced).

## What's implemented

- Server address setup (no service discovery on a home LAN — you type in the
  address once, same as bookmarking it in a browser)
- Character picker (Red One / Blue Bolt / Rosie) + language dropdown
  (English/Telugu/Marathi, matching whatever `/api/status` reports as available)
- Voice call screen: connects to the LiveKit room, native mic/speaker audio,
  mic mute toggle, screen stays awake for the duration of the call
  (`FLAG_KEEP_SCREEN_ON` — a locked/dimmed screen otherwise pauses the
  activity and drops the mic mid-call). Full listening/thinking/speaking
  agent state, read from the same `lk.agent.state` participant attribute the
  web app's `useVoiceAssistant()` hook uses (see "Non-obvious gotchas").
- An animated Canvas-drawn mascot per character (`ui/Mascot.kt`) — a native
  port of the web app's `agent-character.tsx`: blinking eyes, a talking
  mouth, swinging arms/legs, a distinct "thinking" pose (hand to chin, eyes
  glancing, bouncing thought dots) separate from "listening" (pulsing radar
  rings), and Red One's signature grumpy fold. Same mascot also appears
  (idle) on the character-picker screen.
- A faint animated balloon field behind the call screen (`ui/BalloonField.kt`,
  ported from the web app's `balloon-field.tsx`).
- Parent dashboard: PIN gate, time limit, story text, PDF upload
- Session time-limit enforcement (ends the call automatically, mirroring the web app)
- Voice recognition (the agent remembering the child by name across calls)
  is a **backend-only** feature — see the main README's
  [Voice recognition](../README.md#voice-recognition) section. Nothing to
  build or configure here; the personalized greeting just arrives over the
  same audio track playback this app already does.

## Opening it

Android Studio: **Open** → select this `tab-app/` directory. It's a normal
Gradle project — first sync will pull dependencies (including a JitPack-
hosted LiveKit dependency, see `settings.gradle.kts`).

Command line:
```bash
./gradlew assembleDebug     # app/build/outputs/apk/debug/app-debug.apk
./gradlew installDebug      # with a device/emulator connected via adb
```

## Installing on your tablet

**Fastest way — grab the auto-built APK:** every push to `main` rebuilds
this app and republishes it at the same link, so this always has the
latest build. Requires **Android 8.0 (Oreo, API 26) or newer**
(`minSdk = 26` in `app/build.gradle.kts`) — older tablets can't install it:

> **[Download tab-app-debug.apk](https://github.com/sooriyapsn/baby-story-teller/releases/download/debug-latest/tab-app-debug.apk)**

Open that link in the tablet's browser, let it download, then skip to
step 3 below. (See "Publishing a build as a GitHub Release" further down
for how this link is kept up to date.)

Building it yourself instead:

1. Build it:
   ```bash
   ./gradlew assembleDebug
   ```
   Produces `app/build/outputs/apk/debug/app-debug.apk`.

2. Get it onto the tablet, either way:
   - **USB + adb** (fastest, and lets you see logcat while testing):
     ```bash
     adb install -r app/build/outputs/apk/debug/app-debug.apk
     ```
     Needs the tablet connected by USB with Developer Options → USB
     debugging turned on (tap the tablet's Build Number 7 times under
     Settings → About tablet to unlock Developer Options).
   - **No cable**: copy the APK to the tablet any way you'd move a file
     (a USB drive, a cloud-storage app, emailing it to yourself) and open
     it from the Files app on the tablet.

3. **Install from unknown sources**: since this isn't from the Play Store,
   Android will block the install the first time and prompt you to allow
   it for whichever app you used to open the APK (Files, Chrome, etc.) —
   follow that prompt, then try opening the APK again.

4. First launch: grant the microphone permission when asked, then enter
   the server address on the setup screen (see "HTTPS / the local CA"
   below if you're running the server with `ENABLE_HTTPS=1`).

5. Reinstalling after a rebuild: `adb install -r ...` (the `-r` reinstalls
   over the existing app, keeping its saved server address) or just repeat
   step 2 and confirm the "replace existing app" prompt.

### Troubleshooting: "No connected devices!" / adb doesn't see the tablet

This is the single most common snag with the USB + adb install path, and
it's almost always the same cause: **the tablet is plugged in, but USB
debugging isn't turned on yet.** Plain USB file-transfer mode (what a
tablet uses by default when you plug it in) and USB *debugging* mode
(what `adb` needs) are two different things — being able to see the
tablet's files on your computer doesn't mean `adb` can talk to it.

Fix it in order — most people only need step 1–4:

1. **Unlock Developer Options** (skip if you've done this before): on the
   tablet, go to **Settings → About tablet**, find **Build number**, and
   tap it **7 times in a row**. You'll see a small message counting down
   ("You are now 3 steps away from being a developer...") and then
   "You are now a developer!"
2. **Turn on USB debugging**: go to **Settings → Developer options**
   (it's a new menu that appeared after step 1, usually near the bottom of
   Settings) and turn on **USB debugging**.
3. **Unplug the USB cable and plug it back in.** This matters — Android
   needs to renegotiate the connection now that debugging is enabled; it
   won't switch modes on its own while already plugged in.
4. **Unlock the tablet's screen and look at it.** A popup should appear:
   *"Allow USB debugging?"* with a long string of letters/numbers (your
   computer's ID) underneath. Tick **"Always allow from this computer"**
   and tap **Allow**. If you don't see this popup, it may be hidden behind
   the lock screen — make sure the tablet is unlocked and awake.
5. **Check it worked**, from a terminal on your computer:
   ```bash
   adb devices
   ```
   You want to see your tablet listed with the word `device` next to it,
   like:
   ```
   List of devices attached
   R58N30ABCDE     device
   ```
   - If the list is **empty** — go back to step 2, the toggle can silently
     reset if you plugged in before turning it on.
   - If it says `unauthorized` instead of `device` — you missed the popup
     in step 4; unlock the tablet and look again.
   - If it's still empty after re-checking everything above, try:
     ```bash
     adb kill-server && adb start-server && adb devices
     ```
     which restarts adb's background process — sometimes it just gets
     into a stuck state and this clears it.
   - Still nothing? Try a different USB cable or port. Some cheap cables
     only carry power, not data, and will never work for this even though
     the tablet still charges through them.

Once `adb devices` shows your tablet as `device`, run
`./gradlew installDebug` (or `adb install -r app/build/outputs/apk/debug/app-debug.apk`)
again and it should go through.

## Publishing a build as a GitHub Release

`.github/workflows/android.yml` builds this app (and `phone-app`) on every
push to `main` that touches either directory, then republishes both APKs as
assets on a single fixed-tag release, `debug-latest` — deleting and
recreating that release each time, so the same download link always points
at the latest build:

- Phone: https://github.com/sooriyapsn/baby-story-teller/releases/download/debug-latest/phone-app-debug.apk
- Tablet: https://github.com/sooriyapsn/baby-story-teller/releases/download/debug-latest/tab-app-debug.apk

Needs the repo's Settings → Actions → General → Workflow permissions set to
"Read and write permissions" — that's what lets the workflow's
`gh release create` step publish the release.

### Publishing a one-off release manually (optional)

To publish a specific build without pushing to `main` — e.g. a version you
want to keep around under its own tag instead of it being overwritten —
use the [`gh` CLI](https://cli.github.com/) directly (`gh auth login` first):
```bash
./gradlew assembleDebug
gh release create tab-app-v1 app/build/outputs/apk/debug/app-debug.apk \
  --title "Story Teller — Tablet v1" \
  --notes "Debug build for sideloading. See tab-app/README.md for install steps."
```
That prints a URL — open it on the tablet's browser (or send it via
whatever you like) and tap the `.apk` link to download and install
directly, same "allow unknown sources" prompt as any sideloaded APK.

Without `gh`: build the APK, then on GitHub → **Releases** → **Draft a new
release** → drag the `.apk` file into the assets box → **Publish release**.
Give it its own tag (`tab-app-v2`, etc.) rather than reusing `debug-latest`,
which the CI workflow expects to own.

## HTTPS / the local CA

The backend's `ENABLE_HTTPS=1` mode (see the main README) uses a self-signed
local CA. `res/raw/story_teller_ca.crt` bundles a snapshot of that CA
directly into the APK (trusted via `res/xml/network_security_config.xml`),
so a fresh install works over `https://` with no manual cert-install step —
*system* and *user-installed* certificates are still trusted too, as a
fallback.

The one case that still needs a manual step: if the server's `caddy_data`
volume is ever recreated, a **new** CA gets generated, and the bundled one
in an already-built APK goes stale. Either rebuild the app with a fresh copy
of the cert in `res/raw/`, or install the new CA the manual way, same as
for a browser:

```bash
docker compose exec app cat /data/caddy/pki/authorities/local/root.crt
```

Transfer that file to the tablet and add it under Settings → Security →
Encryption & credentials → Install a certificate → CA certificate, then
enter `https://<server-address>:8091` in the app's server-setup screen.

## Non-obvious gotchas worth knowing before touching related code

- **`Mascot.kt`/`BalloonField.kt` deliberately don't use Compose's
  `animateFloat`/`infiniteRepeatable` APIs.** Those respect the OS-level
  "Animator duration scale" developer setting (a real accessibility feature,
  sometimes also dialed down by OEM battery savers) — when it's off, every
  Compose animation in every app on the phone goes instant/frozen. That's
  exactly what made the mascot look completely static on a real test device
  even though the underlying agent-state detection was working correctly.
  Every gesture is instead driven by a manually-ticked `withFrameNanos`
  timer and plain trigonometry, which is immune to that setting — don't
  reintroduce `animateFloat` for anything the child is meant to actually
  see move.
- **Agent state comes from the `lk.agent.state` participant attribute**
  (`LiveKitManager.kt`), not from `RoomEvent.ActiveSpeakersChanged`. The
  older audio-level-heuristic approach can't distinguish "thinking" from
  "listening" at all, and is flaky about "speaking" too (a quiet beat
  mid-sentence can make it look stuck) — this is why the mouth used to look
  frozen mid-call. `Participant.agentAttributes.lkAgentState` is the
  authoritative signal the web app's `useVoiceAssistant()` hook also reads.

## Known gaps

- No live audio-level lip sync — the mouth flutters on a steady timer while
  speaking rather than reacting to actual amplitude (LiveKit Android does
  expose `Participant.audioLevel`, just not wired up yet).
- No wake-word support.
- Launcher icon is a placeholder solid-color shape, not real character art.
