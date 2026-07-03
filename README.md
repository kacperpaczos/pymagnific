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
pymagnific spaces inspect ecommerce-two-products
pymagnific spaces pull ecommerce-two-products -o ./output/ecommerce-two-products
pymagnific spaces push ecommerce-two-products ./nowe-zdjecie.png
pymagnific spaces run SPACE_UUID --start-node NODE_ID
```

## Workspace: sync vs exec

**Dwie osobne operacje** - synchronizacja projektu ze Space to nie to samo co uruchamianie pipeline.

| Grupa | Co robi | Czego NIE robi |
|-------|---------|----------------|
| `project sync` | provision, deploy, upload, prepare, full | nie uruchamia `spaces_run` |
| `project exec` | run, batch | nie zmienia grafu ani assetow |

### Workspace v3 (jeden Space, pomnozone pipeline'y)

JSON na dysku jest zrodlem prawdy dla produktow (#77, #79). Jeden Magnific Space, szablon `ecommerce_raw`.

```bash
# 1. Provision - dodaje panele pipeline w Space
pymagnific project sync provision ecommerce-two-products --apply

# 2. Deploy - upload assetow + prepare list/promptow (bez run)
pymagnific project sync deploy ecommerce-two-products --apply --pipeline 77

# Upload i prepare mozna tez wywolac osobno (deploy = upload + prepare)
pymagnific project sync upload ecommerce-two-products --apply --pipeline 77
pymagnific project sync prepare ecommerce-two-products --apply --pipeline 77

# Pelny sync (provision + bind + deploy) z jednym checkpointem
pymagnific project sync full ecommerce-two-products --apply

# 3. Reczna weryfikacja w UI Magnific

# 4. Exec - tylko jawnie
pymagnific project exec run ecommerce-two-products --pipeline 77 --job pilot-77-white-photoshoot
pymagnific project exec batch ecommerce-two-products --phase pilot --pipeline 77
```

Layout v3:

```
projects/ecommerce_two_products/
  workspace.json              # hub: space_id, shared_prompts, pipeline_ids
  pipeline-spec-draft.json    # spec: kolory, shot ideas, tla
  pipelines/77/instance.json
  pipelines/77/assets/        # product.jpg, material.jpg, backgrounds/
  pipelines/79/instance.json
  pipelines/79/assets/
projects/templates/           # kanoniczne szablony (ecommerce_raw, do3d_textures_2d)
```

### Szablony i walidacja

```bash
pymagnific project templates list
pymagnific project templates validate ecommerce_raw
pymagnific project validate my-workspace
pymagnific project audit my-workspace --strict
```

### Exec (uruchamianie - tylko jawnie)

```bash
pymagnific project exec run produkty-ecommerce --pipeline 77 --job pilot-77-navy-desk
pymagnific project exec batch produkty-ecommerce --phase pilot --parallel 2
```

Typowy flow:

1. `sync init --spec pipeline-spec.json` - workspace + `pipelines/*/instance.json`
2. `project validate <slug>` - lokalne assety i schema
3. `sync provision --apply` - graf w Magnific (bez uploadu!)
4. `sync deploy --apply` - **upload assetow wymagany** + prepare list/promptow
5. `project audit <slug> --strict` - weryfikacja remote vs instance (wymaga `.remote/board.json`)
6. `exec run` / `exec batch` (zablokowane bez udanego `upload:product` i lokalnej walidacji)

### Checkpoint i resume (po awarii lub Ctrl+C)

Dlugie operacje sync (`provision`, `deploy`, `full`) zapisuja postep w
`projects/<slug>/.sync/state.json`. Na stderr widzisz live progress `[krok/total]`.

```bash
# Status ostatniego przebiegu
pymagnific project sync status ecommerce-two-products

# Wznowienie deploy od ostatniego udanego kroku
pymagnific project sync deploy ecommerce-two-products --apply --resume

# Od zera (usun checkpoint)
pymagnific project sync deploy ecommerce-two-products --apply --fresh

# Tylko JSON na koniec (bez linii na stderr)
pymagnific project sync deploy ecommerce-two-products --apply --quiet
```

Flagi `--resume`, `--fresh`, `--quiet` dzialaja tez dla `sync provision`, `sync bind-nodes` i `sync full`.

### Logowanie (domyslnie `./logs/`)

Kazde uruchomienie CLI zapisuje sesje do pliku w katalogu `logs/` **w biezacym katalogu roboczym** (skad wywolujesz `pymagnific`):

```
logs/pymagnific-20260701-203045.log
```

W pliku: postep sync, polling `spaces_edit` / `spaces_run`, kroki `exec run` (dlaczego trwa dlugo — widac poll co ~25 s).

Zmienne `.env`:

| Zmienna | Domyslnie | Opis |
|---------|-----------|------|
| `MAGNIFIC_LOG_DIR` | `./logs` | Katalog logow |
| `MAGNIFIC_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` |
| `MAGNIFIC_LOG_TO_CONSOLE` | `true` | Duplikat na stderr |

`exec run` dla jobu z 2 krokami (`stage_color` + `stage_photoshoot`) moze trwac **10–20 min** — kazdy krok to generacja obrazow na Magnific z pollingiem do 600 s.

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
