# Flightlog

A multiuser paragliding flight log. Log a flight from dropdowns of your own launch sites, landing sites,
gliders, harnesses and categories, attach an IGC track, and get statistics a spreadsheet cannot produce.

It replaces a 600-flight Excel workbook covering 2018–2026.

**The API is the product.** Other services consume this one rather than keeping their own copy of your
flights — video tooling pulls flight metadata and thermal-based highlight timestamps straight from here.

Status: **v0.2 shipped** (not yet tagged) — core data model, owner-scoped CRUD, and the Excel import that
moved all 600 flights out of the spreadsheet. v0.3 (flight log UI, the MVP boundary) is next. See
`.ai/context/features.md` for the roadmap and `specs/001-core-data-import/` for v0.2's spec and design.

## Features

Shipped in v0.1:

- Email + password accounts with JWT access and refresh tokens
- Self-registration behind a config flag — private now, public-ready later
- Bootstrap admin created on first start
- Health endpoint with liveness/readiness semantics
- Typed error envelope on every response
- Server-side static asset cache-busting

Shipped in v0.2:

- Owner-scoped CRUD for sites, gliders, harnesses, flight categories, buddies and flights
- Computed altitude figures (gain, site height difference, total descent) — derived on read, never
  stored, so a site elevation correction retroactively fixes every flight that used it
- A two-sided buddy account-link flow that never leaks whether an email is registered
- A one-shot Excel importer (`python -m flightlog.core.importer`) — dry-run by default, idempotent,
  with a region-count reconciliation and an altitude-figure cross-check against the spreadsheet's own
  derived columns, and buddy-name proposals from flight comments (never auto-created)

Coming, in order: the flight log UI (v0.3 — the point at which the spreadsheet is retired), IGC ingest
with thermal and glide analysis (v0.4), the secondary sheets and XContest import (v0.5), statistics
(v0.6), the public API (v0.7).

## Getting started

Requires Python 3.13+ and Poetry, or Docker.

```bash
cp config.yml.example config.yml
# Generate a secret and paste it into auth.jwt_secret:
openssl rand -hex 32
```

The app **refuses to start** if `auth.jwt_secret` is empty, under 32 characters, or a known placeholder.

Set `auth.bootstrap_admin_email` and `auth.bootstrap_admin_password` to have the first account created
for you. That seeder is skipped entirely once any user exists.

### Docker

```bash
docker compose up -d --build                                                   # prod
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build   # dev, port 8002
```

### Local

```bash
poetry install --with dev
poetry run uvicorn flightlog.api.main:app --reload --port 8002
```

Then open http://localhost:8002. Interactive API docs are at `/docs`.

## Configuration

Everything lives in `config.yml`, validated by Pydantic at startup; every non-secret value is logged so
a running instance can be reconstructed from cold logs. `config.yml` is gitignored — only
`config.yml.example` is committed. Nothing reads `os.environ` except `CONFIG_PATH`.

| Key | Purpose |
|---|---|
| `auth.allow_self_registration` | `false` keeps registration closed; admins create accounts instead |
| `storage.igc_dir` | Where raw IGC files live. Content-addressed, never in the database |
| `sites.dedup_radius_m` | Two sites closer than this are treated as the same place |

## Testing

```bash
poetry run pytest --tb=short -q
poetry run ruff check src/ tests/
poetry run ruff format --check src/ tests/
```

CI runs all three on Python 3.13 and 3.14.

## Project structure

```
src/flightlog/
  api/          app factory, dependencies, error envelope, routers
  core/         domain logic — flights, aliases, importer, IGC analysis, statistics
  database/     ORM models and engine setup
  models/       Pydantic request/response schemas
  services/     auth, API keys
static/         no build step; vanilla ES modules, vendored Leaflet and Chart.js
tests/backend/  pytest suite
.ai/            conventions, architecture notes and workflow prompts
```

`.ai/` is the source of truth for how this project is built — architecture decisions and their rationale
live in `.ai/context/architecture.md`.

## Notes

- No Alembic. New tables come from `create_all()`; new columns get a guarded `ALTER TABLE`.
- No npm, no bundler, no CDN. A strict CSP blocks third-party scripts, so libraries are vendored.
- The version in `pyproject.toml` is the static-asset cache key. Bump it whenever `static/` changes.

## License

MIT
