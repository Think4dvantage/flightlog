# Implementation Plan: Secondary Sheets & XContest Import

Spec: [`spec.md`](./spec.md) · Research: [`research.md`](./research.md) · Data model:
[`data-model.md`](./data-model.md) · Contracts: [`contracts/`](./contracts/)

## Technical Context

Backend-first, on the existing stack — no new tech stack decisions. FastAPI + Pydantic v2 + SQLAlchemy
2.0 (four new tables, three new columns on `flights`, five new routers); vanilla-JS ES modules on the
frontend (four new list/CRUD pages, one XContest-import page), following the exact same
`bootstrapPage()`/`fetchAuth()`/i18n/dark-theme/console-logging conventions every prior feature already
established.

**Architecture approach**: the three read-only import types (hikes, ground-handling, tandem flights)
and the one editable type (goals) both reuse `core/importer.py`'s existing idempotency pattern
(`import_key`, `UniqueConstraint(owner_id, import_key)`) rather than inventing a new one. The
hike-to-flight linking and XContest bulk-match both reuse the ambiguity-reporting pattern
`specs/003-igc-ingest-analysis` already established (`igc_pending_uploads`) rather than a bespoke
mechanism — the XContest import even reuses that feature's exact response shape
(`BulkUploadOutcomeOut`). This feature is mostly application of decisions already made twice before, not
new design.

**Performance**: trivial — the secondary-sheet import handles single-digit-to-low-hundred row counts
(85/9/17/11 in the real workbook); no pagination or server-side filtering is needed for any of the four
new list views at this scale, matching NFR-001.

**Security**: no new auth surface — every new route reuses `get_current_user` and the standard
`_get_own_<x>()` 404-not-403 pattern. `flights.xc_official_url` gets the same URL-scheme validation
already required of `media_links.url`/`tracker_links.url` (`04-constraints.md`).

## Constitution Check

| Principle (`00-ai-usage.md`) | Status |
|---|---|
| Read before acting | Done — spec, every `.ai/instructions/` file, `architecture.md`, `core/importer.py`, `core/aliases.py`, and the real workbook's four secondary sheets (read directly via `openpyxl`, not assumed from `specs/001-core-data-import/research.md`'s "out of scope, not read" note), all read before this plan was written |
| Plan before building | This document; no code has been written yet |
| Minimal scope | No CRUD for hikes/ground-handling/tandem-flights beyond import-and-view (spec's Out of Scope); no weather-goal matching (that's v0.10); no XC-score recomputation (project-wide decision already shelved in `features.md`) |
| Tool-agnostic instructions | No `CLAUDE.md` or equivalent introduced |
| Keep docs in sync | Deferred to session end (`sync.md`) once implemented |
| No secrets committed | N/A |
| Prod is off-limits | N/A — local implementation; deployment follows the existing tag-push pipeline |

No violations.

## Data Model Summary

Four new tables (`hikes`, `groundhandling_sessions`, `tandem_flights`, `goals`) and three new columns on
the existing `flights` table (`xc_official_score`/`_type`/`_url`, already named in prior specs, first
populated here). Full detail in `data-model.md`. No column needs a migration guard except the three on
`flights` (an existing table); the four new tables need none (`Base.metadata.create_all()` handles
them).

## File Structure

### Backend (new)
```
src/flightlog/core/secondary_import.py       # parses Fitnessprogramm/Groundhandling/Tandemflüge/Ziele,
                                              # hike-to-flight linking, import_key idempotency
src/flightlog/core/xcontest_import.py        # parses an XContest "My Flights" export, date-based
                                              # match against untracked flights, ambiguity handling
src/flightlog/models/secondary.py            # Pydantic schemas: HikeOut, GroundhandlingSessionOut,
                                              # TandemFlightOut, GoalOut/Create/Update
src/flightlog/models/xcontest.py             # Pydantic schemas: XContestOutcomeOut, XContestPendingOut
src/flightlog/api/routers/hikes.py
src/flightlog/api/routers/groundhandling.py
src/flightlog/api/routers/tandem_flights.py
src/flightlog/api/routers/goals.py
src/flightlog/api/routers/xcontest_import.py
```

### Backend (modified)
```
src/flightlog/database/models.py             # + Hike, GroundhandlingSession, TandemFlight, Goal;
                                              # + flights.xc_official_score/_type/_url
src/flightlog/database/db.py                 # _run_column_migrations() guard for the 3 new flights columns
src/flightlog/api/main.py                    # register 5 new routers
src/flightlog/api/routers/pages.py           # + GET /hikes, /groundhandling, /tandem-flights, /goals,
                                              # /xcontest-import
static/i18n/en.json                          # nav + per-page keys
```

### Frontend (new pages)
```
static/hikes.html            static/hikes.js            # list, linked-flight indicator
static/groundhandling.html   static/groundhandling.js    # list
static/tandem-flights.html   static/tandem-flights.js    # list
static/goals.html            static/goals.js             # list + status filter + add/edit drawer +
                                                          # mark-done + delete (full CRUD, per FR-006)
static/xcontest-import.html  static/xcontest-import.js   # upload + outcome list + pending/resolve,
                                                          # mirrors static/igc.js's structure closely
```

### New HTML routes in `pages.py`
```
GET /hikes            -> hikes.html
GET /groundhandling   -> groundhandling.html
GET /tandem-flights   -> tandem-flights.html
GET /goals            -> goals.html
GET /xcontest-import  -> xcontest-import.html
```

