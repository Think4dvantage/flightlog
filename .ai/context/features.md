# Feature History & Backlog

## Current Version: v0.2 deployed (`v0.2.0`); v0.3 MVP implemented, not yet deployed

v0.1 is tagged `v0.1.0`. v0.2 is tagged `v0.2.0` (commit `15dcb0a`) and its 600 flights are confirmed
imported into the live production database — see `RESUME.md` for the region-seeding bug found and fixed
during that write, and the pending prod cleanup + redeploy (still open as of this note).

**v0.3's MVP boundary (Phases 1–8, `specs/002-flight-log-ui/tasks.md` T001–T036) is implemented on
`main`, not yet tagged or deployed.** See that milestone's entry below for what shipped and what's
still open before it can ship. The roadmap below is the plan of record for what remains; each milestone
states its scope boundary and what is deliberately deferred.

---

## Shipped Milestones

### v0.2 — Core data + Excel import

Spec, plan, research and data model live in `specs/001-core-data-import/`. Nine new tables
(`regions`, `sites`, `user_site_prefs`, `gliders`, `harnesses`, `flight_categories`, `buddies`,
`flights`, `flight_buddies`), owner-scoped CRUD across seven routers, `core/flights.py`'s
COALESCE-chain altitude figures (computed on read, never stored), `core/aliases.py`'s
byte-verified normalization tables, and `core/importer.py` — dry-run by default, idempotent via
`import_key`, with region reconciliation, a formula cross-check, and buddy-name proposals.

**The 600 flights land here** — verified against the real `olddata/Flugbuch.xlsx`: exactly 600
flights import, a second `--write` run changes nothing, and the importer's own checks surface
(rather than silently resolve) three real data-quality findings inherited from the spreadsheet — the
region-formula bug behind the 596-vs-600 gap (see `architecture.md`'s Statistics section for the
confirmed root cause), one `Altgain` figure that disagrees with a recomputed value (row 387), and one
harness (`Advance Success 2`, 3 flights) that is retired gear absent from the current master list.

