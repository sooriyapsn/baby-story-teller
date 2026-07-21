---
name: watch-ci
description: Poll GitHub Actions for the commit just pushed to this repo and report pass/fail. Use right after `git push` to main, instead of manually curling the API each time.
---

# Watch CI after a push

This repo (`sooriyapsn/baby-story-teller`) is public, so the GitHub REST API
works unauthenticated — no `gh auth login` needed, and `gh` isn't
authenticated in this environment anyway.

## Steps

1. **Get the pushed commit SHA:**
   ```bash
   git rev-parse HEAD
   ```

2. **Find the run(s) for it** (there may be two: `CI`, and `Android` if the push touched `phone-app/`/`tab-app/`):
   ```bash
   curl -s "https://api.github.com/repos/sooriyapsn/baby-story-teller/actions/runs?per_page=5" \
     | python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d['workflow_runs']:
    print(r['id'], r['name'], r['head_sha'][:7], r['status'], r.get('conclusion'))
"
   ```

3. **Poll each matching run** in the background rather than blocking the turn — a full CI run takes minutes:
   ```bash
   for i in $(seq 1 30); do
     status=$(curl -s "https://api.github.com/repos/sooriyapsn/baby-story-teller/actions/runs/<RUN_ID>" \
       | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['status'], d.get('conclusion'))")
     echo "$(date +%H:%M:%S) $status"
     [ "$(echo "$status" | awk '{print $1}')" = "completed" ] && break
     sleep 15
   done
   ```
   Run this via the background-bash mechanism (`run_in_background: true`) so other work can continue while it waits, and report back once the notification lands — don't fabricate a result before it actually completes.

4. **On failure**, pull the job list and the failing job's logs to diagnose before reporting:
   ```bash
   curl -s "https://api.github.com/repos/sooriyapsn/baby-story-teller/actions/runs/<RUN_ID>/jobs" \
     | python3 -c "import json,sys; d=json.load(sys.stdin); [print(j['name'], '->', j['status'], j.get('conclusion')) for j in d['jobs']]"
   ```

## Notes

- Two separate workflows exist: `.github/workflows/ci.yml` (`test` + `frontend`, gate merges; `docker`/`docker-merge` only on push to main/tags) and `.github/workflows/android.yml` (builds/publishes `phone-app`/`tab-app` APKs, only triggers on changes under those directories).
- Don't poll faster than every ~15s — there's no benefit and it just spends API calls against the unauthenticated rate limit.
