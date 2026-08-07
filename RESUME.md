# Resume Notes — 2026-08-07

## In Progress

Nothing blocking. v0.2 (core data + Excel import) is implemented and tested — 120 tests passing,
`ruff check`/`ruff format --check` clean, version bumped to `0.2.0`, tagged `v0.2.0` and pushed.
Live-boot verification against a real `config.yml` (the way v0.1's release note describes) is happening
on the homelab host directly — that host's compose/deploy config lives in a separate repo, not here.

## Next Step

Once the host confirms `v0.2.0` boots cleanly and the importer works end-to-end against a real
`config.yml`, start v0.3 — flight log UI (the MVP boundary). Read `.ai/context/features.md` → "v0.3"
for scope.

## Open Questions

None blocking. Two things flagged for later, already in the backlog in `features.md`:
- Grant the deploy `gh` token `read:packages` so published image tags can be verified directly.
- Re-run the `python:3.14-slim` multi-arch build gate once `libigc` is actually installed (v0.4) —
  v0.1's green build did not include it, so the runtime question is only half-answered.

## Context

- **v0.2's spec/plan/research/data-model live in `specs/001-core-data-import/`.** Read `research.md`
  before touching `core/aliases.py` or `core/importer.py` — every canonical name and alias in there was
  verified byte-for-byte against a direct `openpyxl` read of `olddata/Flugbuch.xlsx`, and that file
  records two of its own transcription typos that were caught and fixed that way (Möntschelenalp with ö
  not ü; Därstetten with ä not ü). Copying a name from a summarized view rather than re-verifying
  against the raw bytes is exactly how those crept in the first time.
- **The 596-vs-600 region-count gap has a confirmed root cause**, not just a confirmed symptom: three
  launch sites were added to the workbook after its initial version; every yearly column's SUM formula
  was updated to include them, but the `Total` column's formula was not. `core/aliases.py`'s
  `SITE_REGION` mapping is reconstructed from the more complete yearly formulas, so it reproduces a
  *different* mismatch than the raw 596-vs-600 gap — see `architecture.md`'s Statistics section and
  `research.md` for the full derivation.
- **An advisor review caught two real defects before they shipped**: `_get_own_glider`'s sample in
  `02-backend-conventions.md` showed a 403 for "not yours," which leaks a row's existence and
  contradicts this project's own testing-conventions coverage table — fixed in the doc and in every
  router. `Flight.import_key`'s uniqueness was scoped globally instead of per-owner, which would have
  broken tenancy the moment a second pilot's import produced the same `"xlsx:5"` — fixed to
  `UniqueConstraint("owner_id", "import_key")`.
- **Real bugs found by testing against a live boot, not just the test suite (v0.1)**:
  `check_db_health()` read stale module state instead of the request's engine; `APP_VERSION` resolved
  to `0.0.0-dev` in the container because `poetry install --no-root` leaves no distribution metadata for
  `importlib.metadata` to find (fixed with a `pyproject.toml` fallback); SQLite returns naive
  datetimes, so raw API responses had no UTC marker (`UtcDateTime` type decorator fixes it for every
  future table, not just `users`). All four are documented with rationale in `context/architecture.md`.
- **The blueprint's `dev-web` category has real defects**, corrected locally and worth fixing upstream
  in `ai-blueprint`: `02-backend-conventions.md` and `04-constraints.md` specify two contradictory
  migration doctrines (`.sql`+`_migrations` vs `_run_column_migrations()`); `06-testing-conventions.md`
  lost all the StaticPool/ASGITransport trap documentation and its one example test uses an httpx API
  removed in 0.28.
- **Dependency freshness was broken twice during v0.1**, both now fixed and the rule widened in
  `02-backend-conventions.md` to explicitly cover four kinds (Python packages, GitHub Actions, vendored
  JS, base images) with a "verify programmatically" instruction: `pytest-asyncio` was reported as
  `0.26.0` when `1.4.0` was current, and every GitHub Action was copied from Lenticularis 1–3 majors
  behind (`actions/checkout@v4` → `@v7`, etc.). `openpyxl`'s pin was re-verified at the start of v0.2
  and is still current (3.1.5).
- **The first tagged release did not dispatch its own publish workflow** — the tag and the workflow
  file arrived in the same push. Documented in `context/architecture.md`; the publish workflow now also
  has `workflow_dispatch` so this doesn't need a tag delete/re-push next time.

This file is a pointer, not a duplicate — `.ai/context/features.md`, `architecture.md` and
`specs/001-core-data-import/` have the detail.
