# Implementation Plan: Core Data & Excel Import

## Technical Context

- **Stack**: unchanged from v0.1 — FastAPI + SQLAlchemy 2.0 declarative + SQLite (no Alembic), Pydantic
  v2 schemas, PyJWT/bcrypt auth already shipped. No new framework-level dependency.
- **New dependency, already declared**: `openpyxl (>=3.1.5,<4.0.0)` under the `importer` extra in
  `pyproject.toml`. Re-verified against PyPI on 2026-08-06 — still the latest release, no pin change
  needed (`research.md`).
- **Architecture approach**: nine new ORM tables (`regions`, `sites`, `user_site_prefs`, `gliders`,
  `harnesses`, `flight_categories`, `buddies`, `flights`, `flight_buddies`), one router per non-trivial
  domain (`regions`, `sites`, `gliders`, `harnesses`, `categories`, `buddies`, `flights`), each with a
  `_get_own_<entity>()` ownership helper that returns 404 for both "missing" and "not yours" — see the
  Constitution Check row below. `core/flights.py` holds the list/filter/sort logic behind
  `GET /api/flights`, per the layout already documented in `01-project-overview.md`; the router calls
  into it rather than embedding query logic itself. `core/aliases.py` + `core/importer.py` are new,
  CLI-only (no HTTP route) — see `contracts/endpoints.md`.
- **`services/geo.py` / coordinate dedup — not in this feature.** `SitesConfig.dedup_radius_m` stays
  declared-but-unconsumed, the same state `StorageConfig.igc_dir`/`max_igc_bytes` shipped in v0.1 with no
  IGC feature yet — established precedent, not a stub. No FR in `spec.md` covers proximity dedup, and the
  legacy workbook has no coordinates at all (`architecture.md`), so v0.2 produces no lat/lon to dedupe
  against in the first place. Revisit once something actually writes site coordinates (v0.3 manual pin
  drop or v0.4 IGC backfill).
- **Deviation from the plan template**: no OpenAPI YAML contracts. `contracts/endpoints.md` is a plain
  table instead, matching this project's own stated convention (`architecture.md`: *"Routes are not
  enumerated here beyond the prefix — read the router file, which is the source of truth"*). A hand-kept
  OpenAPI copy would drift from the FastAPI-generated schema the moment a query parameter changes.

## Constitution Check

| Principle (`00-ai-usage.md`) | Status |
|---|---|
| 1. Read before acting | Satisfied — this plan follows a research pass that read `models.py`, `db.py`, `auth.py`, `dependencies.py`, `errors.py`, `main.py`, `config.py`, `conftest.py`, and the legacy workbook itself directly |
| 2. Plan before building | Satisfied by this document; implementation does not start until a separate go-ahead |
| 3. Minimal scope | Satisfied — `site_observations`, generic per-account category seeding, `services/geo.py`, and all XContest columns are explicitly excluded as v0.4/v0.5/v0.8 concerns with no consumer or FR yet (`research.md`, `data-model.md`). `elevation_igc_m`/`coord_accuracy_m` on `sites` are the one exception, and deliberately so — see Data Model Summary |
| 4. Tool-agnostic instructions | N/A — no tool-specific file touched |
| 5. Keep docs in sync | Addressed in Phase 6 below — `architecture.md`, `features.md`, `README.md` updated once implementation lands. Also fixed now: `02-backend-conventions.md`'s `_get_own_glider` sample showed a 403 for "not yours," contradicting `06-testing-conventions.md`'s coverage table and this feature's own `spec.md` FR-018 — corrected in place, same class of fix as the already-annotated migration-doctrine conflict |
| 6. No secrets committed | N/A — no secrets introduced |
| 7. Prod is off-limits | N/A — no deployment action in this feature |

No unresolved violations.

## Data Model Summary

Nine tables. Full column-level detail in `data-model.md`. In one line each:

