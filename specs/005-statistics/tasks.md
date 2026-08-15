# Tasks: Statistics

Spec: [`spec.md`](./spec.md) · Plan: [`plan.md`](./plan.md) · Data model: [`data-model.md`](./data-model.md)
· Contracts: [`contracts/endpoints.md`](./contracts/endpoints.md) · Research: [`research.md`](./research.md)

## Summary

- Total tasks: 22
- Parallel opportunities: 6 (marked `[P]`)
- MVP scope: Phase 3 (US1 — totals, time breakdown, distributions, personal bests) is the smallest
  independently-shippable slice, matching `spec.md`'s P1 priority.

Test tasks included throughout, matching every prior feature's precedent. No frontend test tasks,
consistent with every prior UI feature's own precedent.

## Dependencies

```
Phase 1 (Setup) ─> Phase 2 (Foundation: models/stats.py schemas) ─┬─> Phase 3  US1 totals/breakdown/distribution/personal-bests
                                                                    │        │
                                                                    │        v
                                                                    ├─> Phase 4  US2 dimension matrices + launch-technique
                                                                    │        (independent of Phase 3's files, can run parallel)
                                                                    │
                                                                    └─> Phase 5  US3 IGC rollup + buddy matrix + streaks/pace/progression
                                                                             (independent of Phase 3/4)

Phase 6  Frontend — depends on Phases 3-5's endpoints all existing
Final Phase — Polish
```

---

## Phase 1 — Setup

- [x] T001 [P] Re-confirm Chart.js is still `v4.5.1` (`gh api repos/chartjs/Chart.js/releases/latest`)
      if implementation starts a meaningful time after this plan

## Phase 2 — Foundation

- [x] T002 Create `src/flightlog/models/stats.py` — every Pydantic response schema from `data-model.md`
      (`TotalsOut`, `TimeBreakdownOut`, `DistributionOut`, `PersonalBestOut`, `DimensionYearMatrixOut`,
      `LaunchTechniqueOut`, `IgcRollupOut`, `BuddyYearMatrixOut`, `ProgressionOut`)
- [x] T003 [P] Build a small hand-crafted fixture set in `tests/backend/test_stats.py`'s own fixtures
      (not the real workbook) covering: a tie for a personal best, a flight missing glider/landing site,
      zero uploaded tracks, zero tagged buddies, then some tagged buddies — these specific edge cases
      matter more here than realistic scale

## Phase 3 — Totals, time breakdown, distributions, personal bests [US1]

**Goal**: a pilot sees career totals/averages, a year×month breakdown, duration/distance/altitude
distributions, and linked personal bests.
**Independent test criteria**: against the fixture set, every total/average matches a hand-computed
expectation; the year×month matrix matches; a tied personal best resolves deterministically to the
earliest flight; every duration bucket boundary matches the workbook's own 30/60/120/180 min scheme.

- [x] T004 [US1] Implement `totals()`, `time_breakdown()`, `distribution()`, `personal_bests()` in
      `src/flightlog/core/stats.py` — `alt_gain_m` totals from the computed value, never the legacy
      stored figure (`research.md`); tie-break to earliest flight by date then id
- [x] T005 [US1] [P] `tests/backend/test_stats.py` — totals/breakdown/distribution/personal-bests
      against the T003 fixtures, including the tie case
- [x] T006 [US1] Add `GET /api/stats/totals`, `/time-breakdown`, `/distribution`, `/personal-bests` to
      `src/flightlog/api/routers/stats.py`; register the router in `src/flightlog/api/main.py`

## Phase 4 — Dimension matrices and launch technique [US1, continued]

**Goal**: per-year matrices for site/region/glider/harness/category, plus launch-technique split and
Hike&Fly totals.
**Independent test criteria**: a flight missing an optional dimension field appears in a `null`-id "not
recorded" bucket, not silently dropped; the reverse-launch percentage is computed correctly over the
full flight count, confirmed to disagree with the workbook's own (already-known-buggy) figure rather
than matching it.

- [x] T007 [US1] Implement the shared `year_matrix()` helper in `core/stats.py` and its five callers
      (site/region/glider/harness/category), per `research.md`'s shared-query decision
- [x] T008 [US1] Implement `launch_technique_split()` in `core/stats.py`
- [x] T009 [US1] [P] `tests/backend/test_stats.py` — matrix "not recorded" bucket case, launch-technique
      split and percentage
- [x] T010 [US1] Add `GET /api/stats/matrix/{dimension}` and `/launch-technique` to `stats.py`

## Phase 5 — IGC rollup, buddy matrix, streaks/pace/progression [US2, US3]

**Goal**: cumulative thermal climb, a (legitimately sparse) per-buddy matrix, current streak, YTD pace,
cumulative progression series.
**Independent test criteria**: zero uploaded tracks shows a clear empty state, not a bare zero; the
buddy matrix reflects only existing `flight_buddies` rows; a streak/pace computation against a small
known fixture calendar matches hand-computed expectations.

- [x] T011 [US2] Implement `igc_rollup()` in `core/stats.py` — `SUM(igc_segments.alt_change_m) WHERE
      kind = 'thermal'`, joined across the owner's tracks
- [x] T012 [US3] Implement the buddy year matrix (reusing `year_matrix()`'s shape, extra join per
      `plan.md`'s risk note) in `core/stats.py`
- [x] T013 [US3] Implement `current_streak()`, `ytd_pace()`, `cumulative_progression()` in `core/stats.py`
- [x] T014 [US2] [US3] [P] `tests/backend/test_stats.py` — zero-track empty state, sparse-then-populated
      buddy matrix, streak/pace against a small known fixture calendar
- [x] T015 [US2] [US3] Add `GET /api/stats/igc-rollup`, `/matrix/buddy` (or fold into T010's
      `{dimension}` route if `buddy` fits the same shape cleanly), `/progression` to `stats.py`

## Phase 6 — Frontend

- [x] T016 Create `static/stats.html`/`static/stats.js` — totals section, time-breakdown chart, personal
      bests (each a link to `/flights/{id}`), the five/six dimension matrices, launch-technique split,
      IGC rollup, streak/pace/progression chart — each section independently fetched so the page renders
      incrementally (per `contracts/endpoints.md`'s 8-small-endpoints rationale)
- [x] T017 Add `GET /stats` route to `src/flightlog/api/routers/pages.py`; nav entry (`nav.stats`,
      already referenced in `bootstrap.js`'s `NAV_LINKS` since `v0.3` but never linked to a real page) in
      `static/bootstrap.js`
- [x] T018 [P] Add `stats.*` i18n keys, including explicit empty-state copy for the IGC rollup and buddy
      matrix (per `plan.md`'s risk note — must read as "not built up yet," not "broken")

## Final Phase — Polish

- [x] T019 Live-boot verification against the real 600-flight data: spot-check totals/averages by hand;
      confirm the year×month matrix, launch-technique split, and Hike&Fly total against `Übersicht`'s
      real numbers — matching where the workbook is right, confirmed-different where it's a known bug
- [x] T020 Confirm every NFR-003 zero-state renders cleanly on a scratch account with no flights
- [x] T021 `ruff check`/`ruff format --check`/full `pytest` clean; bump `pyproject.toml`'s version
- [x] T022 `sync.md` — update `architecture.md` (API Contracts table, note the third confirmed workbook
      disagreement discovered in `research.md`), `features.md` (mark v0.7 shipped), `RESUME.md`
