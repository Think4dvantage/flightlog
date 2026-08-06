# Feature History & Backlog

## Current Version: v0.1 (in progress)

Nothing has shipped yet. The roadmap below is the plan of record; each milestone states its scope
boundary and what is deliberately deferred.

---

## Roadmap

### v0.1 — Skeleton & auth

App factory + lifespan, `/health`, typed error envelope with three global handlers, security headers +
CSP `script-src 'self'`, GZip, `?v=` cache-busting from `pyproject.toml`, `init_db()` + WAL pragmas +
`_run_column_migrations()`, the `users` table, JWT register/login/refresh/`/me` via PyJWT + bcrypt,
`auth.allow_self_registration: false` gate, login/register pages, `shared.css` / `bootstrap.js` /
`auth.js` / `i18n.js`, vendored Leaflet + Chart.js, Docker + compose + dev overlay, both workflows,
`conftest.py` with the StaticPool and ASGITransport traps documented.

**Deferred:** OAuth, roles beyond pilot/admin, any flight data.

### v0.2 — Core data + Excel import

`regions`, `sites`, `site_observations`, `user_site_prefs`, `gliders`, `harnesses`,
`flight_categories`, `flights`, `buddies`, `flight_buddies`. Owner-scoped CRUD for all of them.
`core/aliases.py` and `core/importer.py` with a dry-run report, buddy proposals, region-count
verification, the formula cross-check and `import_key` idempotency.

**The 600 flights land here.**

**Deferred:** IGC, statistics, any UI beyond the raw API.

### v0.3 — Flight log UI · **← MVP BOUNDARY**

`/flights` with search / year / category / glider / site / region filters, sortable columns, pagination
and an inline add-edit drawer. `/flights/{id}` detail. `/sites` with map and pin drop. `/equipment`.
`/contacts`. `/import` review page. CSV export.

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
