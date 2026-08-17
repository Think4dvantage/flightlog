# Project Overview — Flightlog

## What This Is

Flightlog is a multiuser paragliding flight log. A pilot logs each flight from dropdowns of their own
launch sites, landing sites, gliders, harnesses and flight categories, optionally attaches an IGC track,
and gets back statistics a spreadsheet cannot produce.

It replaces `olddata/Flugbuch.xlsx` — 600 flights from 2018-05-19 to 2026-07-12, plus separate sheets for
hike training, groundhandling, tandem flights and goals.

**The core differentiator is that the API is the product, not a byproduct.** VidFactory (a separate video
production tool) consumes this service for video metadata and for thermal-based highlight suggestions
derived from IGC tracks. A future mobile app and a public flight feed consume the same surface. Where UI
convenience and a clean machine contract conflict, the machine contract wins — deliberately.

---

## Tech Stack

| Concern | Tool |
|---|---|
| Language | Python 3.13+ |
| Web framework | FastAPI + Uvicorn (ASGI) |
| Data validation | Pydantic v2 (also validates YAML config) |
| Dependency management | Poetry (`pyproject.toml`, `poetry.lock` committed) |
| Relational DB | SQLite via SQLAlchemy 2.0 declarative — **no Alembic** |
| Migrations | Idempotent `ALTER TABLE` guarded by `PRAGMA table_info()` in `_run_column_migrations()` |
| Auth | JWT via **PyJWT**, passwords via **bcrypt directly** |
| Machine auth | Opaque API keys, SHA-256 hashed |
| IGC parsing | `libigc` — thermal detection, glide segmentation |
| Excel import | `openpyxl`, one-shot CLI |
| Config | YAML (`config.yml`) validated by Pydantic, singleton `get_config()` |
| Frontend | Vanilla JS ES modules + Leaflet + Chart.js, self-hosted, **no build step** |
| i18n | Custom `i18n.js`, `SUPPORTED = ['en']` |
| Testing | pytest + pytest-asyncio (`asyncio_mode = "auto"`) |
| Lint / format | **ruff only** — `ruff check` and `ruff format` |
| Container | Docker + docker-compose + Traefik |

### Divergences from the blueprint defaults — do not "fix" these

The blueprint's `dev-web` category is written for the Lenticularis-shaped project. Four of its defaults
are deliberately not followed here:

1. **PyJWT, not `python-jose`.** python-jose's last release is 3.5.0 (May 2025) and it carries a CVE
   history including algorithm confusion. PyJWT is actively maintained and requires an explicit
   `algorithms=[...]` on decode — the exact parameter whose absence caused that CVE.
2. **bcrypt directly, not `passlib`.** passlib is unmaintained and adds a layer for no benefit.
3. **`ruff format`, not `black`.** Drop-in replacement, one tool instead of two.
4. **`_run_column_migrations()`, not `.sql` files + a `_migrations` table.** See
   `02-backend-conventions.md`. The blueprint contains both doctrines in different files; this project
   uses only the first.

**There is no InfluxDB, no scheduler and no pyproj in this project.** Where an inherited instruction or
prompt mentions collectors, Flux queries, `AsyncIOScheduler` or coordinate projection, it does not apply.

---

## Repository Layout

