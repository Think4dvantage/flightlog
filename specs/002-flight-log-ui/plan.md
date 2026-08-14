# Implementation Plan: Flight Log UI

Spec: [`spec.md`](./spec.md) · Research: [`research.md`](./research.md) · Data model:
[`data-model.md`](./data-model.md) · Contracts: [`contracts/`](./contracts/)

## Technical Context

Pure application of the existing stack — no new tech stack decisions. FastAPI + Pydantic v2 + SQLAlchemy
2.0 on the backend (two small additions only, see below); vanilla-JS ES modules, no build step, on the
frontend (six new pages). Leaflet 1.9.4 and Chart.js 4.5.1 remain the current stable releases (re-verified
against GitHub Releases at the start of this milestone, per `02-backend-conventions.md`'s dependency-
freshness rule) — Leaflet is newly *used* by this feature (site map), Chart.js is not used until v0.6.

**Architecture approach**: almost entirely additive. The flights/sites/gliders/harnesses/categories/
buddies CRUD surface shipped in v0.2 already covers everything this feature's pages need except two
gaps (see Data Model Summary). The heavy lifting is frontend: six new page+script pairs following the
existing `bootstrapPage()` / `fetchAuth()` / i18n / dark-theme / console-logging conventions in
`03-frontend-conventions.md`.

**Performance**: NFR-001 is met by the client-side approach in `research.md` — ~600 rows fits comfortably
in browser memory and array operations; no pagination/search API surface is being added.

**Security**: no new auth surface. Every new page requires the same `get_current_user` dependency already
used everywhere; the new `/api/import-report` endpoint is read-only and requires auth but is not
owner-scoped (see `contracts/import-report.yaml` for why).

## Constitution Check

| Principle (`00-ai-usage.md`) | Status |
|---|---|
| Read before acting | Done — spec, all `.ai/instructions/`, `database/models.py`, every router this feature touches or reuses, read before this plan was written |
| Plan before building | This document; no code has been written yet |
| Minimal scope | Client-side search/sort/pagination/CSV avoids adding backend surface not yet needed by a second consumer; buddy linking, IGC, stats, sharing explicitly deferred per spec's Out of Scope |
| Tool-agnostic instructions | No `CLAUDE.md` or equivalent introduced |
| Keep docs in sync | Deferred to session end (`sync.md`) once the feature is actually implemented — updating `architecture.md`/`features.md` now, before any code exists, would document work that hasn't happened |
| No secrets committed | N/A — no secrets touched |
| Prod is off-limits | N/A — this plan is local implementation; deployment follows the existing pipeline afterward |

No violations.

## Data Model Summary

No new tables. Two backend gaps close, both detailed in `data-model.md`:

1. **Historical import findings** — a frozen `HistoricalImportSummary` constant (`core/import_history.py`),
   generated once from a real dry-run against `olddata/Flugbuch.xlsx`, served read-only by a new
   `GET /api/import-report` endpoint (`contracts/import-report.yaml`).
2. **`sites.coord_source`** — already a column, never written until now. `POST`/`PUT /api/sites` start
   setting it to `"manual"` server-side whenever `lat`/`lon` is present in the request
   (`contracts/sites-coord-source.md`).

Everything else — `flights`, `sites`, `gliders`, `harnesses`, `flight_categories`, `buddies`, `regions` —
is read and written through the CRUD surface v0.2 already shipped, unchanged.

## File Structure

### Backend (new)
```
src/flightlog/core/import_history.py           # frozen HistoricalImportSummary constant
src/flightlog/models/import_report.py          # Pydantic response schema
src/flightlog/api/routers/import_report.py     # GET /api/import-report
```

### Backend (modified)
```
src/flightlog/api/main.py                      # register import_report router
src/flightlog/api/routers/sites.py             # coord_source="manual" on lat/lon write
src/flightlog/api/routers/pages.py             # 6 new HTML routes (see below)
static/i18n/en.json                             # new keys: nav.contacts, nav.import, and per-page strings
static/index.html                               # home.empty_hint copy + a "go to flights" link when logged in
```

### Backend assets (new, vendored — not application code)
```
static/vendor/leaflet/images/marker-icon.png
static/vendor/leaflet/images/marker-icon-2x.png
static/vendor/leaflet/images/marker-shadow.png
static/vendor/leaflet/images/layers.png
static/vendor/leaflet/images/layers-2x.png
```
Pulled from the Leaflet **v1.9.4** GitHub release (`dist/images/`) — the exact version already vendored,
not a newer one. Covered by the existing `static/vendor/** -text` `.gitattributes` rule.

### Frontend (new pages — one `.html` + companion `.js` each, per `03-frontend-conventions.md`)
```
static/flights.html          static/flights.js          # list, search/filter/sort/paginate, add/edit
                                                          # drawer, CSV export
static/flight-detail.html    static/flight-detail.js    # single-flight detail view
static/sites.html            static/sites.js            # list + Leaflet map + pin drop
static/equipment.html        static/equipment.js        # gliders + harnesses CRUD/retire
static/contacts.html         static/contacts.js         # buddies CRUD
static/import.html           static/import.js           # read-only import-findings view
```