### Tests (new)
```
tests/backend/test_secondary_import.py    # idempotent import of all 3 read-only types; hike-to-flight
                                           # linking: unambiguous link, same-day-collision -> unlinked
tests/backend/test_goals.py               # full CRUD, status filter, mark-done
tests/backend/test_xcontest_import.py     # unambiguous attach, ambiguous -> pending, resolve, dismiss,
                                           # idempotent re-import
tests/backend/fixtures/xcontest_sample.json  # a real (or research-verified-shape) sample export
```

## Implementation Phases

### Phase 1: Backend prerequisites — verify the XContest schema, then build the data layer
**Before writing `core/xcontest_import.py`'s parser**, obtain and read one real "My Flights" export
sample (`research.md`'s open item) — this determines the exact field names `models/xcontest.py` and the
parser work against; guessing here risks a silent no-op import (every entry "unmatched" because the
parser looked for the wrong key). Once resolved: the four new tables in `database/models.py`, the
`flights` column migration, and `core/secondary_import.py` (parses the three read-only sheets +
`Ziele`, applies `import_key` idempotency, hike-to-flight linking). Fully unit-testable against a copy
of the real workbook before any HTTP route exists — the same verification level
`specs/001-core-data-import` and `specs/003-igc-ingest-analysis` both held themselves to (real fixture
data, not synthetic).

### Phase 2: Read-only import types — hikes, ground-handling, tandem flights
`api/routers/hikes.py`, `groundhandling.py`, `tandem_flights.py` (GET-only, per contracts); their
Pydantic schemas; backend tests. A CLI or admin-triggered import entry point (mirroring
`core/importer.py`'s `python -m` pattern, or folded into the existing importer's own entry point —
implementation-time call) runs `core/secondary_import.py`.

### Phase 3: Goals — full CRUD
`api/routers/goals.py`, `models/secondary.py`'s Goal schemas, status-filtered list, mark-done action.
Backend-testable independently of Phase 2.

### Phase 4: XContest import
`core/xcontest_import.py`'s parser (now that Phase 1 resolved the schema), the bulk-match-and-pending
flow reusing `igc_pending_uploads`'s exact pattern, `api/routers/xcontest_import.py`.

### Phase 5: Frontend — four list pages + goals CRUD + XContest import page
`hikes.html`/`.js`, `groundhandling.html`/`.js`, `tandem-flights.html`/`.js` (simple list views,
smallest frontend surface of any feature so far); `goals.html`/`.js` (list + drawer, following
`equipment.js`'s add/edit/retire drawer pattern exactly, substituting "mark done" for "retire");
`xcontest-import.html`/`.js` (closely mirrors `static/igc.js`'s bulk-upload + pending-review structure).
Nav entries, i18n keys throughout.

### Phase 6: Verification pass
Live-boot walkthrough: run the secondary-sheet import against the real workbook and hand-verify a
sample of each type against the source rows directly (same rigor as `specs/001-core-data-import`'s
600-flight verification and `specs/003-igc-ingest-analysis`'s fixture cross-check); import a real
XContest export and verify at least one attached score by comparing it to the pilot's own XContest
account; confirm a hike with `Airtime`/`Landeplatz` links to its flight and a pure hike doesn't; confirm
goals CRUD end-to-end including mark-done and delete-confirmation (NFR-003). `ruff check`/`ruff format
--check`/`pytest` clean. Then `sync.md` to update `architecture.md`/`features.md`/`RESUME.md`.

## Dependencies

- No new Python packages — JSON parsing is stdlib; nothing else this feature needs isn't already in the
  dependency set.
- No new vendored JS — the four new pages follow existing patterns with existing shared modules
  (`bootstrap.js`, `auth.js`, `i18n.js`, `refdata.js`).
- Requires one real XContest "My Flights" export sample as a planning-to-implementation handoff input
  (`research.md`) — without it, Phase 1 cannot finalize the parser or the Pydantic schemas with
  confidence.

## Risk & Mitigations

- **Risk**: the XContest export schema, once actually seen, turns out to need fields beyond the three
  `architecture.md` already committed to (`xc_official_score`/`_type`/`_url`) — e.g. per-rule-set scores
  that don't collapse cleanly into one `_score`/`_type` pair.
  **Mitigation**: `research.md` flags this explicitly rather than assuming the three-column shape is
  definitely sufficient; if the real schema needs more, that's a small, contained addition to the
  `flights` migration in Phase 1, not a redesign of anything else in this plan.
- **Risk**: the real workbook's same-day `Hike&Fly` collisions turn out to be more common than the
  85-row sample's spot-check suggested, making the hike-to-flight linking mostly useless in practice.
  **Mitigation**: acceptable even in the worst case — an unlinked hike is still a fully valid, complete
  record (spec's Assumptions); the link is a nice-to-have cross-reference, not something anything else
  depends on.
- **Risk**: `Ziele`'s ~505-columns-wide reported shape (497 of them empty formatting artifacts,
  `research.md`) trips up a naive "iterate every column" parser and produces hundreds of spurious `None`
  fields per goal.
  **Mitigation**: already documented as a specific implementation instruction in `research.md` — read
  only the first 8 columns by name/position, don't iterate the sheet's full reported width.
