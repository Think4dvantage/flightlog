# Tasks: Secondary Sheets & XContest Import

Spec: [`spec.md`](./spec.md) · Plan: [`plan.md`](./plan.md) · Data model: [`data-model.md`](./data-model.md)
· Contracts: [`contracts/endpoints.md`](./contracts/endpoints.md) · Research: [`research.md`](./research.md)

## Summary

- Total tasks: 30
- Parallel opportunities: 9 (marked `[P]`)
- MVP scope: Phase 3 (US1 — the three read-only imports + their list views) is the smallest
  independently-shippable slice; it alone retires most of the spreadsheet's remaining unique data.

**Phase 5 (XContest import, T018–T024) has moved to `features.md`'s Backlog** (2026-08-15) — no real "My
Flights" export sample was available at implementation kickoff, and v0.6 otherwise ships complete without
it. This milestone is done; v0.7 (statistics) is next. Phase 5 stays here as the design record to resume
from once a sample export exists (`spec.md`'s Clarifications).

Test tasks included throughout, matching every prior feature's precedent.

## Dependencies

```
Phase 1 (Setup: obtain XContest sample) ─> Phase 2 (Foundation: 4 tables, flights columns, migration) ─┬─> Phase 3  US1 read-only imports + list views
                                                                                                         │        │
                                                                                                         │        v
                                                                                                         ├─> Phase 4  US2 goals CRUD (independent of Phase 3's files)
                                                                                                         │
                                                                                                         └─> Phase 5  US3 XContest import (needs Phase 1's resolved schema)

Final Phase — Polish: after everything above.
```

Phase 4 and Phase 5 each depend only on Phase 2 and can proceed in either order relative to each other
and to Phase 3.

---

## Phase 1 — Setup

- [~] T001 **Moved to backlog** — obtain one real XContest "My Flights" export sample from the pilot's
      own account and record its actual JSON structure in `research.md`. Not done at kickoff; Phase 5
      (T018–T024) moved to `features.md`'s Backlog (2026-08-15) rather than staying an open phase of this
      milestone — see that entry to resume
- [x] T002 [P] Confirm the real workbook's four secondary sheets still match `research.md`'s recorded
      structure — re-read via `openpyxl`, unchanged since planning

## Phase 2 — Foundation

- [x] T003 [P] Add `Hike`, `GroundhandlingSession`, `TandemFlight`, `Goal` ORM models to
      `src/flightlog/database/models.py` per `data-model.md`
- [~] T004 **Deferred alongside Phase 5** — `flights.xc_official_score`/`_type`/`_url` columns have no
      consumer until the XContest import exists; adding them now would be dead schema ahead of the
      feature that populates them, which the minimal-scope principle argues against. Add together with
      Phase 5 once T001 unblocks it
- [x] T005 [P] Create `src/flightlog/models/secondary.py` — Pydantic schemas for all four new types
      (`HikeOut`, `GroundhandlingSessionOut`, `TandemFlightOut`, `GoalOut`/`GoalCreate`/`GoalUpdate`)

## Phase 3 — Import and view hikes, ground-handling sessions, and tandem flights [US1]

**Goal**: a pilot can see their historical hikes, ground-handling practice, and tandem flights in the
app, each in its own list, without opening the spreadsheet.
**Independent test criteria**: run the import against the real workbook; every non-empty row of the
three sheets appears exactly once in its corresponding list; a hike with `Airtime`/`Landeplatz` in the
source shows a linked flight when the match is unambiguous; re-running the import changes nothing.

- [x] T006 [US1] Create `src/flightlog/core/secondary_import.py` — parses `Fitnessprogramm`,
      `Groundhandling`, `Tandemflüge`; `import_key` idempotency per `research.md`; hike-to-flight
      linking (unambiguous same-date match against `is_hike_fly` flights only, else unlinked and
      reported)
- [x] T007 [US1] [P] `tests/backend/test_secondary_import.py` — idempotent import of all three types
      against the real workbook (85/9/17, matching the exact counts confirmed at planning time), 35
      hikes correctly linked with per-hike date/flight verification, second-run idempotency. 6/6 passing
- [x] T008 [US1] Create `src/flightlog/api/routers/hikes.py`, `groundhandling.py`, `tandem_flights.py`
      (`GET` list + `GET /{id}` each, per `contracts/endpoints.md`); register all three in
      `src/flightlog/api/main.py`
- [x] T009 [US1] Create `static/hikes.html`/`.js`, `static/groundhandling.html`/`.js`,
      `static/tandem-flights.html`/`.js` — three list views; a hike's row shows its linked flight, if any
- [x] T010 [US1] Add `GET /hikes`, `/groundhandling`, `/tandem-flights` routes to
      `src/flightlog/api/routers/pages.py`; nav entries in `static/bootstrap.js`
- [x] T011 [US1] [P] Add i18n keys for all three list pages to `static/i18n/en.json`

## Phase 4 — Goals, fully editable [US2]

**Goal**: a pilot can see their imported flying-goals wishlist and keep adding to/editing/completing it
going forward.
**Independent test criteria**: every `Ziele` row imports; create/edit/delete/mark-done all work; the
status filter correctly separates open from done.

- [x] T012 [US2] Extend `core/secondary_import.py` (folded in directly, not a sibling module) to import
      `Ziele` — read only the first 8 columns by position, per `research.md`'s "497 empty formatting-
      artifact columns" finding
- [x] T013 [US2] Create `src/flightlog/api/routers/goals.py` — full CRUD + `POST /{id}/mark-done`, per
      `contracts/endpoints.md`
- [x] T014 [US2] [P] `tests/backend/test_goals.py` — import (exactly 11 goals, matching the real count),
      CRUD, status filter, mark-done, cross-owner 404. 7/7 passing
- [x] T015 [US2] Create `static/goals.html`/`.js` — list + status filter + add/edit drawer (following
      `equipment.js`'s drawer pattern) + mark-done + delete-with-confirmation (NFR-003)
- [x] T016 [US2] Add `GET /goals` route to `pages.py`; nav entry in `bootstrap.js`
- [x] T017 [US2] [P] Add `goals.*` i18n keys to `en.json`

## Phase 5 — XContest import [US3] (moved to `features.md`'s Backlog, 2026-08-15)

**Goal**: a pilot can import their XContest "My Flights" export and see an independently-verified score
on matched flights.
**Independent test criteria**: an unambiguous entry attaches its score/type/url to the right flight; an
ambiguous or unmatched entry is reported, never guessed; re-importing the same export changes nothing.

- [ ] T018 [US3] Create `src/flightlog/core/xcontest_import.py` — parser built against T001's real
      sample schema; date-based match against flights with no existing `xc_official_score` yet;
      unambiguous → attach, else → pending (reusing `igc_pending_uploads`'s exact pattern per
      `research.md`)
- [ ] T019 [US3] Create `src/flightlog/models/xcontest.py` — `XContestOutcomeOut`, `XContestPendingOut`
      schemas
- [ ] T020 [US3] Create `src/flightlog/api/routers/xcontest_import.py` — `POST /api/xcontest-import`,
      `GET .../pending`, `POST .../pending/{id}/resolve`, `DELETE .../pending/{id}`; register in `main.py`
- [ ] T021 [US3] [P] `tests/backend/test_xcontest_import.py` — using `tests/backend/fixtures/
      xcontest_sample.json` (built from T001's real sample); unambiguous attach, ambiguous → pending,
      resolve, dismiss, idempotent re-import
- [ ] T022 [US3] Create `static/xcontest-import.html`/`.js` — mirrors `static/igc.js`'s bulk-upload +
      pending-review structure
- [ ] T023 [US3] Add `GET /xcontest-import` route to `pages.py`; nav entry in `bootstrap.js`
- [ ] T024 [US3] [P] Add `xcontest.*` i18n keys to `en.json`

## Final Phase — Polish

- [x] T025 Live-boot verification: ran the secondary-sheet import against the real workbook via the CLI
      entry point against the actual dev database (603 real flights), confirmed exact real row counts
      (85/9/17/11), spot-checked linked hikes against their flights directly. **XContest score import
      moved to `features.md`'s Backlog** — no real export sample yet (see Phase 5)
- [x] T026 Confirmed via spot-check and a live browser click-through: a hike with source
      `Airtime`/`Landeplatz` links to its flight (clicked "View flight" on a real linked hike, landed on
      the correct Hike&Fly flight with matching date/launch site) and a pure hike shows no link
- [x] T027 Confirmed goals CRUD end-to-end in a real, connected browser (Claude in Chrome, connected for
      the first time this session) — not just `curl`: create, edit-drawer pre-fill, mark-done, and
      delete all exercised through actual clicks, with mark-done/delete additionally confirmed
      server-side after a screenshot-capture glitch (unrelated to the app — see below) interrupted the
      visual confirmation of those last two steps
- [x] T028 `ruff check`/`ruff format --check`/full `pytest` clean (157/157); `pyproject.toml` bumped
      `0.5.0` → `0.6.0`
- [x] T029 **Real browser connected and used for the first time all session** (Claude in Chrome — every
      prior feature's T047/T033-equivalent task had been left for "next time"). Hikes, Groundhandling,
      Tandem flights, and Goals list pages all confirmed rendering correctly with real data; the Goals
      add/edit drawer confirmed interactively (create, pre-filled edit, mark-done, delete). One
      screenshot-capture timeout occurred partway through (CDP `Page.captureScreenshot` hung on the tab)
      — confirmed via direct API calls that the underlying mark-done and delete actions had both
      already succeeded server-side before the timeout, so this was a transient extension/tab glitch,
      not an application bug; the tab was closed cleanly rather than force-retried
- [x] T030 `sync.md` — updated `architecture.md` (SQLite Tables list, API Contracts table),
      `features.md` (marked v0.6 partially shipped — Phases 1-4; Phase 5 still open), and `RESUME.md`
