# Implementation Plan: Statistics

Spec: [`spec.md`](./spec.md) · Research: [`research.md`](./research.md) · Data model:
[`data-model.md`](./data-model.md) · Contracts: [`contracts/`](./contracts/)

## Technical Context

Backend-heavy, read-only, on the existing stack — no new tech stack decisions, no new tables. FastAPI +
SQLAlchemy 2.0 aggregate queries (one new router, no new persisted models beyond response schemas);
vanilla-JS ES modules on the frontend (one new page, several chart sections), reusing Chart.js 4.5.1
(already vendored since `v0.1`, in real use since `v0.5`'s barogram) for every bar/line chart this
feature needs — no new chart type or plugin is required, since bar and line charts are Chart.js's core,
always-available chart kinds (unlike the barogram's per-segment coloring, which needed a specific
callback feature but not a plugin).

**Architecture approach**: almost entirely a read layer over data every prior feature already wrote.
`core/stats.py` holds every aggregate query, parameterized where the same shape repeats (`research.md`'s
shared `year_matrix` helper for the five/six dimension matrices). `api/routers/stats.py` is thin —
each endpoint calls one `core/stats.py` function and returns its result.

**Performance**: NFR-001's "well under a second at ~600 rows" is met by indexed aggregates over a table
this size — no denormalization, no cache, matching the project's explicit "don't cache speculatively"
stance (`architecture.md`).

**Security**: no new auth surface; every endpoint scopes directly by `owner_id` in its query, with no
path-parameter id to leak existence through (`contracts/endpoints.md`).

## Constitution Check

| Principle (`00-ai-usage.md`) | Status |
|---|---|
| Read before acting | Done — spec, every `.ai/instructions/` file, `architecture.md`'s Statistics/Derived-values/Flight-categories sections, the real `Übersicht` sheet (read directly via `openpyxl`, going beyond what prior research had already read from it), `core/aliases.py`, `core/igc.py`/`igc_storage.py` for the IGC rollup, all read before this plan was written |
| Plan before building | This document; no code has been written yet |
| Minimal scope | No new stored/cached statistics table (explicit non-goal, matching `architecture.md`); no historical buddy-tag backfill (explicitly rejected in `research.md` as belonging to a different feature); no shareable/public stats view (`v0.9` dependency, not yet built) |
| Tool-agnostic instructions | No `CLAUDE.md` or equivalent introduced |
| Keep docs in sync | Deferred to session end (`sync.md`) once implemented |
| No secrets committed | N/A |
| Prod is off-limits | N/A — local implementation; deployment follows the existing tag-push pipeline |

No violations.

## Data Model Summary

No new tables (`data-model.md`) — every figure is a read-time aggregate over `flights` and its already-
existing related tables (`flight_categories`, `sites`, `regions`, `gliders`, `harnesses`,
`buddies`/`flight_buddies`) plus `igc_tracks`/`igc_segments` for the one IGC-derived rollup.

## File Structure

### Backend (new)
```
src/flightlog/core/stats.py                  # every aggregate query; the shared year_matrix() helper
src/flightlog/models/stats.py                # Pydantic response schemas (data-model.md's shapes)
src/flightlog/api/routers/stats.py           # 8 GET endpoints, per contracts/endpoints.md
```

### Backend (modified)
```
src/flightlog/api/main.py                    # register the stats router
src/flightlog/api/routers/pages.py           # + GET /stats
static/i18n/en.json                          # nav + /stats page keys
```

### Frontend (new page)
```
static/stats.html            static/stats.js   # totals, time breakdown, distributions, personal
                                                # bests (each linking to its flight), 6 year-matrices,
                                                # launch-technique split, IGC rollup, streak/pace/
                                                # progression chart — all via existing Chart.js
```

### New HTML route in `pages.py`
```
GET /stats  -> stats.html
```

### Tests (new)
```
tests/backend/test_stats.py   # one test file, covering all 8 endpoints against a small hand-built
                               # fixture set (not the real 600-flight workbook — this feature needs
                               # specific, known edge cases: ties, a "not recorded" dimension bucket,
                               # zero-track and zero-buddy states — more than it needs realism at scale)
```

## Implementation Phases

### Phase 1: Core aggregates
`core/stats.py`'s totals, time-breakdown, distribution, and personal-bests functions (the four
`spec.md` P1 stories that don't need the shared matrix helper). Fully unit-testable against a hand-built
fixture set before any HTTP route exists.

### Phase 2: Dimension matrices
The shared `year_matrix()` helper and its five callers (site/region/glider/harness/category), plus the
launch-technique split and Hike&Fly total (structurally the simplest matrix — two buckets, not N).

### Phase 3: IGC rollup and buddy matrix
`cumulative_thermal_climb_m` (a direct sum, no new filtering per `research.md`) and the buddy year
matrix (explicitly sparse, per `research.md` — tested with a fixture that has zero and then some
`flight_buddies` rows to confirm both states render sensibly).

### Phase 4: Streaks, pace, progression
The one genuinely new *kind* of computation in this feature (everything else is a sum/average/count) —
current streak (consecutive weeks/months), YTD pace, cumulative progression series.

### Phase 5: API layer
`api/routers/stats.py`'s 8 endpoints, `models/stats.py`'s schemas, registration in `main.py`.

### Phase 6: Frontend
`stats.html`/`stats.js` — one page, several sections, each independently fetched (per
`contracts/endpoints.md`'s "8 small endpoints" rationale) so the page can render incrementally rather
than blocking on the slowest aggregate. Personal-best figures link to `/flights/{id}`. Charts via the
already-vendored Chart.js.

### Phase 7: Verification pass
Live-boot walkthrough against the real 600-flight data: spot-check totals/averages by hand against a
handful of flights; confirm the year × month matrix, launch-technique split, and Hike&Fly total match
(or, where a workbook bug is confirmed, correctly *don't* match) `Übersicht`'s real numbers; confirm the
IGC rollup shows a real, non-zero cumulative climb once tracks are uploaded; confirm every zero-state
(NFR-003) renders cleanly on a scratch account with no flights. `ruff check`/`ruff format --check`/
`pytest` clean. Then `sync.md`.

## Dependencies

- No new Python packages.
- Chart.js 4.5.1 — already vendored and in real use since `v0.5`; no version change, no new plugin.
- No new npm/build-step anything.

## Risk & Mitigations

- **Risk**: the shared `year_matrix()` helper's parameterized `GROUP BY` becomes awkward once a sixth
  dimension (`buddy`, via a join table rather than a direct FK) is added on top of the original five
  direct-FK dimensions.
  **Mitigation**: `research.md` already anticipates this — the buddy matrix is documented as reusing
  the *shape* (`DimensionYearMatrixOut`), not necessarily the exact same SQL construction, since it
  requires an extra join `flight_buddies` the other five don't.
- **Risk**: a personal-best or matrix computation silently breaks on a flight missing an optional field
  (no glider, no landing site) rather than bucketing it as "not recorded."
  **Mitigation**: explicitly called out in `spec.md`'s Edge Cases and `data-model.md`'s
  `DimensionYearMatrixOut` shape (`id: null` bucket) — a Phase 2 test case, not an afterthought.
- **Risk**: the pilot expects the per-buddy matrix or IGC rollup to already show full historical depth,
  since everything else on `/stats` does.
  **Mitigation**: `spec.md`'s NFR-003 and Assumptions sections state plainly that both are legitimately
  partial; the frontend's empty/sparse-state copy (Phase 6) should say so directly rather than let a
  half-empty matrix read as broken.
