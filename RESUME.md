# Resume Notes — 2026-08-07

## In Progress

**The real workbook import has now been run against the live container — 600 flights are confirmed
landed in production.** `python -m flightlog.core.importer` (dry-run, then `--write`) was exercised via
`docker cp` + `docker exec` (never direct SSH/`docker-compose` on the host — see `04-constraints.md`).
The dry-run report matched every documented finding exactly: 600/600 rows resolved, the three region
mismatches (Interlaken/Grindelwald higher, `Fiesch`/`Fiescheralp` unmapped), the row-387 Altgain
mismatch, the `Advance Success 2` unresolved harness, and 7 buddy-name proposals. `--write` then
committed all 600.

**That write surfaced a real bug, now fixed on `main` (commits `7345d28`, `e4ae0b8`), not yet
redeployed:** `database/db.py`'s `_seed_regions()` still had `"Dürstetten"` (ü) — the exact transcription
typo `aliases.py`'s `SITE_REGION` had already been corrected away from, to `"Därstetten"` (ä). The
spelling mismatch meant the importer's `_get_or_create_region` couldn't match the seeded row by name, so
it silently created a 13th, duplicate region on the write. Fixed in `db.py`, and a regression test
(`test_real_workbook_import_creates_no_new_regions`, asserting `regions_written == 0` against the real
workbook) was added since nothing previously pinned seed-spelling-vs-alias-spelling agreement. 121 tests
passing, `ruff check` clean, `ruff format --check` clean on everything touched (5 pre-existing unrelated
`.ai/*.md` doc-fence formatting issues remain, not touched by this fix). `poetry.lock` was also committed
for the first time — it was documented as committed in `01-project-overview.md` but never actually was.

**Not yet done: the orphan `"Dürstetten"` (ü) region row still exists in the live prod DB** — the code
fix doesn't retroactively clean it up, and the fixed image hasn't been rebuilt/redeployed yet. Two
commands are ready and were handed to the user (check row has 0 sites attached, then delete it) but
execution and confirmation are still pending as of this note.

v0.2.0 is deployed and confirmed live at `fl.sdh.lol` — login works, the typed error envelope is
confirmed working over real HTTP (`/stats` correctly 404s as `ENTITY_NOT_FOUND`, since neither the page
nor `/api/stats` exist before v0.6). Tagged `v0.2.0` on commit `15dcb0a`, both CI workflows green as of
that tag (not yet re-run against the two new commits above).

A post-deploy login issue (bootstrap admin password not working) was hit and resolved on the host side;
the exact root cause among the three candidates below wasn't confirmed back to this session, so it's
recorded as a set of possibilities rather than a single diagnosis:
1. Secret delivered as a container env var instead of templated into `config.yml` (the app only reads
   `config.yml` + `CONFIG_PATH`, never other env vars) — seeder would log "not configured, skipping".
2. A stale user row in a persisted volume blocking the one-shot seeder — seeder would log "users already
   exist, skipping".
3. A trailing newline from the GitHub Actions secret baked into the hashed password — seeder would log
   "Bootstrap admin created: ...", but login would still fail.

Whichever it was, `config.py`'s `log_effective_config()` doesn't log `bootstrap_admin_email` or whether
`bootstrap_admin_password` is set, unlike `jwt_secret`'s `set=%s` pattern — noted in `features.md`'s
backlog as a small operability gap that would make this faster to diagnose next time.

**The tag was moved once.** The first `v0.2.0` push (`a6dee4c`) had a real gap: `poetry install --with
dev` in CI and `--only main` in the Dockerfile both skip optional-dependency extras, so `openpyxl` was
missing from both the CI test environment and the shipped container image — `python -m
flightlog.core.importer` would have crashed inside it. Local testing hadn't caught this because the dev
sandbox already had `openpyxl` installed outside Poetry, masking the gap. Fixed by adding `--extras
importer` to both, and the `v0.2.0` tag was deleted and recreated against the fix commit rather than
shipping a known-broken tag — safe only because it was minutes old and not yet pulled by anything.

## Next Step

Still open, in order:
1. User runs the two `docker exec` commands already handed to them to check-then-delete the orphan
   `"Dürstetten"` region row from the live DB.
2. Rebuild and redeploy the image (commits `7345d28`, `e4ae0b8` are on `main` but not yet released) so a
   fresh volume never reseeds the wrong spelling again. No version bump was made — backend-only fix, not
   a static-asset change — so this can ship as a `docker-publish.yml` `workflow_dispatch` run against
   `main`, or wait and fold into whatever ships v0.3, whichever the user prefers.
3. Once both are done, start v0.3 — flight log UI (the MVP boundary). Read `.ai/context/features.md` →
   "v0.3" for scope.

## Open Questions

None blocking. Three things flagged for later, already in the backlog in `features.md`:
- Grant the deploy `gh` token `read:packages` so published image tags can be verified directly.
- Re-run the `python:3.14-slim` multi-arch build gate once `libigc` is actually installed (v0.4) —
  v0.1's green build did not include it, so the runtime question is only half-answered.
- Whether to add a startup-time or test-time cross-check that every name `SITE_REGION` (or any future
  alias table) can produce is actually present in its corresponding seed list — the `Dürstetten`/
  `Därstetten` bug was only caught because this session happened to inspect `regions_written` by hand;
  the existing test suite had no assertion that would have failed on it.

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
- **A dependency being pinned correctly is not the same as it being installed where it's needed.**
  `openpyxl` was correctly declared as the `importer` extra in `pyproject.toml`, but neither
  `.github/workflows/test.yml` (`poetry install --with dev`) nor the `Dockerfile` (`poetry install
  --only main`) actually installed it — both need `--extras importer` explicitly, since Poetry doesn't
  pull optional extras in by default. A local sandbox that happened to have `openpyxl` installed outside
  Poetry masked this until the real CI run failed on a clean checkout, by which point `v0.2.0` had
  already been tagged and its container image already published, broken. Caught and fixed within the
  same session before anyone pulled the image — see the tag-move note above. Lesson: a new optional
  extra needs its install command checked in every place code actually runs (CI, Dockerfile, dev
  setup instructions), not just declared in `pyproject.toml`.
- **The first tagged release did not dispatch its own publish workflow** — the tag and the workflow
  file arrived in the same push. Documented in `context/architecture.md`; the publish workflow now also
  has `workflow_dispatch` so this doesn't need a tag delete/re-push next time.

This file is a pointer, not a duplicate — `.ai/context/features.md`, `architecture.md` and
`specs/001-core-data-import/` have the detail.
