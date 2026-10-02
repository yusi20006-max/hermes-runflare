# Hermes Agent Gateway — Runflare Free Deployment

Production Docker deployment of **Hermes Agent v0.20.6 (v2026.8.27)** for Runflare Free tier, with the locally validated Bale platform integration.

## Quick Start

### 1. Build Image Locally (Optional Verification)

```bash
docker build -t hermes-gate .
```

### 2. Test Locally

```bash
# Create local data volume
docker volume create hermes-data

# Run with your Telegram credentials
docker run --rm -it \
  -p 8000:8000 \
  -v hermes-data:/opt/data \
  -e TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrSTUvwxYZ" \
  -e TELEGRAM_ALLOWED_USERS="123456789" \
  hermes-gate
```

### 3. Deploy to Runflare

#### Option A: Runflare Web Portal (Recommended)

1. Push this repository to GitHub
2. In Runflare Portal → Project `hermes` → Service `hermes-gate`:
   - **Source**: GitHub repository
   - **Build**: Dockerfile (this repo)
   - **Plan**: Free (3 GB RAM, 1.5 GHz CPU)
   - **Port**: 8000
   - **Environment Variables** (see below)
   - **Volumes**: Add persistent volume mounted at `/opt/data`

#### Option B: Runflare CLI (if available)

```bash
runflare deploy --project hermes --service hermes-gate --dockerfile Dockerfile
```

---

## Required Environment Variables (Runflare Secrets)

Add these in Runflare Portal → Service `hermes-gate` → **Environment Variables**:

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | **YES** | Bot token from @BotFather | `123456789:ABCdefGHIjklMNOpqrSTUvwxYZ` |
| `TELEGRAM_ALLOWED_USERS` | **YES** | Your Telegram user ID(s) (comma-separated) | `123456789` or `123456789,987654321` |
| `BALE_BOT_TOKEN` | **If Bale enabled** | Bale bot token | Set as a Runflare secret |
| `BALE_ALLOWED_USERS` | Recommended | Comma-separated Bale user IDs allowed to chat | `1041795208` |
| `BALE_CHAT_ID` | Optional | Additional Bale chat ID allowed to chat | `1041795208` |
| `BALE_ALLOW_ALL_USERS` | Optional | Truthy value allows all Bale users | `false` |
| `BALE_HOME_CHANNEL` | Optional | Default Bale chat ID for cron/notification delivery | `1041795208` |
| `TELEGRAM_WEBHOOK_URL` | No | Public HTTPS URL for webhook mode (enables webhook instead of long-polling) | `https://hermes-gate.runflare.app/telegram` |
| `TELEGRAM_WEBHOOK_PORT` | No* | Local listen port for webhook server | `8443` |
| `TELEGRAM_WEBHOOK_SECRET` | No* | Secret token for webhook verification (generate: `openssl rand -hex 32`) | `a1b2c3d4...` |
| `OPENROUTER_API_KEY` | Recommended | For LLM access via OpenRouter | `sk-or-v1-...` |
| `ANTHROPIC_API_KEY` | Alternative | For direct Anthropic access | `sk-ant-...` |
| `OPENAI_API_KEY` | Alternative | For direct OpenAI access | `sk-...` |

\* Required only if `TELEGRAM_WEBHOOK_URL` is set.

### Bale configuration

The image includes the Bale plugin and enables the Bale platform at container startup. The Bale integration is isolated from Telegram in two ways:

- Bale authorization reads only `BALE_ALLOWED_USERS`, `BALE_CHAT_ID`, and `BALE_ALLOW_ALL_USERS`.
- Bale never activates Telegram's DoH/fallback-IP transport; its Bot API endpoint remains `https://tapi.bale.ai/bot`.

Do **not** put `BALE_BOT_TOKEN` in this repository. Configure it as a Runflare secret.

The integration was validated locally with a real Bale round-trip before this Runflare repository change.

### Getting Telegram Credentials

1. **Bot Token**: Message @BotFather → `/newbot` → follow prompts
2. **User ID**: Message @userinfobot → copy your numeric ID
3. **Security**: Always set `TELEGRAM_ALLOWED_USERS` to restrict access

---

## Runflare Configuration

### Service Settings

| Setting | Value |
|---------|-------|
| **Service Name** | `hermes-gate` |
| **Project** | `hermes` |
| **Plan** | Free |
| **RAM** | 3 GB |
| **CPU** | 1.5 GHz |
| **Runtime** | Docker |
| **Expose Port** | 8000 |
| **Health Check** | Process-based (built-in) |
| **Restart Policy** | Always (Runflare default) |

