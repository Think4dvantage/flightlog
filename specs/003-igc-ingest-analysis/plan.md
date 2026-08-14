# Implementation Plan: IGC Ingest & Analysis

Spec: [`spec.md`](./spec.md) · Research: [`research.md`](./research.md) · Data model:
[`data-model.md`](./data-model.md) · Contracts: [`contracts/`](./contracts/)

## Technical Context

Backend-heavy, on the existing stack — no new tech stack decisions beyond a library already declared for
this exact purpose. FastAPI + Pydantic v2 + SQLAlchemy 2.0 on the backend (four new tables, one new
router, one new config section); vanilla-JS ES modules on the frontend, extending the existing
flight-detail page plus one new page, using two libraries already vendored from earlier milestones
(Leaflet 1.9.4, already in use for `/sites`; Chart.js 4.5.1, vendored since v0.1 but used for the first
time here).

**Architecture approach**: `core/igc.py` wraps `libigc` per `architecture.md`'s seven already-documented
analysis rules — this plan does not re-derive that algorithm, it implements it. The genuinely new design
decisions (upload mechanics, bulk-review persistence, the site-backfill trigger, the re-analysis sweep)
are resolved in `research.md`, not here.

**Performance**: NFR-001 (single-file analysis fast enough to stay in the upload flow) is met by
`asyncio.to_thread`-offloaded parsing of a single file at a time — `04-constraints.md` names IGC parsing
by name as the reason this rule exists. Bulk upload's realistic batch sizes are addressed as a documented
risk below, not a new infrastructure decision.

**Security**: Every flight-scoped route reuses the existing `_get_own_flight()`-style 404-not-403
pattern. `POST /api/admin/reanalyze` is this app's first actual use of the already-existing
`require_admin` dependency — no new auth mechanism, just its first consumer.

## Constitution Check

| Principle (`00-ai-usage.md`) | Status |
|---|---|
| Read before acting | Done — spec, every `.ai/instructions/` file, `architecture.md`'s IGC analysis section in full, `database/models.py`, `config.py`, and the real `libigc` package's PyPI/GitHub metadata, all read before this plan was written |
| Plan before building | This document; no code has been written yet |
| Minimal scope | No job queue, no scheduler, no admin UI for tuning parameters, no partial/filtered re-analysis — each explicitly rejected in `research.md` as unrequested by `spec.md` |
| Tool-agnostic instructions | No `CLAUDE.md` or equivalent introduced |
| Keep docs in sync | Deferred to session end (`sync.md`) once the feature is actually implemented, per Phase 8 below |
| No secrets committed | N/A — no secrets touched; `config.yml.example` gets the new `igc.parsing:` keys with placeholder/default values only |
| Prod is off-limits | N/A — this plan is local implementation; deployment follows the existing tag-push pipeline afterward |

No violations.

## Data Model Summary

Four new tables, detailed in `data-model.md`: `igc_tracks` (one per flight), `igc_segments` (thermals/
glides/markers), `site_observations` (feeds coordinate backfill), and `igc_pending_uploads` (a
plan-level addition — persists bulk-upload results so the review queue survives a closed tab). No new
tables need a migration guard (`Base.metadata.create_all()` handles new tables); no column is added to
an *existing* table, since `flights.takeoff_time`/`landing_time` and `sites.elevation_igc_m`/
`coord_source`/`coord_accuracy_m` were all already declared, unpopulated, back in v0.2 for exactly this
purpose.

## File Structure

### Backend (new)
```
src/flightlog/core/igc.py                 # libigc wrapper: parse/validate/alt-source/thermal-filter/
                                           # glide-ratio/segment-extract (architecture.md rules 1-7)
src/flightlog/core/igc_storage.py         # content-addressed read/write under storage.igc_dir
src/flightlog/core/site_backfill.py       # site_observations insert + median coordinate recompute
src/flightlog/models/igc.py               # Pydantic schemas (contracts/endpoints.md's response shapes)
src/flightlog/api/routers/igc.py          # every route in contracts/endpoints.md
```

