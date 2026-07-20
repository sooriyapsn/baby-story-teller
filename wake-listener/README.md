# Wake listener

A tiny always-on process that runs directly on the laptop (**not** inside
Docker — it exists specifically to start the container when it's down, so it
can't live inside the thing it starts). The phone/tablet apps use it to show
a "Wake up server" button when they can't reach the main app, letting a
parent start it from across the room instead of walking over to the laptop.

It does exactly one thing: on a valid authenticated request, it runs
`docker compose up -d` in this project's directory. Nothing else — no
arbitrary commands, no free-form input ever reaches a shell.

## Setup (one-time, Linux with systemd)

1. Add a secret to the project's `.env` (same file everything else in this
   project already reads — see the root README):
   ```bash
   # in .env
   WAKE_LISTENER_PORT=9191
   WAKE_SECRET=<pick something random, e.g. `openssl rand -hex 16`>
   ```
2. Edit `story-teller-wake.service` if this repo isn't at
   `~/Projects/story-teller` — update the `ExecStart` path.
3. Install as a user service so it starts automatically at login and
   restarts itself if it ever crashes:
   ```bash
   mkdir -p ~/.config/systemd/user
   cp story-teller-wake.service ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable --now story-teller-wake
   loginctl enable-linger "$USER"   # keeps it running even when you're logged out
   ```
4. Confirm it's up:
   ```bash
   systemctl --user status story-teller-wake
   curl http://localhost:9191/health   # -> {"status": "ok"}
   ```
5. In the phone/tablet app's server setup screen, enter the wake secret
   alongside the server address (see the app READMEs).

## Security notes

- **LAN-only threat model, same as the rest of this project.** This listener
  binds `0.0.0.0` so it's reachable from your Wi-Fi, same as the main app.
  Anyone else on your network who has (or guesses) `WAKE_SECRET` could
  trigger `docker compose up -d` — low actual risk (it's idempotent and just
  starts a service you already run), but don't reuse a real password for it,
  and don't port-forward this to the internet.
- The secret is compared with `hmac.compare_digest` (constant-time), and
  `.env` is read fresh on every request — rotate `WAKE_SECRET` any time by
  editing that one line, no restart needed.
- This process needs to run **outside** Docker by design (it starts the
  container, so it can't depend on the container being up) — that's why it's
  a plain systemd service, not another entry in docker-compose.yml.

## Manual run (without systemd, for testing)

```bash
python3 wake_listener.py
```
Stdlib-only — no venv/dependencies needed.