### Frontend (new shared module)
```
static/refdata.js            # fetch-once, cache-in-memory helper for sites/gliders/harnesses/
                              # categories/buddies — used by every page above to resolve display
                              # names client-side (research.md)
```

### New HTML routes in `pages.py`
```
GET /flights                 -> flights.html
GET /flights/{flight_id}     -> flight-detail.html   (id read client-side from the URL, same pattern
                                                        FastAPI page routes already use for path params)
GET /sites                   -> sites.html
GET /equipment                -> equipment.html
GET /contacts                 -> contacts.html
GET /import                   -> import.html
```

### Tests (new)
```
tests/backend/test_import_report.py   # 200 shape, requires auth, matches the frozen constant
```

### Tests (extended)
```
tests/backend/test_sites.py           # coord_source becomes "manual" on create/update with lat/lon;
                                       # stays untouched when neither is present
```

## Implementation Phases

### Phase 1: Backend prerequisites
Generate `core/import_history.py` from a real dry-run (never hand-transcribed), add
`models/import_report.py` and `api/routers/import_report.py`, register in `main.py`. Add the
`coord_source="manual"` behavior to `sites.py`. Vendor the missing Leaflet images. Tests for both backend
changes. This phase is fully testable with `pytest` before any frontend work starts.

### Phase 2: Shared frontend scaffolding
`refdata.js` (cache-once reference-data fetcher/joiner), the 6 new i18n key groups in `en.json`, the 6 new
routes in `pages.py`, nav entries. No page content yet — this phase makes every subsequent page a smaller
diff.

### Phase 3: Flights list + add/edit drawer + CSV export
The largest single piece: search, filters, sortable columns, pagination, the inline add/edit drawer
(create and edit), delete with confirmation, CSV export button. Built and manually verified against a
live boot before moving on, since every later page's list-view patterns (search box, filter row, table)
are established here first.

### Phase 4: Flight detail page
Reachable from the flights list; resolved names via `refdata.js`; "not recorded" states for null optional
fields.

### Phase 5: Sites, Equipment, Contacts
Three structurally similar CRUD-style pages, built together: sites (list + Leaflet map + pin drop),
equipment (gliders/harnesses, create/edit/retire), contacts (buddies, create/edit/delete with flight-count
display).

### Phase 6: Import-findings review page + homepage update
`/import` rendering the frozen `GET /api/import-report` response; `index.html`'s copy/link update.

### Phase 7: Verification pass
Live-boot walkthrough of all six pages plus the flight-detail page: golden path, empty states, validation
errors, keyboard-only navigation (NFR-002), delete confirmations (NFR-003), i18n completeness (every new
string has an `en.json` key, no hardcoded chrome text), console logging present per
`03-frontend-conventions.md`'s mandatory-logging rule. `ruff check` / `ruff format --check` / `pytest`
clean. Then `sync.md` to update `architecture.md`/`features.md`/`RESUME.md` with what actually shipped.

## Dependencies

- Leaflet 1.9.4 (already vendored JS/CSS; this feature adds the missing images) — reverified current via
  `gh api repos/Leaflet/Leaflet/releases/latest` → `v1.9.4`.
- Chart.js 4.5.1 — reverified current via `gh api repos/chartjs/Chart.js/releases/latest` → `v4.5.1`; not
  used by this feature (arrives v0.6), reverified only because the freshness rule applies at the start of
  every milestone, not per-feature.
- OpenStreetMap public tile server (`research.md`) — no new backend dependency, no config key; the
  frontend references it directly, same as any other external image URL already allowed by CSP.
- No new Python packages, no new GitHub Actions, no new npm anything (there is no npm).

## Risk & Mitigations

- **Risk**: the flights list becomes sluggish once the pilot's flight count grows well past ~600.
  **Mitigation**: NFR-001 is scoped to "current count and continuing to scale" deliberately, not a fixed
  ceiling; `research.md` documents server-side search/sort/pagination as the fallback if this is ever
  actually hit, without committing to it now.
- **Risk**: `import.html`'s frozen data drifts from reality as the pilot resolves findings (adds the
  missing harness, creates buddy contacts), reading as if nothing happened.
  **Mitigation**: spec's Edge Cases section explicitly accepts this as a historical snapshot, not a live
  view — the page's copy should say so plainly so it doesn't read as a bug.
- **Risk**: adding six pages with zero automated frontend coverage means regressions on existing pages
  (login, home) could go unnoticed.
  **Mitigation**: Phase 7's live-boot walkthrough explicitly re-checks login/home alongside the new pages,
  not just the new surface; backend coverage (routers, `core/flights.py`) is unaffected and stays under
  `pytest`.
- **Risk**: OpenStreetMap's tile server has fair-use rate limits; heavy map interaction during development
  could get the dev IP rate-limited.
  **Mitigation**: acceptable for a single-pilot personal project's traffic level; `research.md` records
  self-hosting tiles as the fallback if this ever becomes real.
