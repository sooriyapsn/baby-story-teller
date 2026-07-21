---
name: rebuild-verify
description: Rebuild the story-teller Docker container after a local_voice_ai change and verify it's healthy with a clean startup warm-up before declaring the change done. Use after editing anything under local_voice_ai/, or when asked to rebuild/redeploy the backend.
---

# Rebuild & verify the backend

Rebuilding is not the finish line — a healthy container can still have a
broken or stalled startup warm-up (LLM prompt cache, filler audio cache).
Verify both before saying the change is live.

## Steps

1. **Check for an active call first.** `docker logs --tail 20 story-teller-app-1 | grep -iE "participant active|joined"` — a rebuild drops any in-progress session. If one looks live, confirm with the user before proceeding (don't silently interrupt a call).

2. **Rebuild and recreate:**
   ```bash
   docker compose up --build -d
   ```

3. **Wait for healthy** (poll, don't sleep-and-hope):
   ```bash
   for i in $(seq 1 24); do
     status=$(docker inspect --format='{{.State.Health.Status}}' story-teller-app-1)
     echo "$(date +%H:%M:%S) $status"
     [ "$status" = "healthy" ] && break
     sleep 5
   done
   ```

4. **Verify warm-up actually finished clean**, not just that the container is healthy — health checks pass long before warm-up completes:
   ```bash
   docker logs story-teller-app-1 | grep -iE "llm warm-up|filler audio warm-up"
   ```
   Look for `llm warm-up complete: <character>` (x3) and `filler audio warm-up finished`. Any `gave up` line means Kokoro/llama-server were still cold-starting when warm-up's retry budget ran out — usually resolves on its own once the model finishes downloading/loading, but don't declare the change done until you've confirmed it, e.g.:
   ```bash
   docker exec story-teller-app-1 ls /models/story-gallery-audio-cache/   # should have 6 files (3 characters x 2 filler lines)
   ```

5. **Report** what changed, confirm health + clean warm-up, and note if a live test is warranted before calling it done.

## Known gotchas (learned the hard way)

- LiveKit prewarms **several** worker processes at boot; each one runs the warm-up functions independently. A filesystem lock in `gallery_audio_cache.py`/`agent.py` limits actual TTS/LLM calls to one process — if you ever see a flood of duplicate warm-up requests in the logs, that lock is what to check first.
- `docker logs --since <absolute-ISO-timestamp>` has silently returned zero lines in this environment even when activity clearly happened in that window — prefer `--since <N>m` (relative, e.g. `--since 10m`) instead.
