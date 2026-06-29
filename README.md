# pymagnific

CLI for Magnific Spaces - REST API (API key) + MCP (OAuth).

## Requirements

- Python 3.11+
- Magnific paid plan for MCP
- API key from https://www.magnific.com/developers/dashboard

## Install

```bash
cd pymagnific
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Set MAGNIFIC_API_KEY and optional MAGNIFIC_WEBHOOK_SECRET
```

## REST vs MCP

| Operation | Command | Auth |
|-----------|---------|------|
| List / run Apps | `pymagnific apps ...` | API key |
| List / edit / run Spaces | `pymagnific spaces ...` | OAuth (`auth login`) |

Space graph editing (`spaces edit`) is MCP-only, not REST.

### OAuth note

`auth login` uses **OAuth 2.0 Device Flow** (RFC 8628): open the link in your browser,
sign in to Magnific, and the CLI receives tokens automatically. No local port or
manual code paste required.

Tokens and client registration are stored in `~/.config/pymagnific/`.
After upgrading from an older version, run `auth login` once to refresh tokens.

## Quick start

```bash
pymagnific probe
pymagnific auth login
pymagnific auth status
pymagnific spaces list
pymagnific spaces create "Test Pipeline" \
  --edit "Add text prompt node connected to image generate 16:9"
pymagnific spaces state SPACE_UUID
pymagnific spaces inspect produkty-ecommerce
pymagnific spaces pull produkty-ecommerce -o ./output/produkty-ecommerce
pymagnific spaces push produkty-ecommerce ./nowe-zdjecie.png
pymagnific spaces run SPACE_UUID --start-node NODE_ID
```

## Apps (REST)

```bash
pymagnific apps list
pymagnific apps get APP_SQID
pymagnific apps run APP_SQID -i "input-uuid=prompt text"
```

## Webhook

`MAGNIFIC_WEBHOOK_SECRET` is the HMAC signing secret (not a URL).

```bash
pymagnific webhook serve
# Optional: ngrok http 8787, set MAGNIFIC_WEBHOOK_URL in .env
```

## Security

- Do not commit `.env`
- Rotate API key if leaked
- OAuth tokens: `~/.config/pymagnific/oauth.json`

## Rate limits (REST API)

Magnific enforces limits per [docs](https://docs.magnific.com): **50 RPM** per API key,
**50 req / 5s** burst and **10 req/s** average (2 min) per IP, plus daily caps on some endpoints.

`pymagnific` throttles REST calls client-side and prints warnings to stderr when
approaching limits. On HTTP **429** it waits (`Retry-After`) and retries.

```bash
pymagnific rate-limits
pymagnific probe   # includes rate_limits section
```

MCP (Spaces) uses OAuth, not the REST API key - separate limits may apply on Magnific side.

## Project structure

Layered architecture under `src/pymagnific/`:

```
src/pymagnific/
  cli/          # Typer commands (presentation)
  api/          # FastAPI webhook
  services/     # Business logic orchestration
  clients/      # Magnific REST + MCP wrappers
  parsers/      # Pure TOON board parsing
  schemas/      # Pydantic models
  core/         # Settings, exceptions, logging
```

Configuration uses `pydantic-settings` (`MAGNIFIC_*` env vars, `.env` file).

## Tests

```bash
pytest tests/ -v
ruff check src tests
ruff format src tests
```
