# Tasks: Core Data & Excel Import

## Summary
- Total tasks: 42
- Parallel opportunities: 18 (marked `[P]`)
- MVP scope: Phase 3 (US1 — Manage my own data) is the smallest independently valuable slice per the
  template convention. For what this feature is actually for, the practical MVP is **Phase 3 + Phase 4**
  (US1 + US2) — CRUD alone doesn't get the 600 flights out of the spreadsheet, which is this feature's
  stated point (`spec.md` Overview).

## User story numbering
Spec lists stories by priority narrative; tasks number them in build order (P1s reordered so the
schema/CRUD foundation import depends on comes first):

| US# | Story | Priority |
|---|---|---|
| US1 | Manage my own data | P1 |
| US2 | Historical import | P1 |
| US3 | Trustworthy import report | P1 |
| US4 | Data stays private per pilot | P2 |
| US5 | Safe to re-run | P2 |
| US6 | Buddy suggestions from history | P3 |

## Dependencies

```
Phase 1 (Setup)
   └─▶ Phase 2 (Foundation: schema + seed + Pydantic schemas)
          └─▶ Phase 3 (US1: CRUD routers)
                 ├─▶ Phase 4 (US2: importer core)
                 │      └─▶ Phase 5 (US3: import report)
                 │             └─▶ Phase 7 (US5: idempotent re-run)
                 │                    └─▶ Phase 8 (US6: buddy proposals)
                 └─▶ Phase 6 (US4: ownership-privacy tests, extends Phase 3's routers)
                        └─▶ Final Phase (Polish)
```
US4's tests extend the routers Phase 3 already built — it can start as soon as Phase 3 lands, in
parallel with Phase 4 onward. US6 depends on US2/US3/US5's importer, not on US4.

## Phase 1 — Setup

- [x] T001 Confirm the `importer` extra (`openpyxl`) installs cleanly in the dev environment; no
      `pyproject.toml` change expected — `research.md` already re-verified the pin as current.
- [x] T002 [P] Create `tests/fixtures/flugbuch_sample.xlsx` — a small synthetic workbook with `Flugbuch`,
      `DropDownData` and `Übersicht` sheets, covering: two flights on the same date, one alias-needing
      site/glider name, one deliberately unresolvable category value, and enough `Übersicht` "Launch
      Statistics" + "Flight Area" formula rows to exercise region reconciliation.

## Phase 2 — Foundation (blocking for every story)

- [x] T003 Add `Region`, `Site`, `UserSitePref`, `Glider`, `Harness`, `FlightCategory`, `Buddy`, `Flight`,
      `FlightBuddy` ORM classes to `src/flightlog/database/models.py` per `data-model.md`, following
      `User`'s conventions (`new_uuid`, `utcnow`, `UtcDateTime`, indexed `owner_id`,
      `UniqueConstraint("owner_id", "import_key")` on `Flight`). Update the module docstring's table list.
- [x] T004 Add `_seed_regions(engine)` to `src/flightlog/database/db.py`, called from `init_db()`,
      seeding the 12 regions transcribed in `research.md`.
- [x] T005 [P] Add Pydantic `Create`/`Update`/`Out` schemas: `src/flightlog/models/regions.py`,
      `sites.py`, `gliders.py`, `harnesses.py`, `categories.py`, `buddies.py`, `flights.py`.
- [x] T006 `tests/backend/test_schema.py` — `Base.metadata.create_all()` produces all nine new tables;
      `_seed_regions` seeds exactly 12 rows and is idempotent on a second call.

## Phase 3 — Manage my own data [US1]

**Goal**: a pilot can create, read, update and archive/delete every entity kind, scoped to themselves.
**Independent test criteria**: for each domain, create/list/get/update succeeds against the caller's own
rows.

- [x] T007 [US1] Establish the `_get_own_<entity>()` ownership-helper pattern — 404 for both "missing"
      and "not yours," never 403 (see the `02-backend-conventions.md` fix already applied this session).