### Persistent Volume

- **Mount Path**: `/opt/data`
- **Purpose**: Stores Hermes config, sessions, memory, skills, logs
- **Size**: Minimum 1 GB (Runflare Free includes persistent storage)

### Startup Command (Fixed in Dockerfile)

```
hermes gateway run
```

Runs in foreground as required by Docker/Runflare. `HERMES_GATEWAY_NO_SUPERVISE=1` disables s6-overlay supervision (Runflare doesn't provide PID 1).

---

## Architecture Notes

### Why This Dockerfile?

- **Builds from source** at exact tag `v2026.8.3` (v0.20.0) — no PyPI dependency
- **Uses uv** for reproducible, isolated Python 3.11 runtime (Hermes manages its own Python)
- **Non-root user** (`hermes` UID 1000) — security best practice
- **Foreground process** — `hermes gateway run` directly, no systemd/s6 needed
- **Minimal layers** — ~500 MB final image
- **No llama.cpp** — Hermes connects to external LLM providers via API

### Port 8000 vs 8642

- Hermes gateway API defaults to port 8642
- Runflare Free requires exposing a port; we use 8000
- The gateway works in **long-polling mode** (default) without any exposed port
- Port 8000 is exposed to satisfy Runflare; gateway polls Telegram internally

### Health Strategy

- **No HTTP health endpoint invented** — Telegram long-polling gateways don't serve HTTP by default
- **Process health check**: `pgrep -f "hermes gateway run"` every 30s
- **Runflare monitors**: Container liveness via process supervision

---

## Verification Checklist

After deployment, verify in Runflare logs:

```
✓ hermes --version
  hermes 0.20.0

✓ hermes gateway --help
  Usage: hermes gateway run|start|stop|restart|status|install|uninstall|list|setup|migrate-legacy|enroll

✓ hermes gateway run
  [INFO] Starting Hermes gateway...
  [INFO] Telegram gateway: polling mode
  [INFO] Gateway running. Press Ctrl+C to stop.
```

### Test Bale Integration

1. Configure `BALE_BOT_TOKEN` and `BALE_ALLOWED_USERS` in Runflare.
2. Restart the service.
3. Message the Bale bot from an allowed account.
4. Verify the logs contain Bale connection/readiness without Telegram fallback-IP messages.
5. Confirm the bot replies in Bale.

### Test Telegram Integration

1. Open Telegram, message your bot
2. Bot should respond (if `TELEGRAM_ALLOWED_USERS` includes your ID)
3. Check Runflare logs for: `[INFO] Received message from user 123456789`

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Container exits immediately | Check logs: missing `TELEGRAM_BOT_TOKEN` or invalid token |
| "No messaging platforms enabled" | Ensure `TELEGRAM_BOT_TOKEN` is set in Runflare env vars |
| Bot doesn't respond | Verify `TELEGRAM_ALLOWED_USERS` matches your @userinfobot ID |
| Build fails on `uv sync` | Tag `v2026.8.3` has fixed `exclude-newer-package` exemptions |
| OOM (Out of Memory) | Hermes + Python needs ~1.5 GB; Free tier has 3 GB — should fit |
| Webhook not receiving updates | Ensure `TELEGRAM_WEBHOOK_URL` is public HTTPS, port 8443 reachable |

---

## Upgrading Hermes

1. Update `HERMES_TAG` build arg in Dockerfile to new release tag
2. Rebuild image: `docker build -t hermes-gate .`
3. Redeploy to Runflare (new image triggers rolling update)

Official releases: https://github.com/NousResearch/hermes-agent/releases

---

## Security

- **No secrets in image** — all credentials via Runflare environment variables
- **Non-root user** — runs as `hermes` (UID 1000)
- **Read-only root filesystem** — not enforced here but recommended
- **Volume isolation** — `/opt/data` is the only writable path

---

## Files

```
.
├── Dockerfile          # Multi-stage build from source
├── .dockerignore       # Excludes secrets, cache, local data
└── README.md           # This file
```

---

## References

- Hermes Agent: https://hermes-agent.nousresearch.com/
- Docker Guide: https://hermes-agent.nousresearch.com/docs/user-guide/docker
- Telegram Setup: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram
- Environment Variables: https://hermes-agent.nousresearch.com/docs/reference/environment-variables
- Runflare: https://runflare.com/