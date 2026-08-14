# Tasks: Flight Log UI

Spec: [`spec.md`](./spec.md) · Plan: [`plan.md`](./plan.md) · Data model: [`data-model.md`](./data-model.md)

## Summary

- Total tasks: 49
- Parallel opportunities: 5 (marked `[P]`)
- MVP scope: Phase 3 (US1 — browse the flights list) is the smallest independently-shippable slice;
  Phases 3–8 together (US1–US6, all P1) are the spec's stated MVP boundary — "the Excel is never opened
  again."

Test tasks are included for the two backend changes (per `06-testing-conventions.md`: "backend logic must
be test-gated"). No frontend test tasks — `research.md` documents the deliberate decision not to
introduce Playwright for this feature.

**MVP status (2026-08-14): T001–T036 done — Phases 1–8 complete, all 127 backend tests passing,
`ruff check`/`ruff format --check` clean.** Verified live against a local dev boot with the real
600-flight workbook re-imported (dry-run + `--write`): every page route, every new/changed API
endpoint, and the full flight create/edit/delete lifecycle were exercised via `curl` against the
running server. **Not yet verified visually in an actual browser** — no browser automation tool was
connected this session, so rendering, click/drag interactions (the map pin-drop, the drawer), and
keyboard navigation (NFR-002) are unconfirmed. T047 (manual live-boot verification pass) is still
open specifically for that reason. T037–T049 (contacts, CSV export, remember-filters, and polish)
remain — see `RESUME.md` for next steps.

## Dependencies

```
Phase 1 (Setup) ─┬─> Phase 2 (Foundation: refdata.js) ─┬─> Phase 3  US1 flights list
                 │                                      │        │
                 │                                      │        v
                 │                                      │   Phase 4  US2 add/edit drawer  (extends US1's files)
                 │                                      │        │
                 │                                      │        v
                 │                                      │   Phase 5  US3 flight detail    (links back to US1's rows)
                 │                                      │
                 │                                      ├─> Phase 6  US4 sites + map pin-drop
                 │                                      ├─> Phase 7  US5 equipment          (US2's dropdowns read US5's retired flag)
                 │                                      ├─> Phase 8  US6 import-findings review
                 │                                      ├─> Phase 9  US7 contacts (P2)
                 │                                      └─> Phase 10 US8 CSV export (P2, needs US1's cached list)
                 │
                 └─────────────────────────────────────────> Phase 11 US9 remember filters (P3, needs US1's filter state)

Final Phase — Polish: after everything above.
```

Phases 3→4→5 are a strict chain (same files, each extends the previous). Phases 6, 7, 8 depend only on
Phase 2 and can proceed in any order relative to each other and to 3–5. Phase 9 depends on Phase 2 only.
Phase 10 depends on Phase 3 (needs the cached flight list already fetched there). Phase 11 depends on
Phase 3's filter/search/sort state existing.

---

## Phase 1 — Setup

- [x] T001 Re-verify Leaflet and Chart.js are still the latest stable releases (`gh api
      repos/Leaflet/Leaflet/releases/latest`, `gh api repos/chartjs/Chart.js/releases/latest`) if
      implementation starts more than a few days after this plan — confirmed `v1.9.4` / `v4.5.1` at
      planning time
- [x] T002 [P] Vendor the missing Leaflet 1.9.4 marker/layer images (`marker-icon.png`,
      `marker-icon-2x.png`, `marker-shadow.png`, `layers.png`, `layers-2x.png`) from the Leaflet v1.9.4
      GitHub release into `static/vendor/leaflet/images/`

## Phase 2 — Foundation

- [x] T003 Create `static/refdata.js` — fetch-once, in-memory-cached helper for `GET /api/sites`,
      `/api/gliders`, `/api/harnesses`, `/api/categories`, `/api/buddies`, `/api/regions`, plus join
      helpers to resolve an ID to its display name

---

## Phase 3 — Browse, search, filter, sort, paginate flights [US1]

**Goal**: a pilot can find any of the 600 historical flights without knowing its date or row number.
**Independent test criteria**: load `/flights` while logged in; free-text search, each filter, every
sortable column, and pagination all work against the real seeded data; an empty result set shows a
distinct empty state; no console errors.

- [x] T004 [US1] Add `GET /flights` route serving `static/flights.html` in
      `src/flightlog/api/routers/pages.py`
- [x] T005 [US1] Create `static/flights.html` — page shell, search box, filter row, sortable table header,
      pagination controls (nav link already present in `bootstrap.js`'s `NAV_LINKS`)
- [x] T006 [US1] Create `static/flights.js` — `fetchAuth('/api/flights')` once, join via `refdata.js`,
      implement free-text search (launch site, landing site, category, glider, notes), the five filters
      (year, category, glider, launch site, region), sortable columns (default: date descending),
      pagination, URL query-string sync for the current search/filter/sort state, empty-state rendering,
      console logging per `03-frontend-conventions.md`
- [x] T007 [US1] Add `flights.*` keys (search placeholder, column headers, filter labels, empty state,
      pagination controls) to `static/i18n/en.json`

## Phase 4 — Add and edit a flight inline [US2]

**Goal**: log or correct a flight without leaving the list.
**Independent test criteria**: from `/flights`, add a new flight and edit an existing one through the
drawer; an invalid submission shows the error next to the specific field; the list updates in place
without a full reload; deleting a flight requires an explicit confirmation step first.

- [x] T008 [US2] Extend `static/flights.html` with the add/edit drawer markup — every `FlightCreate`/
      `FlightUpdate` field, a buddy multi-select, a delete-confirmation control
- [x] T009 [US2] Extend `static/flights.js` — open/close the drawer, populate dropdowns from
      `refdata.js`, `POST /api/flights` on create, `PUT /api/flights/{id}` on edit, render per-field
      validation errors from the `VALIDATION_FAILED` envelope's `details`, `DELETE /api/flights/{id}`
      behind the confirmation step, in-place list update with the changed row highlighted/scrolled into
      view
- [x] T010 [US2] Add `flights.drawer.*` and `flights.delete_confirm.*` keys to `static/i18n/en.json`

## Phase 5 — Flight detail view [US3]

**Goal**: a stable, linkable page showing everything about one flight.
**Independent test criteria**: navigate directly to `/flights/{id}` (as a fresh page load, not only via
in-app navigation); every stored and computed field renders, with a clear "not recorded" state for null
optional fields; links to launch/landing site, glider, harness, and buddies work wherever a corresponding
page exists.

- [x] T011 [US3] Add `GET /flights/{flight_id}` route serving `static/flight-detail.html` in
      `src/flightlog/api/routers/pages.py`
- [x] T012 [US3] Create `static/flight-detail.html`
- [x] T013 [US3] Create `static/flight-detail.js` — read the flight id from the URL, `GET
      /api/flights/{id}`, join via `refdata.js`, render every stored field plus `alt_gain_m`/
      `site_drop_m`/`total_descent_m`, "not recorded" states, links to related entities
- [x] T014 [US3] Add `flight_detail.*` keys to `static/i18n/en.json`
- [x] T015 [US3] Link each row in `static/flights.js`'s list to its `/flights/{id}` detail page

## Phase 6 — Sites: list and map pin-drop [US4]

**Goal**: the site catalogue matches reality, including manually placed coordinates.
**Independent test criteria**: `/sites` lists every site with its launch/landing flags; dropping a pin on
an unpinned site persists `lat`/`lon` and sets `coord_source="manual"`; moving an existing pin updates it
the same way; sites with and without coordinates are visually distinct in both the list and the map.

- [x] T016 [US4] Modify `src/flightlog/api/routers/sites.py`: `POST`/`PUT` set `coord_source = "manual"`
      server-side whenever the request includes a non-null `lat` and/or `lon` (`contracts/
      sites-coord-source.md`)
- [x] T017 [US4] [P] Extend `tests/backend/test_sites.py`: `coord_source` becomes `"manual"` on create
      with `lat`/`lon`, becomes `"manual"` on update with `lat`/`lon`, stays untouched when neither is
      present
- [x] T018 [US4] Add `GET /sites` route serving `static/sites.html` in
      `src/flightlog/api/routers/pages.py`
- [x] T019 [US4] Create `static/sites.html` — site list table plus a Leaflet map container (nav link
      already present in `bootstrap.js`'s `NAV_LINKS`)
- [x] T020 [US4] Create `static/sites.js` — `GET /api/sites`, render the list, initialize Leaflet against
      the OpenStreetMap tile server with attribution (`research.md`), click-to-drop / drag-to-move a pin
      → `PUT /api/sites/{id}`, distinguish pinned vs unpinned sites in both list and map
- [x] T021 [US4] Add `sites.*` keys to `static/i18n/en.json`

## Phase 7 — Equipment: gliders and harnesses [US5]

**Goal**: the pilot's gear list stays current; retired gear is excluded from new-flight defaults but
never breaks historical flights.
**Independent test criteria**: `/equipment` lists gliders and harnesses; create, edit, and retire all
work; a retired item is visually distinct and excluded from `/flights`' add/edit drawer's default choices,
while remaining correct on any historical flight that references it.

- [x] T022 [US5] Add `GET /equipment` route serving `static/equipment.html` in
      `src/flightlog/api/routers/pages.py`
- [x] T023 [US5] Create `static/equipment.html` (nav link already present in `bootstrap.js`'s
      `NAV_LINKS`)
- [x] T024 [US5] Create `static/equipment.js` — CRUD against `GET/POST/PUT /api/gliders` and
      `/api/harnesses`, `POST .../{id}/retire`, retired-item styling
- [x] T025 [US5] Add `equipment.*` keys to `static/i18n/en.json`
- [x] T026 [US5] Update `static/flights.js`'s drawer (from Phase 4) so its glider/harness dropdowns
      exclude retired equipment by default (FR-013)

## Phase 8 — Historical import findings review [US6]

**Goal**: a read-only page showing exactly what the v0.2 production import found, so the pilot knows what
to clean up.
**Independent test criteria**: `/import` shows the unresolved-harness finding (×3), the three region
mismatches, the one altitude mismatch, and the seven buddy-name proposals — matching the real production
import run recorded in `RESUME.md`; the page performs no write, re-import, or resolution action.

- [x] T027 [US6] Run a dry-run of `run_import()` against `olddata/Flugbuch.xlsx` and use its
      `ImportReport` output to populate `src/flightlog/core/import_history.py`'s frozen
      `HistoricalImportSummary` constant (`data-model.md`) — generated from source, never hand-
      transcribed from this session's chat or from `RESUME.md`
- [x] T028 [US6] Create `src/flightlog/models/import_report.py` (`data-model.md`'s response schema)
- [x] T029 [US6] Create `src/flightlog/api/routers/import_report.py` — `GET /api/import-report`
      (`contracts/import-report.yaml`)
- [x] T030 [US6] [P] Register the `import_report` router in `src/flightlog/api/main.py`
- [x] T031 [US6] [P] Create `tests/backend/test_import_report.py` — 200 with the documented shape,
      requires auth, values match the frozen constant from T027
- [x] T032 [US6] Add `GET /import` route serving `static/import.html` in
      `src/flightlog/api/routers/pages.py`
- [x] T033 [US6] Add a `{ page: 'import', href: '/import', key: 'nav.import' }` entry to `NAV_LINKS` in
      `static/bootstrap.js`
- [x] T034 [US6] Create `static/import.html`
- [x] T035 [US6] Create `static/import.js` — `GET /api/import-report`, render each finding group, an
      explicit "this is a historical snapshot, not a live view" note per the spec's Edge Cases
- [x] T036 [US6] Add `nav.import` and `import.*` keys to `static/i18n/en.json`

## Phase 9 — Contacts [US7] (P2)

**Goal**: a simple named-buddy list for tagging flights.
**Independent test criteria**: `/contacts` lists buddies with an accurate per-buddy flight-tag count;
create, edit, and delete all work; deleting a buddy removes its tag from any flight without deleting the
flight.

- [ ] T037 [US7] Add `GET /contacts` route serving `static/contacts.html` in
      `src/flightlog/api/routers/pages.py`
- [ ] T038 [US7] Add a `{ page: 'contacts', href: '/contacts', key: 'nav.contacts' }` entry to
      `NAV_LINKS` in `static/bootstrap.js`
- [ ] T039 [US7] Create `static/contacts.html`
- [ ] T040 [US7] Create `static/contacts.js` — CRUD against `GET/POST/PUT/DELETE /api/buddies`, per-buddy
      flight count computed from the cached flight list (`refdata.js`), delete confirmation
- [ ] T041 [US7] Add `nav.contacts` and `contacts.*` keys to `static/i18n/en.json`

## Phase 10 — CSV export [US8] (P2)

**Goal**: one export action produces the full flight log as a CSV, independent of the current view.
**Independent test criteria**: clicking Export on `/flights` downloads a CSV containing every flight with
the documented fixed columns, correctly encoded (German characters in site/gear/category names render
correctly in a spreadsheet application), regardless of the list's active search/filter/sort.

- [ ] T042 [US8] Add a CSV-generation helper to `static/flights.js` building the fixed column set from
      the already-cached full flight list joined via `refdata.js`, triggering a UTF-8-encoded browser
      download
- [ ] T043 [US8] Add an Export button to `static/flights.html`
- [ ] T044 [US8] Add `flights.export.*` keys to `static/i18n/en.json`

## Phase 11 — Remember last-used filters and sort [US9] (P3)

**Goal**: returning to `/flights` keeps the pilot's last filter/search/sort state.
**Independent test criteria**: set filters and a non-default sort, navigate away, come back — the same
state is applied; an explicit filtered URL still takes precedence over stored state when both are
present.

- [ ] T045 [US9] Persist the current filter/search/sort state to `localStorage` in `static/flights.js`
      and restore it on load when the URL carries no explicit filter/sort query params

---

## Final Phase — Polish

- [ ] T046 [P] Update `home.empty_hint` in `static/index.html`'s `en.json` copy and add a logged-in
      "go to flights" link (`research.md`)
- [ ] T047 Manual live-boot verification pass across all six new pages plus flight-detail, home, and
      login: golden path, empty states, validation errors, keyboard-only navigation (NFR-002), delete
      confirmations (NFR-003), i18n completeness (no hardcoded chrome strings), console logging present
      per `03-frontend-conventions.md`
- [ ] T048 Run `ruff check`, `ruff format --check`, and the full `pytest` suite — all clean
- [ ] T049 Run `.ai/prompts/sync.md` to update `architecture.md`, `features.md`, and `RESUME.md` with
      what actually shipped