- `regions` — shared, not owner-scoped, seeded once from a hand-transcribed list.
- `sites` — one row can be launch, landing, or both; `owner_id` nullable (reserved for v0.8 sharing, but
  every v0.2 row is owner-set); coordinates and region are optional. Also carries `elevation_igc_m` /
  `coord_accuracy_m`, unpopulated until v0.4 — added now while the table is being created fresh rather
  than deferred, since a later `ALTER TABLE` would cost a migration guard this doesn't.
- `user_site_prefs` — per-pilot alias/elevation/favourite overlay on a site, composite PK.
- `gliders`, `harnesses` — owner-scoped gear, retire rather than delete once referenced.
- `flight_categories` — owner-scoped, `is_hike_fly` / `is_training` flags drive statistics later; archive
  rather than delete once referenced.
- `buddies` — owner-scoped contact, optional two-sided link to another pilot account.
- `flights` — the core record; altitude-derived figures are computed on read, never stored; `import_key`
  gives the importer idempotency.
- `flight_buddies` — join table, composite PK.

## File Structure

```
src/flightlog/database/models.py        # + Region, Site, UserSitePref, Glider, Harness,
                                          #   FlightCategory, Buddy, Flight, FlightBuddy
src/flightlog/database/db.py             # + _seed_regions(engine), called from init_db()
src/flightlog/models/
  sites.py                               # NEW — SiteCreate/Update/Out, UserSitePrefUpdate/Out
  gliders.py                             # NEW
  harnesses.py                           # NEW
  categories.py                          # NEW
  buddies.py                             # NEW
  flights.py                             # NEW — FlightOut includes computed alt_gain_m etc.
  regions.py                             # NEW — RegionOut only, no Create/Update (shared data)
src/flightlog/api/routers/
  regions.py                             # NEW
  sites.py                               # NEW
  gliders.py                             # NEW
  harnesses.py                           # NEW
  categories.py                          # NEW
  buddies.py                             # NEW
  flights.py                             # NEW
src/flightlog/api/main.py                # + include_router() for all seven above
src/flightlog/core/
  flights.py                             # NEW — list/filter/sort/paginate, called from the router
  aliases.py                             # NEW — SITE_ALIASES, GLIDER_ALIASES, HARNESS_ALIASES,
                                          #   CATEGORY_ALIASES, LAUNCH_TYPE_MAP, SITE_REGION,
                                          #   CATEGORY_FLAGS (all as data, not inline conditionals)
  importer.py                            # NEW — python -m flightlog.core.importer, --dry-run default
tests/backend/
  test_schema.py                         # NEW — all nine tables created, regions seeded (12, idempotent)
  test_sites.py, test_gliders.py, test_harnesses.py,
  test_categories.py, test_buddies.py, test_flights.py   # NEW — CRUD + ownership scoping per domain
  test_importer.py                       # NEW — synthetic small workbook fixture, not the real one
tests/fixtures/
  flugbuch_sample.xlsx                   # NEW — small synthetic workbook for test_importer.py
.ai/context/architecture.md              # updated: 9 tables move from "planned" to "shipped v0.2"
.ai/context/features.md                  # updated: v0.2 marked shipped once complete
README.md                                # updated: status line, feature list
```

## Implementation Phases

### Phase 1 — Schema

Nine ORM classes in `models.py`, following `User`'s exact conventions (`new_uuid`, `utcnow`,
`UtcDateTime`, `owner_id` indexed). `_seed_regions()` in `db.py`, called from `init_db()`. No column
migrations needed — all nine are new tables, so `Base.metadata.create_all()` is the whole story.

### Phase 2 — Schemas

Pydantic `Create`/`Update`/`Out` models per domain in `models/`.

### Phase 3 — Core logic & CRUD routers

