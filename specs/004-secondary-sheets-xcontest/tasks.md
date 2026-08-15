# Tasks: Secondary Sheets & XContest Import

Spec: [`spec.md`](./spec.md) · Plan: [`plan.md`](./plan.md) · Data model: [`data-model.md`](./data-model.md)
· Contracts: [`contracts/endpoints.md`](./contracts/endpoints.md) · Research: [`research.md`](./research.md)

## Summary

- Total tasks: 30
- Parallel opportunities: 9 (marked `[P]`)
- MVP scope: Phase 3 (US1 — the three read-only imports + their list views) is the smallest
  independently-shippable slice; it alone retires most of the spreadsheet's remaining unique data.

**Phase 5 (XContest import, T018–T024) is deferred** — no real "My Flights" export sample was available
at implementation kickoff (2026-08-15). Phases 1–4 and the Final Phase's non-XContest items ship in this
pass; Phase 5 resumes once a sample export exists (`spec.md`'s implementation-kickoff Clarifications).

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

- [~] T001 **Deferred** — obtain one real XContest "My Flights" export sample from the pilot's own
      account and record its actual JSON structure in `research.md`. Not done at kickoff; Phase 5
      (T018–T024) is deferred until this happens, per this pass's implementation-kickoff decision
- [x] T002 [P] Confirm the real workbook's four secondary sheets still match `research.md`'s recorded
      structure — re-read via `openpyxl`, unchanged since planning

## Phase 2 — Foundation

- [ ] T003 [P] Add `Hike`, `GroundhandlingSession`, `TandemFlight`, `Goal` ORM models to
      `src/flightlog/database/models.py` per `data-model.md`
- [~] T004 **Deferred alongside Phase 5** — `flights.xc_official_score`/`_type`/`_url` columns have no
      consumer until the XContest import exists; adding them now would be dead schema ahead of the
      feature that populates them, which the minimal-scope principle argues against. Add together with
      Phase 5 once T001 unblocks it
- [ ] T005 [P] Create `src/flightlog/models/secondary.py` — Pydantic schemas for all four new types
      (`HikeOut`, `GroundhandlingSessionOut`, `TandemFlightOut`, `GoalOut`/`GoalCreate`/`GoalUpdate`)

## Phase 3 — Import and view hikes, ground-handling sessions, and tandem flights [US1]

**Goal**: a pilot can see their historical hikes, ground-handling practice, and tandem flights in the
app, each in its own list, without opening the spreadsheet.
**Independent test criteria**: run the import against the real workbook; every non-empty row of the
three sheets appears exactly once in its corresponding list; a hike with `Airtime`/`Landeplatz` in the
source shows a linked flight when the match is unambiguous; re-running the import changes nothing.

- [ ] T006 [US1] Create `src/flightlog/core/secondary_import.py` — parses `Fitnessprogramm`,
      `Groundhandling`, `Tandemflüge`; `import_key` idempotency per `research.md`; hike-to-flight
      linking (unambiguous same-date match against `is_hike_fly` flights only, else unlinked and
      reported)
- [ ] T007 [US1] [P] `tests/backend/test_secondary_import.py` — idempotent import of all three types
      against a copy of the real workbook; linked vs. unlinked hike cases; a manufactured same-day
      collision case proves the ambiguity rule reports rather than guesses
- [ ] T008 [US1] Create `src/flightlog/api/routers/hikes.py`, `groundhandling.py`, `tandem_flights.py`
      (`GET` list + `GET /{id}` each, per `contracts/endpoints.md`); register all three in
      `src/flightlog/api/main.py`
- [ ] T009 [US1] Create `static/hikes.html`/`.js`, `static/groundhandling.html`/`.js`,
      `static/tandem-flights.html`/`.js` — three list views; a hike's row shows its linked flight, if any
- [ ] T010 [US1] Add `GET /hikes`, `/groundhandling`, `/tandem-flights` routes to
      `src/flightlog/api/routers/pages.py`; nav entries in `static/bootstrap.js`
- [ ] T011 [US1] [P] Add i18n keys for all three list pages to `static/i18n/en.json`

## Phase 4 — Goals, fully editable [US2]

**Goal**: a pilot can see their imported flying-goals wishlist and keep adding to/editing/completing it
going forward.
**Independent test criteria**: every `Ziele` row imports; create/edit/delete/mark-done all work; the
status filter correctly separates open from done.

- [ ] T012 [US2] Extend `core/secondary_import.py` (or a sibling function) to import `Ziele` — read only
      the first 8 columns by name/position, per `research.md`'s "497 empty formatting-artifact columns"
      finding
- [ ] T013 [US2] Create `src/flightlog/api/routers/goals.py` — full CRUD + `POST /{id}/mark-done`, per
      `contracts/endpoints.md`
- [ ] T014 [US2] [P] `tests/backend/test_goals.py` — import, CRUD, status filter, mark-done,
      cross-owner 404
- [ ] T015 [US2] Create `static/goals.html`/`.js` — list + status filter + add/edit drawer (following
      `equipment.js`'s drawer pattern) + mark-done + delete-with-confirmation (NFR-003)
- [ ] T016 [US2] Add `GET /goals` route to `pages.py`; nav entry in `bootstrap.js`
- [ ] T017 [US2] [P] Add `goals.*` i18n keys to `en.json`

## Phase 5 — XContest import [US3]

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

- [ ] T025 Live-boot verification: run the secondary-sheet import against the real workbook, hand-verify
      a sample of each type against the source rows directly; import a real XContest export and verify
      at least one attached score against the pilot's own XContest account
- [ ] T026 Confirm a hike with source `Airtime`/`Landeplatz` links to its flight and a pure hike doesn't
- [ ] T027 Confirm goals CRUD end-to-end including mark-done and delete-confirmation (NFR-003)
- [ ] T028 `ruff check`/`ruff format --check`/full `pytest` clean; bump `pyproject.toml`'s version
      (static assets and backend both changed — the version is the cache key)
- [ ] T029 Get a real browser connected and actually render every new page at least once — three
      features in a row (`specs/002-flight-log-ui`, `v0.4.0`'s icon fix, `specs/003-igc-ingest-analysis`)
      shipped without this until a late live confirmation; don't make this the fourth
- [ ] T030 `sync.md` — update `architecture.md` (SQLite Tables list, API Contracts table, mark
      `Flugbuch.xlsx`'s retirement per this milestone's `features.md` entry), `features.md` (mark v0.6
      shipped), and `RESUME.md` with what actually shipped
