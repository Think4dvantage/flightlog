# Resume Notes — 2026-08-15

## In Progress

**v0.7 (statistics) is implemented, tested, verified live via `curl` and a real connected browser,
but not yet committed, tagged, or deployed.** `v0.6.0` remains the last tagged release (still itself
awaiting its own tag/deploy per the previous session's notes below — check `git status`/`git tag` before
assuming which of v0.6/v0.7 is actually live in any given environment).

**What shipped**: `core/stats.py` — every `/api/stats` aggregate, computed read-time with no new tables.
One batched load per call (`_load_owner_data`) fetches the owner's flights plus every reference row
needed to resolve them (sites, `user_site_prefs`, categories, gliders, harnesses, regions,
`flight_buddies`), then every figure is pure Python over that in-memory set — deliberately not reusing
`core/flights.py`'s per-flight `compute_altitude_figures()`, which would be the exact N+1
`04-constraints.md` warns against. Only the cumulative thermal-climb rollup stays a genuine SQL aggregate
(`SUM(igc_segments.alt_change_m) WHERE kind='thermal'`). `api/routers/stats.py`'s 8 `GET` endpoints
(`totals`, `time-breakdown`, `distribution`, `personal-bests`, `matrix/{dimension}`, `launch-technique`,
`igc-rollup`, `progression`) are thin wrappers; `matrix/{dimension}` validates against a plain allowlist
(never `Literal[...]`) so an unknown dimension 404s instead of FastAPI's own 422. One new page,
`/stats` (`static/stats.html`/`stats.js`), fetches all 8 sections independently so the page renders
incrementally. `pyproject.toml` bumped `0.6.0` → `0.7.0`.

**Tests**: 23 new (180/180 passing project-wide) — a pure-logic set duck-typing flights with
`SimpleNamespace` (matching `06-testing-conventions.md`'s own pinned `launch_technique_split` example, so
no DB is needed for `launch_technique_split`/`hike_fly_total`/`current_streak`/`ytd_pace`/
`cumulative_progression`), plus API tests against a small hand-built fixture (not the real workbook) that
specifically covers a personal-best tie, a flight missing glider/harness/landing site (the "not recorded"
matrix bucket), zero-track and zero-then-populated-buddy states, and the 404-not-422 dimension check.
`ruff check`/`ruff format --check` clean.

**Verified live, not just non-crashing.** Booted the real dev server (`config.yml` +
`data/flightlog.db`, 603 real flights) and hit every one of the 8 endpoints via `curl`/`urllib`, then —
**Claude in Chrome connected successfully again this session** — logged in through a real tab (token
injected into `localStorage` via `javascript_tool` rather than driving the login form, since the point was
verifying `/stats`, not re-verifying `/login`), navigated to `/stats`, and scrolled the entire page:
totals, both bar charts, the year×month table, all three distribution charts, all 8 personal bests, every
one of the 6 matrix tabs (including clicking "By buddy" to confirm its sparse-state hint and empty-state
copy render instead of a bare zero), launch technique, the IGC rollup, and the momentum/progression
section including its cumulative-flights line chart — zero console errors throughout, console logging
followed the `[FL:stats]` convention with URL/status/elapsed-ms on every fetch. Clicked a "View flight"
link from `longest_airtime` and confirmed it navigated to the correct flight detail page (3h30min /
3645m, matching the number shown on `/stats`).

**Three of the four confirmed workbook disagreements were re-confirmed against live numbers**, not just
asserted in tests: reverse-launch share is 209/603 ≈ 34.66% (denominator now 603, not the original 600 —
the reverse count itself, 209, is unchanged, which is exactly the "live, not frozen" behavior FR-001
requires, not a bug); `total_alt_gain_m` (60841) differs from the workbook's own reference Total Altgain
(61191) by exactly 350 — the already-known row-387 correction baked in automatically since totals sum the
app's own computed `alt_gain_m`, never the stored column, with no unexplained residual; and the buddy year
matrix returned empty (`rows: []`), confirming zero `flight_buddies` rows exist yet in the real dev
database — the "legitimately sparse" state the spec predicted. See `architecture.md`'s Statistics section
for the fourth (the `Buddys`-tally name/count mismatch, discovered during this feature's planning) and the
full detail on all four.

**Not yet done**: `git add`/commit, a version tag, and deployment. `specs/005-statistics/tasks.md`'s T022
(this doc-sync pass) is now done; re-check that file's checkboxes before considering v0.7 fully closed.

## Next Step

1. **Commit and decide on tagging v0.7** — check with the pilot before tagging/pushing, per this
   project's own "confirm before push" norm; nothing here was pushed automatically.
2. **v0.8 (public API + VidFactory) or v0.9 (sharing) are both fully planned** (`specs/006-public-api-
   vidfactory/`, `specs/007-sharing-public-readiness/`) and ready to implement next, in either order — no
   code-level dependency forces one before the other.
3. **XContest score import remains a backlog item**, not a blocking dependency of anything — see
   `features.md`'s Backlog entry. Pick it up only if/when a real "My Flights" export sample turns up.
4. **Config tuning on `v0.5`'s IGC parsing may still need iteration** — still unconfirmed whether the
   pilot's real thermal/glide figures looked right against what they remember of those flights.
5. **Decide on `specs/002-flight-log-ui`'s Phases 9–11** (`/contacts`, CSV export, remember-last-filters)
   — still open, not tied to any particular tag.

## Open Questions

- None blocking v0.8/v0.9 — both are ready to implement as planned, in either order.
- Whether `v0.6.0` itself still needs tagging/deploying before v0.7 does, or whether they ship together —
  check `git tag`/the deploy pipeline's actual state rather than assuming from this file alone.
- `features.md`'s backlog, unchanged this session: grant the deploy `gh` token `read:packages`, the
  `bootstrap_admin_email`/`bootstrap_admin_password` `set=%s`-style logging gap.

## Context

- **`specs/005-statistics/`** holds the complete spec/research/data-model/contracts/plan/tasks set for
  v0.7, now implemented — `tasks.md`'s checkboxes should be marked off to match (not yet done as of this
  note; do that before considering the milestone fully closed).
- **`specs/006-public-api-vidfactory/` and `specs/007-sharing-public-readiness/`** hold complete spec sets
  for v0.8/v0.9 — ready whenever picked up.
- **A running theme worth remembering for whichever milestone comes next**: prior sessions repeatedly
  found that an existing doc or an old spec's prose had drifted from reality. Verify against the real
  source (code, real files, an actually-booted dev server) before designing on top of any existing doc's
  claims — including this file's own claims, once enough time has passed.
- **The dev server needs a restart after every backend edit** (no `--reload`). See
  [[flightlog-dev-server-workflow]].
- **`importlib.metadata.version("flightlog")` caches the version at install time** — after bumping
  `pyproject.toml`, `poetry install` (no args needed, it's already in the lockfile) must re-run before
  `APP_VERSION`/the static-asset cache-busting reflects the new version; otherwise `test_app_version_
  matches_pyproject` fails even though the edit is correct. Caught and fixed this session.
- **The Windows-only WAL gotcha**: `data/flightlog.db`'s main file is often stale on its own — real,
  current data lives in the accompanying `.db-wal`/`.db-shm` sidecar files until SQLite checkpoints them.
  Copy all three together, or better, just point directly at the real path.

This file is a pointer, not a duplicate — `.ai/context/features.md`, `architecture.md`, and each
feature's own `specs/` folder have the detail.
