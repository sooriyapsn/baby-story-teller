---
name: kid-scope-audit
description: Audit the codebase for capability or content that's out of scope for a kids' voice-storytelling app — leftover generic-assistant features, privacy-sensitive surface (camera/mic/screen capture), or content paths that could produce non-kid-safe output. Use periodically as the app grows, or after pulling in a new template/library/dependency.
---

# Kid-scope audit

This project's stated goal is narrow: **telling stories for kids, kid-safe,
voice-only.** This app started as a fork of a generic voice-assistant
template (video, screen share, text chat, the works) — the risk is template
capability surviving in disabled-but-present form, not just messy code.
"Off by default" is not the same as "removed," and for a kids' product that
distinction matters: a config flag can flip, disabled code can't grant
capability it doesn't contain.

## What to check, in order

1. **Grep for template remnants** across `local_voice_ai/`, `frontend/`, `tab-app/`, `phone-app/` (excluding `node_modules`/`.venv`):
   ```bash
   grep -rlE "screen.?share|camera|video.?track|ChatInput|typed.?message" \
     --include="*.py" --include="*.tsx" --include="*.ts" --include="*.kt" \
     local_voice_ai frontend tab-app phone-app 2>/dev/null | grep -v node_modules
   ```
   For each hit, trace whether it's **reachable** in the real UI (imported and rendered under some real prop/state), not just present in a file. Check the feature-flag chain end to end (e.g. a config default → the prop that gates rendering) rather than trusting the flag's current value alone — a `false` today doesn't mean the surface is actually gone.

2. **Check documented claims against reality.** Grep `README.md`, `CLAUDE.md`, `ARCH.md` for words like "removed," "disabled," "not included" and verify the code actually matches. A claim that's gone stale here is worse than most staleness — it's telling a reader (human or Claude) that a risk doesn't exist when it does.

3. **Check what's actually reachable in the shipped UI**, not just what's imported — a component can be imported and still be permanently unreachable if every path to opening it is gated behind a flag that's structurally always false. Confirm by tracing the prop/state chain from the top-level page down, the way `chatOpen`/`visibleControls.chat` were traced in the 2026-07-20 audit.

4. **New dependencies since the last audit** — skim `pyproject.toml` / `package.json` diffs for anything that smells like analytics, tracking, ads, or unrelated capability creeping in via a transitive feature.

5. **Safety-relevant code paths** (not just feature scope): confirm the system prompt (`characters.py`'s `_SHARED_RULES`) is still the only content-safety mechanism and nothing bypasses it (e.g. a raw/unfiltered LLM call added somewhere outside `Assistant.llm_node()`).

## Reporting

- Categorize findings: **in scope** (legitimately repurposed or necessary infra — explain why), **needs a decision** (ambiguous, ask), **recommend removing** (dead template surface with no purpose here).
- **Never delete anything in this pass without confirming scope with the user first** — present findings, then act on their go-ahead. Deleting frontend/backend surface is a real, sometimes multi-file change; scope it before cutting (see the 2026-07-20 audit: tracing shared hooks like `use-input-controls.ts` before trimming saved a broken build).
- After removing anything, run the project's actual checks (`pnpm run build && pnpm run lint && pnpm run format:check` for frontend; `uv run pytest tests/ -q` for backend) before calling it done — an audit isn't finished until the removal is verified, not just performed.