### Backend (modified)
```
src/flightlog/database/models.py          # + IgcTrack, IgcSegment, SiteObservation, IgcPendingUpload
src/flightlog/config.py                   # + IgcParsingConfig, IgcConfig, MainConfig.igc
src/flightlog/api/main.py                 # register igc router
src/flightlog/api/routers/pages.py        # + GET /igc (bulk upload/review page)
config.yml.example                        # + igc.parsing block
pyproject.toml                            # `igc` extra becomes load-bearing (installed for real), not
                                           # just declared-and-unused — CI/Docker need
                                           # `--extras igc` alongside `--extras importer`
static/i18n/en.json                       # nav.tracks + igc.* keys (upload control, map/chart labels,
                                           # bulk page, pending-review actions)
static/flight-detail.html                 # + upload control, map container, chart container,
                                           # segment list
static/flight-detail.js                   # + upload/replace/detach calls, map+chart rendering,
                                           # segment fetch
```

### Frontend (new page)
```
static/igc.html              static/igc.js       # bulk upload + pending-review queue
```

### New HTML route in `pages.py`
```
GET /igc  -> igc.html
```

### Tests (new)
```
tests/backend/test_igc_upload.py          # single-flight upload/replace/dedup/rejection
tests/backend/test_igc_bulk.py            # bulk auto-match, ambiguous -> pending, resolve, dismiss
tests/backend/test_site_backfill.py       # median recompute; manual pin never overwritten; >=3 threshold
tests/backend/test_igc_reanalyze.py       # admin-only (403 for a pilot account); analyzer_version filter
tests/backend/fixtures/*.igc              # valid flight, no-baro flight, corrupt file, and a same-day
                                           # two-flights pair for bulk-match ambiguity testing
```

## Implementation Phases

### Phase 1: Backend prerequisites & core analysis
Install/confirm the `igc` extra; resolve `research.md`'s two open items (per-fix altitude field shape,
`FlightParsingConfig`'s real parameter names/defaults) against the actually-installed package before
writing a single config key. `core/igc.py`, `core/igc_storage.py`; the four new tables in
`database/models.py`; `config.py` + `config.yml.example`'s `igc.parsing:` block with real, verified
defaults. Fully unit-testable against IGC fixture files before any HTTP route exists.

### Phase 2: Single-flight upload + view
`api/routers/igc.py`'s flight-scoped routes (`POST`/`GET`/`DELETE /api/flights/{id}/igc`,
`GET .../segments`, `GET .../track.geojson`); `models/igc.py` schemas. Backend fully testable with
`pytest` before touching the frontend.

### Phase 3: Site coordinate backfill
`core/site_backfill.py`, wired into both the upload path and the detach/replace path — FR-004 and
FR-012 both need a track's old `site_observations` gone before any recompute, not just new ones added.
Tested independently of the HTTP layer.

### Phase 4: Bulk upload + pending review
`igc_pending_uploads` table; the bulk-match algorithm exactly as architecture.md already specifies it
(date + duration scoring, auto-attach only when `|Δ| ≤ 3 min` **and** the runner-up is `> 10 min` away,
everything else to manual resolution); `/api/igc/bulk` and `/api/igc/pending*` routes.

### Phase 5: Admin re-analysis
`POST /api/admin/reanalyze`, gated by the already-existing `require_admin` dependency — its first actual
use anywhere in this app.

### Phase 6: Frontend — flight detail
Upload/replace/detach control, Leaflet track map, Chart.js barogram with thermal/glide segment bands, on
the existing flight-detail page — the largest frontend piece. Built and manually verified against a live
boot with a handful of real IGC files (not just fixtures) before moving on.

### Phase 7: Frontend — bulk upload & pending review page
`igc.html`/`igc.js`: multi-file upload, per-file outcome list, resolve/dismiss actions for pending rows,
nav entry ("Tracks" — friendlier to a pilot than the acronym "IGC" as a nav label, per
`03-frontend-conventions.md`'s i18n rules; the page and file format itself stay "IGC" throughout, this is
copy-only).