`core/flights.py` holds list/filter/sort/pagination over `Flight`. Seven routers, each with a
`_get_own_<entity>()` helper that returns 404 for both "missing" and "not yours," registered in
`main.py`. `flights.py`'s `GET /{id}` and list responses compute `alt_gain_m` / `site_drop_m` /
`total_descent_m` at serialization time per the `COALESCE` rule in `architecture.md` — never stored.
**Route-order trap**: `PUT /api/categories/reorder` must be declared before `PUT /api/categories/{id}`
in `categories.py` — FastAPI matches routes in declaration order, so the reverse order would swallow
`/reorder` requests into the `{id}` handler with `id="reorder"`.

### Phase 4 — Aliaser

`core/aliases.py`: normalization tables transcribed from `DropDownData` (spelling variants →
canonical name, one dict per entity kind) and the `SITE_REGION` mapping reconstructed from the
`Übersicht` formulas (`research.md`). Each table is enumerable so the importer's dry-run report can
count hits per table, per FR-011/FR-013.

### Phase 5 — Importer

`core/importer.py`. Reads `Flugbuch` row by row (`import_key = "xlsx:<row>"`), resolves every reference
through the aliaser, skips and reports (never inserts a placeholder for) any row it can't resolve,
recomputes region totals and compares against `Übersicht`'s own summary (expected to reproduce the
confirmed region-formula mismatches traced in `research.md` — not a flat 4-flight gap, since
`SITE_REGION` is built from the more complete yearly formulas, not the stale Total column), compares
computed altitude figures against the sheet's own `Höhe diff.` / `Altgain` columns per flight, and
proposes buddy candidates from `Kommentar` text without creating them. `--dry-run` by default; a second
run against the same file is a no-op.

### Phase 6 — Tests & docs

CRUD + ownership tests per domain (create, list-scoped-to-owner, another user's row → 404, `owner_id` in
body ignored — per `06-testing-conventions.md`'s stated coverage expectations). Importer tests run
against a small synthetic fixture workbook (`tests/fixtures/flugbuch_sample.xlsx`), not the real
600-flight file — keeps the suite fast and doesn't hard-couple CI to personal data that must eventually
leave git history (`04-constraints.md`). One additional real-data regression test, gated the same way
`test_igc_analysis.py` gates the real IGC fixtures, asserts the actual import produces exactly 600
flights and reproduces the confirmed region-formula mismatches and the single altgain mismatch (row
387) — this is intentionally the one test module in the suite that reads `olddata/Flugbuch.xlsx`
directly, and it will need to be removed or replaced with a fixture alongside the file's eventual
removal from git history at v0.8.

Update `architecture.md` (move the nine tables from "planned" to "shipped v0.2", document the region
formula bug and its confirmed reproduction), `features.md` (mark v0.2 shipped), `README.md` (status +
feature list) — per the constitution's docs-in-sync rule.

## Dependencies

- `openpyxl (>=3.1.5,<4.0.0)` — already declared, re-verified current.
- No new runtime dependency beyond that. No new GitHub Action, no new vendored frontend library (no UI
  in this feature).

## Risk & Mitigations

- **Manual transcription errors in `aliases.py`'s alias/region tables.** Mitigated structurally: the
  formula cross-check (FR-016) and the "exactly 600 flights, zero silently dropped" success criterion
  both fail loudly if a transcription error leaves a row unresolved — there's no code path that lets a
  bad alias entry pass silently.
- **`olddata/Flugbuch.xlsx` is personal data, committed only because the repo is currently private.**
  The one real-data regression test in Phase 6 is a deliberate, isolated exception to "tests don't touch
  personal data" — flagged so it isn't missed when `04-constraints.md`'s pre-public-release history scrub
  happens at v0.8.
- **`Flugbuch`'s own cells have no formulas** (confirmed by direct inspection) — only `Übersicht`'s
  summary rows do. So the importer reading flight data with `data_only=True` carries no risk of reading a
  stale cached formula result; that risk is fully contained to the cross-check comparison, which is
  explicitly a "report a mismatch" step, never a silent overwrite either direction.
