---
name: live-device-test
description: Walk through a live voice-call test on the tab-app/phone-app against the running backend, then verify what actually happened via docker logs rather than trusting "it sounded fine." Use when a backend change (agent.py, story/TTS/LLM behavior) needs real-device confirmation.
---

# Live device test

Claude can't operate the tablet/phone itself — this skill is about giving
the user a precise thing to say and then reading the backend's own account
of what happened, instead of taking "it worked" at face value.

## Steps

1. **Make sure the container is already rebuilt and healthy** on the code under test (see the `rebuild-verify` skill if not).

2. **Give the user one specific thing to do**, not a vague "go test it" — the exact phrase to say, which character/session state matters, and what you're listening for. E.g. "ask a plain 'tell me a story' — no topic" vs "ask about a specific topic to force the real LLM path."

3. **Note the current time before they act:**
   ```bash
   date -u +%Y-%m-%dT%H:%M:%S
   ```
   (For pulling logs afterward, prefer `docker logs --since <N>m story-teller-app-1` with a relative window over this absolute timestamp — `--since` with an ISO timestamp has silently returned zero lines in this environment even when activity clearly happened.)

4. **Wait for the user's confirmation** that they've done it — don't poll or guess at timing for a real person's action.

5. **Pull and interpret the logs**, matched to what's actually being verified:
   - Which device/app connected: `grep -iE "deviceModel|\"sdk\": \"ANDROID\""` on the participant-join lines (shows device model, Android version, app SDK version).
   - Gallery-story shortcut fired (not the LLM): `grep "gallery_story_check"` (shows the matched text and whether it triggered) and `grep "gallery audio cache"` (hit vs. miss).
   - Real LLM path used: look for new `llama-server` slot-launch lines (`slot launch_slot_`) around the right timestamp.
   - Filler line played: `grep -iE "say|filler"`.
   - Story-gallery state persisted: `docker exec story-teller-app-1 cat /models/story-gallery-state.json`.

6. **Report the finding as evidence, not narration** — quote the actual log line(s) that confirm (or contradict) the expected behavior, not just "yes it worked."

## Gotchas learned from real sessions

- A session with a parent-set custom story (`room metadata` has `"story": "..."`) still goes through the same shortcut logic — the custom-story instruction only affects the LLM path, not whether the gallery shortcut can fire on a bare "tell me a story" ask.
- If something that should have matched didn't, don't guess — add a temporary `logger.info` right at the decision point, rebuild, and re-test. That's what surfaced the actual bug the one time this was needed, faster than reasoning about it blind.