### Phase 8: Verification pass
Live-boot walkthrough: upload a real single-file track and cross-check every computed figure by hand
against the same file; re-upload the identical file (confirm no-op) and then a different file (confirm
replace, including that old segments/observations are gone, not accumulated); bulk-upload a small batch
including a deliberately ambiguous same-day pair and confirm it lands in `igc_pending_uploads`, never
guessed; resolve it; confirm a site that reaches 3 tracked flights gets a real coordinate and a
manually-pinned site never does, even past 3; confirm `POST /api/admin/reanalyze` is `403` for the (only)
pilot account. `ruff check` / `ruff format --check` / `pytest` clean. Then `sync.md` to update
`architecture.md`/`features.md`/`RESUME.md` with what actually shipped — including resolving
`research.md`'s two open items with what was actually found in the installed package, and correcting
architecture.md's IGC analysis section if either assumption turned out wrong.

## Dependencies

- `libigc` 1.2.0 — already declared as the `igc` extra in `pyproject.toml`; reverified current against
  PyPI's JSON API this session (`research.md`). This feature is the extra's first actual use — CI and
  the Docker image need `poetry install --extras igc` alongside the existing `--extras importer`, which
  is exactly the build-gate risk `features.md`'s backlog already flags for this dependency by name.
- Chart.js 4.5.1 — already vendored (`static/vendor/chartjs/chart.umd.js`) since v0.1's foundation work
  and reverified current against GitHub Releases this session (`v4.5.1`, unchanged). This feature is its
  first actual use — `specs/002-flight-log-ui/plan.md` deferred that to the (pre-renumbering) statistics
  milestone; the barogram needs it now instead. No new asset, no version change.
- Leaflet 1.9.4 — already vendored and in use since v0.3's `/sites` map; reverified current this session
  (`v1.9.4`, unchanged). The track map reuses the same vendored copy.
- No new npm/build-step anything — there is no npm (`04-constraints.md`).

## Risk & Mitigations

- **Risk**: `research.md`'s two open items (per-fix `press_alt`/`gnss_alt` field shape;
  `FlightParsingConfig`'s real parameter names and defaults) turn out not to match
  `architecture.md`'s assumption once the package is actually installed and inspected.
  **Mitigation**: flagged explicitly rather than silently assumed going in; Phase 1 resolves both before
  any config key or altitude-source line of `core/igc.py` is finalized, so a mismatch changes a few lines
  there, not the data model or the API contract — neither table nor endpoint shape depends on which way
  it resolves.
- **Risk**: a large bulk upload (a full historical backfill — hundreds of files, the historical
  importer's own precedent is ~600) held in one synchronous HTTP request risks a client or reverse-proxy
  timeout.
  **Mitigation**: `research.md`'s documented tradeoff — acceptable for a single-pilot tool's realistic,
  infrequent batch sizes; if it's ever actually hit in practice, the fallback is chunking the upload
  client-side into smaller batches against the same endpoint, not new backend job infrastructure this
  feature doesn't otherwise need.
- **Risk**: enabling the `igc` extra for real in CI/Docker for the first time repeats v0.1's
  `pytest-asyncio`-style pinned-version surprise, or hits the `python:3.14-slim` multi-arch build-gate
  caveat `features.md`'s backlog already flags specifically for `libigc`.
  **Mitigation**: that backlog item exists exactly so this isn't a surprise — Phase 1 is where the build
  gate gets exercised for real instead of assumed clean; a failure here blocks Phase 1, not a late
  surprise at deploy time.
- **Risk**: `igc_pending_uploads` grows without bound if a pilot bulk-uploads the same messy folder
  repeatedly without ever resolving old entries.
  **Mitigation**: `UniqueConstraint("owner_id", "sha256")` means a repeat upload of the same file
  recognizes the existing pending row instead of duplicating it; genuinely distinct files are bounded by
  the pilot's own historical file count, which needs no cleanup job at this scale.