- [x] T008 [P] [US1] `src/flightlog/api/routers/regions.py` — `GET /api/regions`.
- [x] T009 [P] [US1] `src/flightlog/api/routers/sites.py` — CRUD + `PUT /{id}/prefs`.
- [x] T010 [P] [US1] `src/flightlog/api/routers/gliders.py` — CRUD + `POST /{id}/retire`.
- [x] T011 [P] [US1] `src/flightlog/api/routers/harnesses.py` — same shape as gliders.
- [x] T012 [P] [US1] `src/flightlog/api/routers/categories.py` — CRUD + `POST /{id}/archive`. Declare
      `PUT /reorder` **before** `PUT /{id}` — route-order trap noted in `plan.md`.
- [x] T013 [P] [US1] `src/flightlog/api/routers/buddies.py` — CRUD + `/link`, `/link/accept`,
      `/link/decline`; `/link` always returns 202.
- [x] T014 [US1] `src/flightlog/core/flights.py` — list/filter/sort/paginate over `Flight` (filters:
      `year`, `category_id`, `glider_id`, `site_id`, `region_id`).
- [x] T015 [US1] `src/flightlog/api/routers/flights.py` — CRUD calling into `core/flights.py`; `GET`
      responses compute `alt_gain_m`/`site_drop_m`/`total_descent_m` via the `COALESCE` rule, never
      stored.
- [x] T016 [US1] Register all seven routers in `src/flightlog/api/main.py`.
- [x] T017 [P] [US1] `tests/backend/test_sites.py` — create/list/get/update/delete, prefs upsert, delete
      blocked while a flight references the site.
- [x] T018 [P] [US1] `tests/backend/test_gliders.py` — create/list/get/update/retire; delete blocked
      while a flight references the glider.
- [x] T019 [P] [US1] `tests/backend/test_harnesses.py` — same shape, including the delete-blocked-while-
      referenced check.
- [x] T020 [P] [US1] `tests/backend/test_categories.py` — create/list/get/update/reorder/archive; delete
      blocked while a flight references the category; regression test for the reorder-vs-`{id}` route
      order.
- [x] T021 [P] [US1] `tests/backend/test_buddies.py` — create/list/get/update/delete; `/link` returns 202
      identically for a registered and an unregistered contact.
- [x] T022 [US1] `tests/backend/test_flights.py` — create/list/get/update/delete; computed altitude
      fields present and correct on `GET`, including the `COALESCE` precedence itself: a flight-level
      elevation override beats a `user_site_prefs` override, which beats the site's own `elevation_m`.

## Phase 4 — Historical import [US2]

**Goal**: running the import against the real workbook produces exactly 600 flights and all referenced
entities, resolved through the aliaser.
**Independent test criteria**: dry-run makes no writes; a `--write` run against the fixture workbook
produces the expected rows.

- [x] T023 [US2] `src/flightlog/core/aliases.py` — `SITE_ALIASES`, `GLIDER_ALIASES`, `HARNESS_ALIASES`,
      `CATEGORY_ALIASES`, `LAUNCH_TYPE_MAP`, `SITE_REGION`, `CATEGORY_FLAGS`, transcribed from
      `DropDownData` and the `Übersicht` region formulas per `research.md`.
- [x] T024 [US2] `src/flightlog/core/importer.py` — read `Flugbuch` row by row via `openpyxl`, resolve
      every reference through `core/aliases.py`, write `regions`/`sites`/`gliders`/`harnesses`/
      `flight_categories`/`flights` (skip and collect — never insert a placeholder — anything
      unresolved), `import_key = "xlsx:<row>"`, `--dry-run` default, `--write` to commit.
- [x] T025 [P] [US2] `tests/backend/test_importer.py` — dry-run makes zero DB writes against the fixture
      workbook; `--write` produces the expected entity counts; alias resolution hits the expected
      canonical names.
- [x] T026 [US2] One real-data regression test (same file) asserting import of `olddata/Flugbuch.xlsx`
      produces exactly 600 flights — the one test in the suite reading personal data directly; flagged
      in `plan.md`'s Risk section for removal/replacement at v0.8's history scrub.

## Phase 5 — Trustworthy import report [US3]

