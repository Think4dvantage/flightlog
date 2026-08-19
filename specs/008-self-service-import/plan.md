# Implementation Plan: Self-Service Spreadsheet Import

## Technical Context

New router `api/routers/imports.py` (`/api/imports`, JWT-authenticated, owner-scoped like every
other domain router). New core module `core/spreadsheet_import.py` — deliberately **not** shared
with `core/importer.py`: that module is tightly coupled to the legacy workbook's fixed column
positions and this pilot's own `core/aliases.py` alias tables (German legacy spellings); this
feature parses an arbitrary pilot's arbitrary spreadsheet by header-name mapping instead, with
exact-string (never fuzzy) reference-data matching per the spec. Same reasoning `models/
integration.py`'s URL validator duplication already established: genuinely independent contracts
don't share code just because they're superficially similar.

Excel via `openpyxl` (already a dependency). CSV via the stdlib `csv` module — no new dependency.
No new third-party package needed.

**Stateless upload/preview/commit** — the file is re-sent on both `preview` and `commit` calls
rather than cached server-side between wizard steps. No orphaned-upload cleanup problem, no
"import session expired" edge case, consistent with this app's general "don't materialise what
you don't have to" bias (`architecture.md`'s Statistics section).

## Constitution Check

- **Plan before building**: this document.
- **Minimal scope**: no format-specific parsers (XCTrack/FlySkyHy/SkyViz), no cross-source dedup,
  no hikes/hardware-service/goals import — matches spec's Out of Scope.
- **Never accept `owner_id` from a request body**: every write derives it from `current_user.id`.
- **No Alembic / `.sql` migrations**: new table via `Base.metadata.create_all()`; new columns on
  existing tables via `_run_column_migrations()`'s `PRAGMA table_info()` guard, same as every
  prior schema change.
- **404 not 403** on any other pilot's import run.
- **Never leak existence / never guess-match**: reference-data reuse is exact-string only,
  mirroring `core/importer.py`'s own `_get_or_create_*` shape but without the alias-table fuzzy
  layer (that layer is specific to this pilot's own legacy data cleanup).

## Data Model Summary

**New table `import_runs`**: `id`, `owner_id` (FK users, cascade), `source_filename`,
`column_mapping` (JSON text — `{flightlog_field: source_column_header}`), `row_count`,
`imported_count`, `skipped_count`, `created_at`.

**New nullable `import_run_id` column** (FK `import_runs.id`, `ondelete="SET NULL"`) on `flights`,
`sites`, `gliders`, `harnesses`, `flight_categories` — tags exactly what a run created, for undo.
Reused rows (matched by exact name, not created) are never tagged.

**Idempotency reuses the existing `flights.import_key` column and its existing
`UniqueConstraint(owner_id, import_key)`** rather than adding a new mechanism —
`import_key = f"upload:{sha256_hex(file_bytes)}:{row_index}"`. Content-addressed, mirroring the
IGC storage pattern already in this codebase. A byte-identical re-upload produces the same keys,
so a lookup-before-insert (same pattern as `core/importer.py`) skips rows already imported —
FR-010 — without a new column or constraint.

**Undo safety**: a tagged flight is deleted only if `updated_at IS NULL` (never edited, never had
a track attached — `Flight.updated_at` has `onupdate=utcnow`, which fires on any UPDATE
regardless of which columns changed, including the IGC-attach code path). A tagged reference row
(site/glider/harness/category) is deleted only if no flight belonging to this owner still
references it — computed at undo time, not inferred from the row's own `updated_at`, since the
real risk is a *different*, later flight now depending on it, not whether the row's own fields
were edited. Anything not safe to delete has its `import_run_id` cleared (kept, just untagged)
rather than blocking the whole undo.

## File Structure

- `src/flightlog/database/models.py` — `ImportRun` model; `import_run_id` column on the five
  tables above.
- `src/flightlog/database/db.py` — `_run_column_migrations()` gets five more guarded
  `ALTER TABLE` statements; `Base.metadata.create_all()` covers the new table for free.
- `src/flightlog/core/spreadsheet_import.py` — `read_columns()`, `parse_rows()`,
  `commit_import()`, `undo_import()`. Row-level date/number coercion mirrors `core/importer.py`'s
  `_to_date`/`_to_int` shape but must additionally parse CSV string dates (openpyxl already
  returns real `date`/`datetime` objects for Excel date cells; CSV never does) — ISO format
  first, then a short fixed list of common alternates, never a new `dateutil` dependency.
- `src/flightlog/models/imports.py` — Pydantic schemas: `ImportColumnsOut`, `ImportMappingIn`,
  `ImportPreviewOut`, `ImportCommitOut`, `ImportRunOut`.
- `src/flightlog/api/routers/imports.py` — registered in `main.py`.
- `src/flightlog/config.py` + `config.yml.example` — `StorageConfig.max_import_bytes`, mirroring
  `max_igc_bytes`.
- `static/import.html` / `static/import.js` — new page, nav link added; wizard: upload → map →
  preview → confirm, plus a list of past import runs with an undo action.
- `static/i18n/en.json` — new `import.*` keys.
- `tests/backend/test_spreadsheet_import.py`.

## Implementation Phases

### Phase 1 — Backend core
Schema + migration, `core/spreadsheet_import.py` parsing/matching/commit/undo logic, config key.
Unit-level tests against the core module directly (no HTTP layer yet).

### Phase 2 — API
`api/routers/imports.py`'s five endpoints (`columns`, `preview`, `commit`, list, undo), wired to
`main.py`. HTTP-level tests: owner scoping (404 not 403), validation errors, the full
upload → preview → commit → undo round trip for both `.xlsx` and `.csv`, re-upload idempotency.

### Phase 3 — Frontend
`/import` page: 4-step wizard + past-runs/undo list. i18n keys. Live-verified via `curl` against
a local dev boot (throwaway account) since the Chrome extension has been unavailable all recent
sessions — flag for real browser confirmation next time it connects, same as `v0.9.7`.

### Phase 4 — Docs
`architecture.md` (new table, new endpoints), `features.md` (new milestone entry), `README.md`,
`pyproject.toml` version bump.

## Dependencies
None new. `openpyxl` (existing) for `.xlsx`; stdlib `csv` for `.csv`.

## Risk & Mitigations
- **A pilot's spreadsheet has an unparseable date format** → reported per-row (FR-012), never
  guessed; the pilot fixes and re-runs (idempotent, so already-imported rows aren't duplicated).
- **Undo after partial edits** → per-row/per-reference safety check above; nothing silently lost,
  nothing silently force-deleted out from under a later edit.
- **Large file** → `max_import_bytes` size cap, same shape as `max_igc_bytes`.