121 tests passing (61 new since v0.1's 60, including a post-deploy regression test — see below);
`ruff check` and `ruff format --check` clean.

**Deferred:** IGC, statistics, any UI beyond the raw API, the secondary Excel sheets (hiking,
ground-handling, tandem, goals), XContest import.

**Verified against a live boot**, including running the importer itself inside the deployed container
(not just under pytest): dry-run and `--write` both exercised via `docker exec` against the real
workbook, all 600 flights landed. That run surfaced one real bug — `database/db.py`'s region-seed list
had the same transcription typo (`Dürstetten` vs the byte-verified `Därstetten`) that `aliases.py` had
already been corrected for — which silently created a 13th, orphaned region row. Fixed on `main`, with a
regression test asserting a real-workbook import creates zero new regions. Not yet redeployed to prod;
the orphan row and the fix are both still pending as of this note — see `RESUME.md`.

### v0.1 — Skeleton & auth (2026-08-06, tag `v0.1.0`)

App factory + lifespan, `/health` with liveness/readiness semantics, typed error envelope with three
global handlers (registered against **Starlette's** `HTTPException`, not FastAPI's subclass — see
`context/architecture.md`), security headers + CSP `script-src 'self'`, GZip, `?v=` cache-busting from
`pyproject.toml` with a `tomllib` fallback for the no-root container install, `init_db()` + WAL pragmas
+ `_run_column_migrations()`, the `users` table with a `UtcDateTime` type decorator, JWT
register/login/refresh/`/me`/password-change via PyJWT + bcrypt, `auth.allow_self_registration: false`
gate, login/register/index pages, `shared.css` / `bootstrap.js` / `auth.js` / `i18n.js`, vendored
Leaflet 1.9.4 + Chart.js 4.5.1, Docker on `python:3.14-slim` + compose + dev overlay, both GitHub
Actions workflows, `conftest.py` with the StaticPool and ASGITransport traps documented.

**Deploy note:** multi-arch (amd64+arm64) image built and pushed in 5m29s — `python:3.14-slim` is
proven for this dependency set. Not yet proven for `libigc` (arrives v0.4); re-run the build gate then.

**Verified in production shape**, not just under test: booted with a real `config.yml`, exercised
`/health`, login, `/me`, the 401/404/422 error envelopes and static cache headers over live HTTP.

60 tests passing; `ruff check` and `ruff format --check` clean on Python 3.13 and 3.14.

**Deferred:** OAuth, roles beyond pilot/admin, any flight data.

---

## Roadmap

### v0.3 — Flight log UI · **← MVP BOUNDARY** (MVP implemented on `main`, not yet deployed)

Spec, plan, research, data model and the 49-task breakdown live in `specs/002-flight-log-ui/`.

**MVP done (Phases 1–8, T001–T036):** `/flights` with free-text search plus year / category / glider /
launch-site / region filters, sortable columns, client-side pagination, URL-synced filter state, and an
inline add/edit/delete drawer with per-field validation rendered from the `VALIDATION_FAILED` envelope.
`/flights/{id}` detail, fresh-load safe. `/sites` with a self-hosted-Leaflet map — click an unpinned
site's row to arm placement, click the map to drop the pin, drag an existing pin to move it; both paths
set `coord_source = "manual"` server-side (`sites.py`, new behavior, no schema change). `/equipment` —
create/edit/retire for gliders and harnesses; retired gear stays visible (styled distinct) but is
excluded from the flights drawer's default dropdowns. `/import` — a read-only page rendering
`core/import_history.py`'s `HISTORICAL_IMPORT_SUMMARY`, a frozen constant generated from a fresh dry-run
of `run_import()` against `olddata/Flugbuch.xlsx` (not hand-transcribed from `RESUME.md`) behind the new
`GET /api/import-report`. `static/refdata.js` is the shared fetch-once join cache every list/detail page
uses to resolve ids to display names. 127 backend tests passing (6 new: 4 for `coord_source`, 2 for the
import report), `ruff check`/`ruff format --check` clean. Verified live via `curl` against a local dev
boot with the real 600-flight workbook re-imported — every route, every new/changed endpoint, and the
full flight CRUD lifecycle exercised end-to-end.

**Not yet done:** visual browser verification (T047 — no browser automation tool was connected this
session, so rendering, the map's click/drag interactions, and keyboard navigation (NFR-002) are
unconfirmed), Phases 9–11 (`/contacts`, CSV export, remember-last-filters — all P2/P3, droppable from
the first shippable cut), a version tag, and deployment. `pyproject.toml` was bumped to `0.3.0` (static
assets changed — the version is the cache key) but nothing has been tagged or shipped yet.

**At v0.3 the `Flugbuch` sheet is fully replaced and the Excel is never opened again.** That is the MVP
definition — everything after it is upside, not table stakes.

**Deferred:** everything IGC, all statistics, all sharing.

### v0.4 — IGC ingest + analysis

Per-flight upload, content-addressed store, sha256 + fingerprint deduplication, `core/igc.py` with the
documented algorithm and config-driven tuning, `igc_tracks` + `igc_segments`, bulk import with duration
disambiguation, takeoff-time writeback, site coordinate backfill, `GET /track.geojson`, Leaflet track +
Chart.js barogram with thermal/glide bands, `POST /api/admin/reanalyze`.

**Deferred:** XC scoring, AGL/DEM, 3D.

### v0.5 — Secondary sheets + XContest

`hikes`, `groundhandling`, `tandem_flights`, `goals` imported in one pass. XContest "My Flights" JSON
import filling `xc_official_score` / `_type` / `_url` alongside the hand-entered FAI distance.

**`Flugbuch.xlsx` is retired here.**

### v0.6 — Statistics

The full catalogue: totals, averages (including excluding-training), per-year / per-month / year×month,
duration buckets and histograms, distance and altitude distributions, personal bests each linking to
their flight, per-site / per-region / per-glider / per-harness / per-category / per-buddy year matrices,
launch-technique split, Hike&Fly totals, IGC rollups (cumulative thermal climb — the headline number the
Excel cannot produce), streaks and YTD pace, cumulative progression series. `/stats` and `/goals` pages.

### v0.7 — Public API + VidFactory integration

API keys with scopes, `/api/integration/v1`, `flight_links` push-back. VidFactory switches to the API
and drops its own flight tables.

**No data migration** — this service already holds the authoritative 600 flights. VidFactory's copy is
discarded, not reconciled.

### v0.8 — Sharing & public readiness

Per-flight visibility (private / unlisted / public), public flight page, public pilot profile, rate
limiting on the public surface, buddy invite/accept flow, `allow_self_registration` genuinely flippable.

**`olddata/Flugbuch.xlsx` must be removed from git history before this ships.**

### v0.9 — Enrichment

Lenticularis cross-link ("what were the conditions at this site on this date"), DEM for AGL, weather
snapshot per flight.

### v1.0 — Polish

Mobile-responsive pass, `/help`, `/admin`, one-command backup and export-everything.

---

## Backlog (unordered)

- Bulk edit on the flights table (reassign category / glider across a selection)
- Duplicate-flight detection on manual entry (same date + site + duration)
- Gear service reminders — reserve repack due, annual check due
- Per-site wind-window editing with a compass-rose control
- Import from other logbook formats (SkyViz, XCTrack, Flyskyhy)
- Photo thumbnails resolved from `media_links` without hosting the images
- Grant the deploy `gh` token `read:packages` so published image tags can be verified from this repo
  rather than inferred from the workflow config
- Re-run the `python:3.14-slim` multi-arch build gate once `libigc` (a v0.4 optional dependency,
  requires Python ≥3.12 with no declared upper bound) is actually installed — v0.1's green build did
  not include it
- `config.py`'s `log_effective_config()` doesn't log `auth.bootstrap_admin_email` or whether
  `auth.bootstrap_admin_password` is set (the way it already does `auth.jwt_secret set=%s`). Surfaced
  while diagnosing a post-v0.2.0-deploy login failure — the fastest signal was `db.py`'s own
  "Bootstrap admin: ..." log line, but confirming whether the deploy pipeline actually delivered the
  secret into `config.yml` at all took longer than it should have. Two log lines would close the gap.

### Shelved

- **XC scoring computed in-app.** Decided against for now: FAI triangle and free-distance optimisation
  is a hard computational-geometry problem, and while XContest is the authority the number that matters
  is theirs, not ours. Official scores are imported instead. **This blocks the far-future direction
  below** and would need revisiting — the candidate is `igc-xc-score` (branch-and-bound, WGS84, supports
  XContest/FFVL/FAI/XCLeague rules, bounded runtime with an optimality flag), invoked as a subprocess.
- **Official shared site catalogue.** The schema reserves `sites.owner_id IS NULL` for it, but with one
  user there is nothing to share yet.

### Never in scope

Live tracking. Competition scoring for organisers. Social feed / comments / likes. A mobile app *in this
repo* — that would be a separate repo against the same API.

---

## Far-future direction (recorded, not planned)

The stated long-term ambition is to grow this into an XContest competitor. Nothing here is scheduled; it
is written down so near-term decisions do not quietly foreclose it.

Already aligned: the API-first design, owner-scoped multiuser from day one, `sites.owner_id` reserved
for a shared catalogue, `igc_segments` persisted rather than recomputed, and the v0.8 visibility flags.

Would need revisiting: **XC scoring must become computed, not imported** — a competitor has to be the
scoring authority. The plan keeps this cheap by isolating everything XC behind `core/xcontest.py` and a
small set of `xc_*` columns, so the swap is a module replacement rather than a schema change.

Would need genuine new work: **SQLite → PostgreSQL** (a public league is a write-concurrency problem and
SQLite's single-writer model is the wall), and **track validation / anti-cheat** (G-record signature
verification, plausibility checks), which a personal log simply does not need.
