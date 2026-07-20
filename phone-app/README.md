# Story Teller — Android phone (native)

A native Kotlin/Jetpack Compose client for the same backend the web app talks
to (`local_voice_ai/api.py`), sized and laid out for a regular phone screen
(portrait-friendly, no forced landscape — see `tab-app/` for the
tablet-oriented sibling this was forked from). Built for better voice
quality than a mobile browser gives you: LiveKit's Android SDK drives WebRTC
through Android's native audio pipeline (hardware AEC/NS/AGC where the
device supports it, proper audio-focus and Bluetooth-routing integration)
instead of whatever a WebView happens to negotiate.

## Status

Builds clean (`./gradlew assembleDebug` succeeds, lint passes with only
cosmetic/version-bump warnings) but has **not been run on a real device** —
this was written and verified by compiling it, not by installing and testing
it, since no Android device or emulator was available in the environment it
was built in. Treat the voice-call screen especially as needing real-device
verification before you trust it: open it in Android Studio, run it on your
phone, and watch the logcat output the first time you make a call.

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

Android Studio: **Open** → select this `phone-app/` directory. It's a normal
Gradle project — first sync will pull dependencies (including a JitPack-
hosted LiveKit dependency, see `settings.gradle.kts`).

Command line:
```bash
./gradlew assembleDebug     # app/build/outputs/apk/debug/app-debug.apk
./gradlew installDebug      # with a device/emulator connected via adb
```

## Installing on your phone

There's no Play Store listing or CI-built release — you build the APK
yourself and put it on the phone directly.

1. Build it:
   ```bash
   ./gradlew assembleDebug
   ```
   Produces `app/build/outputs/apk/debug/app-debug.apk`.

2. Get it onto the phone, either way:
   - **USB + adb** (fastest, and lets you see logcat while testing):
     ```bash
     adb install -r app/build/outputs/apk/debug/app-debug.apk
     ```
     Needs the phone connected by USB with Developer Options → USB
     debugging turned on (tap the phone's Build Number 7 times under
     Settings → About phone to unlock Developer Options).
   - **No cable**: copy the APK to the phone any way you'd move a file
     (a cloud-storage app, emailing it to yourself) and open it from the
     Files app on the phone.

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

## Publishing a build as a GitHub Release (optional)

If you want a downloadable link instead of building locally every time —
e.g. so the APK is one click away from any device's browser — attach it to
a GitHub Release. **Don't commit the `.apk` file into the repo itself**:
it's a ~65 MB binary, and git keeps every version forever, so the repo only
grows from there. Releases attach binaries without that cost.

With the [`gh` CLI](https://cli.github.com/) installed and logged in
(`gh auth login`):
```bash
./gradlew assembleDebug
gh release create phone-app-v1 app/build/outputs/apk/debug/app-debug.apk \
  --title "Story Teller — Phone v1" \
  --notes "Debug build for sideloading. See phone-app/README.md for install steps."
```
That prints a URL — open it on the phone's browser (or send it via
whatever you like) and tap the `.apk` link to download and install
directly, same "allow unknown sources" prompt as any sideloaded APK.

Without `gh`: build the APK, then on GitHub → **Releases** → **Draft a new
release** → drag the `.apk` file into the assets box → **Publish release**.

Re-publish after a rebuild by creating a new release (`phone-app-v2`, etc.)
— release tags aren't meant to be overwritten in place.

## HTTPS / the local CA

The backend's `ENABLE_HTTPS=1` mode (see the main README) uses a self-signed
local CA. This app only trusts *system* and *user-installed* certificates
(`res/xml/network_security_config.xml`) — it does **not** bundle a copy of
the CA into the APK, deliberately, since that CA is regenerated if the
server's `caddy_data` volume is ever recreated and a baked-in cert would go
stale. Install the same CA on the phone that you'd install for a browser:

```bash
docker compose exec app cat /data/caddy/pki/authorities/local/root.crt
```

Transfer that file to the phone and add it under Settings → Security →
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