**Goal**: the import's dry-run output is enough to trust before writing.
**Independent test criteria**: report states per-kind counts, lists normalizations and unresolved values,
flags the region-total and altitude-figure mismatches.

- [x] T027 [US3] Extend `core/importer.py` with the dry-run report: per-entity read/write counts, every
      alias hit, every unresolved value.
- [x] T028 [US3] Add region-count reconciliation: recompute per-region flight counts, compare against
      `Übersicht`'s "Flight Area" summary, report the mismatch. Actual result differs from the initial
      guess in `research.md`'s first pass: `SITE_REGION` is reconstructed from the more complete yearly
      formulas, not the stale Total column, so it reproduces higher counts for Interlaken/Grindelwald
      and a residual 1-flight gap for Fiescheralp (genuinely unreferenced anywhere) — see
      `architecture.md`'s Statistics section for the confirmed final numbers.
- [x] T029 [US3] Add the formula cross-check: recompute `alt_gain_m`/`site_drop_m` per flight, compare
      against the sheet's `Altgain`/`Höhe diff.` columns, report per-flight mismatches.
- [x] T030 [P] [US3] Extend `tests/backend/test_importer.py` — report contains expected counts/hits/
      mismatches against the fixture workbook; the real-workbook test asserts the report reproduces the
      confirmed region mismatches (Fiesch, Interlaken, Grindelwald) and the single altgain mismatch
      (row 387).

## Phase 6 — Data stays private per pilot [US4]

**Goal**: cross-owner access is indistinguishable from non-existence, everywhere.
**Independent test criteria**: another user's row via GET/PUT/DELETE returns 404 for every entity kind;
`owner_id` in a request body is always ignored.

- [x] T031 [P] [US4] Extend each of `test_sites.py`, `test_gliders.py`, `test_harnesses.py`,
      `test_categories.py`, `test_buddies.py`, `test_flights.py` — another user's row → 404 on
      GET/PUT/DELETE; `owner_id` supplied in a create/update body is ignored.
- [x] T032 [US4] Extend `test_importer.py` — every entity the import writes gets `owner_id` from the
      (single) existing account, never from source data.

## Phase 7 — Safe to re-run [US5]

**Goal**: re-running the import after a successful write changes nothing.
**Independent test criteria**: two consecutive `--write` runs leave every count unchanged.

- [x] T033 [US5] In `core/importer.py`, look up existing rows by `import_key` (flights) and by canonical
      name + `owner_id` (sites/gliders/harnesses/categories) before writing; skip rows that already
      exist.
- [x] T034 [P] [US5] Extend `test_importer.py` — running `--write` twice against the fixture workbook
      leaves every count unchanged after the second run.
- [x] T035 [US5] Extend the real-data regression test (T026) — a second `--write` run against
      `olddata/Flugbuch.xlsx` still yields exactly 600 flights.

## Phase 8 — Buddy suggestions from history [US6]

**Goal**: names recognized in flight notes are proposed, never auto-created.
**Independent test criteria**: a known name in a fixture flight's comment appears as a dry-run proposal;
no `buddies` row is created for it automatically.

- [x] T036 [US6] Add a maintained name list and case-insensitive, word-boundary matching pass in
      `core/aliases.py` / `core/importer.py` over `Kommentar`, surfaced in the dry-run report as buddy
      proposals — no automatic `buddies` row creation.
- [x] T037 [P] [US6] Extend `test_importer.py` — a name in the fixture workbook's comments is proposed;
      the proposal creates no `buddies` row.

## Final Phase — Polish

- [x] T038 Update `.ai/context/architecture.md` — move the nine tables from "planned" to "shipped v0.2";
      document the region-formula bug and its confirmed reproduction (`research.md`).
- [x] T039 Update `.ai/context/features.md` — mark v0.2 shipped, matching the v0.1 entry's style.
- [x] T040 Update `README.md` — status line and feature list.
- [x] T041 Run `poetry run ruff check src/ tests/` and `poetry run ruff format --check src/ tests/`; fix
      any findings.
- [x] T042 Run the full test suite (`poetry run pytest --tb=short -q`); confirm green.