```
src/flightlog/
├── config.py                # Pydantic-validated YAML loader (singleton)
├── api/
│   ├── main.py              # create_app() + lifespan, security headers, CSP, 3 error handlers
│   ├── dependencies.py      # get_db, get_current_user, require_admin, require_scope
│   ├── errors.py            # AppException + _envelope()
│   └── routers/             # One file per domain; pages.py holds ALL HTML routes
│       ├── api_keys.py      # /api/keys — JWT-authenticated key management (pilot's own session)
│       ├── integration.py   # /api/integration/v1 — the frozen VidFactory contract (API-key auth)
│       └── public.py        # /api/public — unauthenticated by design, slowapi rate-limited (v0.9)
├── core/
│   ├── aliases.py           # Excel dirty-value normalisation tables
│   ├── importer.py          # python -m flightlog.core.importer (one-shot, --dry-run default)
│   ├── igc.py               # libigc wrapper → thermals, glides, segments
│   ├── igc_storage.py       # content-addressed file storage (sha256)
│   ├── reset_igc.py         # python -m flightlog.core.reset_igc (one-shot, --dry-run default)
│   ├── site_backfill.py     # site coordinate backfill from IGC fixes
│   ├── flights.py           # list / filter / sort / paginate
│   ├── stats.py             # rollups
│   ├── user_seed.py         # starter-category seed on self-registration (v0.9)
│   └── xcontest.py          # XContest "My Flights" JSON import
├── database/
│   ├── models.py            # SQLAlchemy ORM — source of truth for the schema
│   └── db.py                # init_db(), get_db(), _run_column_migrations(), seeders
├── models/                  # Pydantic request/response schemas, one module per domain
└── services/
    ├── auth.py              # PyJWT tokens, bcrypt hashing
    ├── apikeys.py           # mint / verify opaque API keys
    └── geo.py               # haversine_m
static/
├── i18n/en.json             # single locale; machinery supports more
├── i18n.js  auth.js  bootstrap.js  shared.css
├── vendor/leaflet/  vendor/chartjs/     # self-hosted, never a CDN
└── *.html + *.js
tests/backend/               # conftest.py + test modules
tests/fixtures/igc/          # small real IGC tracks, committed, `-text` in .gitattributes
olddata/Flugbuch.xlsx        # legacy workbook — gitignored, untracked; scrubbed from git history in v0.9
```

---

## Data Flow

```
Excel → core/importer.py (one-shot, --dry-run by default)
      → sites, regions, gliders, harnesses, categories, flights, buddies

IGC   → core/igc_store.py (sha256, content-addressed on disk, never a BLOB)
      → core/igc.py (libigc) → igc_tracks + igc_segments
      → core/sites.py backfills site lat/lon from takeoff/landing fixes (median of ≥3)

Browser    → fetchAuth() → JSON API (JWT bearer)

VidFactory → X-API-Key → /api/integration/v1 → flight metadata + highlight offsets
           → PUT /api/integration/v1/flights/{id}/links/video/{project_id} → flight_links (push-back)
```

---

## Data Sources

| Source | Auth | What it provides | Cadence |
|---|---|---|---|
| `olddata/Flugbuch.xlsx` | none (local file) | 600 flights, 34 launches, 30 landings, 12 categories, 10 gliders, 8 harnesses | One-shot |
| Uploaded IGC files | user session | Track, thermals, glides, real clock times, site coordinates | Per flight |
| XContest JSON export | none (user-supplied file) | Official score, type, URL | Optional, ad hoc |

Two properties of the legacy data that shape everything downstream:
- **There is no time-of-day on any flight.** IGC attachment is what backfills it.
- **Date is not a unique key** — 117 days carry more than one flight. Row order is the implicit flight
  number and the only stable identity, so `import_key = "xlsx:<row>"`.

---

## User Roles

| Role | Description | Enforced by |
|---|---|---|
| `pilot` | Owns and manages their own flights, sites, gear, categories, buddies | `Depends(get_current_user)` |
| `admin` | Everything a pilot can, plus user management and re-analysis sweeps | `Depends(require_admin)` |
| API key | Machine access, scoped, no browser session | `Depends(require_scope("<scope>"))` |

Scopes: `flights:read`, `igc:read`, `stats:read`, `links:write`, `media:write`.

Every user-owned row carries `owner_id` and every query is scoped by it **from day one**, even while there
is a single user — retrofitting tenancy is the expensive kind of rewrite. `owner_id` is never accepted
from a request body; it always comes from `current_user.id`.

Self-registration is gated by `auth.allow_self_registration` (default `false`). The endpoint, schemas,
hashing and token pair all exist and are tested — only the flag is off. Since v0.9, a self-registered
account is also seeded with five starter flight categories (`core/user_seed.py`), guarded by
`users.seeded_at IS NULL` — before that it landed with zero categories and no way to log a flight.
