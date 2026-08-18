# Flightlog

A multiuser paragliding flight log. Log a flight from dropdowns of your own launch sites, landing sites,
gliders, harnesses and categories, attach an IGC track, and get statistics a spreadsheet cannot produce.

It replaces a 600-flight Excel workbook covering 2018–2026.

**The API is the product.** Other services consume this one rather than keeping their own copy of your
flights — video tooling pulls flight metadata and thermal-based highlight timestamps straight from here.

Status: **v0.9.7**, tagged and published (`ghcr.io/think4dvantage/flightlog`). See
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

Shipped: the flight log UI (v0.3 — the point at which the spreadsheet is retired), IGC ingest with
thermal and glide analysis, a track map, and a barogram (v0.5), and the secondary-sheet imports plus
goals (v0.6, tag `v0.6.0`). XContest score import, originally scoped alongside v0.6, has moved to the
backlog pending a real export sample.

Shipped in v0.7 (statistics): totals, averages, per-year/month/site/glider/category/buddy breakdowns,
personal bests, launch-technique split, an IGC-derived cumulative-thermal-climb figure the spreadsheet
never could produce, streaks and year-to-date pace — plus a run of post-ship additions from live
pilot feedback (contacts/buddy CRUD, full CRUD for hikes/groundhandling/tandem flights, a sortable
IGC-track-present flag on the flights list).

Shipped in v0.8 (public API): a pilot can mint scoped, revocable API keys from their own account and
hand one to an external tool — VidFactory today — which then reads flight metadata and IGC-derived
highlight timing (thermal/glide/launch/landing timestamps, offsets from takeoff) and can push a link
back to a produced video, which shows up on the pilot's own flight page automatically. No shared login
credentials, no VidFactory copy of the flight data.

v0.8.1 removes bulk IGC upload entirely — a real bulk import mismatched flights, and the fix was to
drop the feature rather than debug it. An IGC track is attached from a flight's own edit page only
(unambiguous by construction, no matching heuristic involved), which is how it has always worked
since v0.5. A one-shot `python -m flightlog.core.reset_igc [--write]` cleans up any tracks/segments
the removed feature mismatched, and the two things it wrote elsewhere (a flight's backfilled takeoff/
landing time, a site's IGC-derived coordinate).

Shipped in v0.9 (sharing & public readiness): a pilot can mark an individual flight private, unlisted
(reachable only by its exact link) or public (also listed on their profile), and opt in to a durable
public profile page — both off/private by default. The public surface is a new, unauthenticated,
rate-limited router (`/api/public`) with its own explicit response schemas, never the pilot-facing ones.
Self-registration also seeds five starter flight categories now, closing a gap where a newly
self-registered account previously had none. `olddata/Flugbuch.xlsx`'s git-history scrub — required
before this repository itself can go public — has been performed; the file is gitignored and kept
on disk untracked so the importer and its regression tests keep working locally.

`v0.9.1`–`v0.9.3` are three small pilot-requested additions on top of v0.9.0: landing sites get a
distinct green map pin on `/sites`, flights can carry an optional free-text nickname (searchable,
shown on the flight and public-flight pages, subject to the same visibility rule as notes), and
`/stats` gained IGC-derived thermal and airtime totals — including total airtime measured from the
track, shown beside the self-reported figure, since the two routinely disagree.

`v0.9.4` adds two frontend pages that closed real UI gaps rather than backend ones: `/categories`
is a full create/rename/reorder/archive/delete page for a pilot's own flight categories — the API
had been owner-scoped since v0.2, but no page ever managed it. `/profile` is the account-settings
home that never existed: display name, password change, and the "Public profile" toggle moved here
from `/api-keys`, which had only ever hosted it as a stand-in.

`v0.9.5` closes a gap on the public/unlisted flight page: `/public/flights/{id}` now shows the
same track map, barogram and IGC-derived summary figures the pilot's own flight-detail page shows,
when the flight has an uploaded track. A flight's `visibility` is already the consent boundary for
its notes and nickname on this surface — this was simply missing, not a new exposure decision.

`v0.9.5` also adds public statistics sharing: a new, independent "Public statistics" toggle (off
by default, separate from the public-profile toggle) publishes a read-only `/public/stats/{id}`
page mirroring the pilot's own `/stats` dashboard — same totals, distributions, personal bests,
and per-dimension matrices (including buddy names), computed over the pilot's entire flight
history rather than only public-visibility flights. A personal best whose underlying flight isn't
itself public shows the number without a link, so a shared page never points to a 404.

`v0.9.6` lets a pilot attach links to a flight by hand: multiple YouTube video links plus one
XContest flight link, pasted directly (no API integration). A flight's detail page gained a
Links section — a list for videos, a single replaceable slot for XContest — and a public/unlisted
flight shows the same links on its shared page.

`v0.9.7` fixes two bugs found in live production use: re-uploading an IGC file that was already
attached to a different flight of the same pilot (even after that other flight's own, unrelated
track had been detached) crashed with an opaque 500 instead of a clear conflict; and the API-key
creation drawer wrote the newly minted plaintext key into the page but never actually showed it,
since the reveal panel was nested inside the form element the code hid right before revealing it.

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
| `api.public_rate_limit` | Request ceiling on `/api/public/*` only (e.g. `"30/minute"`); the authenticated surface is never limited |

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
