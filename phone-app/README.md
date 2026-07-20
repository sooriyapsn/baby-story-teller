# Story Teller — Android (native)

A native Kotlin/Jetpack Compose client for the same backend the web app talks
to (`local_voice_ai/api.py`), built specifically to get better voice quality
on a tablet than a mobile browser gives you: LiveKit's Android SDK drives
WebRTC through Android's native audio pipeline (hardware AEC/NS/AGC where the
device supports it, proper audio-focus and Bluetooth-routing integration)
instead of whatever a WebView happens to negotiate.

## Status

Builds clean (`./gradlew assembleDebug` succeeds, lint passes with only
cosmetic/version-bump warnings) but has **not been run on a real device** —
this was written and verified by compiling it, not by installing and testing
it, since no Android device or emulator was available in the environment it
was built in. Treat the voice-call screen especially as needing real-device
verification before you trust it: open it in Android Studio, run it on your
Samsung tablet, and watch the logcat output the first time you make a call.

## What's implemented

- Server address setup (no service discovery on a home LAN — you type in the
  address once, same as bookmarking it in a browser)
- Character picker (Red One / Blue Bolt / Rosie) + language dropdown
  (English/Telugu/Marathi, matching whatever `/api/status` reports as available)
- Voice call screen: connects to the LiveKit room, native mic/speaker audio,
  mic mute toggle. Agent state is simplified to "speaking" vs "listening" —
  the richer listening/thinking/speaking split the web UI gets needs the
  LiveKit voice-assistant attribute protocol, which this doesn't read yet.
- Parent dashboard: PIN gate, time limit, story text, PDF upload
- Session time-limit enforcement (ends the call automatically, mirroring the web app)

## Opening it

Android Studio: **Open** → select this `tab-app/` directory. It's a normal
Gradle project — first sync will pull dependencies (including a JitPack-
hosted LiveKit dependency, see `settings.gradle.kts`).

Command line:
```bash
./gradlew assembleDebug     # app/build/outputs/apk/debug/app-debug.apk
./gradlew installDebug      # with a device/emulator connected via adb
```

## HTTPS / the local CA

The backend's `ENABLE_HTTPS=1` mode (see the main README) uses a self-signed
local CA. This app only trusts *system* and *user-installed* certificates
(`res/xml/network_security_config.xml`) — it does **not** bundle a copy of
the CA into the APK, deliberately, since that CA is regenerated if the
server's `caddy_data` volume is ever recreated and a baked-in cert would go
stale. Install the same CA on the tablet that you'd install for a browser:

```bash
docker compose exec app cat /data/caddy/pki/authorities/local/root.crt
```

Transfer that file to the tablet and add it under Settings → Security →
Encryption & credentials → Install a certificate → CA certificate, then
enter `https://<server-address>:8091` in the app's server-setup screen.

## Known gaps (this was a first pass, not a full port)

- No screenshot/visual mascot animation — the call screen is a plain colored
  circle that pulses when the agent speaks, not the character art frontend/
  has. Swapping in real art or a Lottie/Compose animation is a separate pass.
- Agent state is speaking-vs-not, not the full listening/thinking/speaking
  split (see above).
- No wake-word support.
- Launcher icon is a placeholder solid-color shape, not real character art.
