# Resume Notes — 2026-08-15

## In Progress

**v0.6.0 (secondary sheets + goals) is implemented, tested, verified in a real browser, committed, and
pushed — but not yet tagged or deployed.** `v0.5.0` remains shipped and confirmed live from earlier this
session. Everything below is new: overnight, `v0.6` through `v0.9` were fully planned (spec → research →
data-model → contracts → plan → tasks, in `specs/004`–`specs/007`); this pass then implemented v0.6's
Phases 1–4.

**What shipped**: `core/secondary_import.py` imports `Fitnessprogramm` (hikes), `Groundhandling`,
`Tandemflüge` (tandem flights), and `Ziele` (goals) — idempotent, `import_key`-guarded, mirroring
`core/importer.py`'s existing shape exactly. Four new tables. Hikes link to a `Hike&Fly` flight only on
an unambiguous same-date match (never guessed — same principle as the IGC bulk-match). Three read-only
list pages (`/hikes`, `/groundhandling`, `/tandem-flights`) plus one fully editable page (`/goals`, full
CRUD + mark-done, imported from `Ziele`). 13 new backend tests, 157/157 passing project-wide, `ruff`
clean. `pyproject.toml` bumped `0.5.0` → `0.6.0`.

**Verified against the real workbook, not just non-crashing**: exactly 85 hikes / 9 ground-handling
sessions / 17 tandem flights / 11 goals, matching the counts confirmed at planning time. 35 of 85 hikes
correctly linked — spot-checked (both via a script and by clicking through in a real browser) that a
linked hike's destination place matches its flight's launch site and date, not just "some" flight.
Idempotent on a second run (0 written, all skipped). Also verified live against the real dev database
(603 real flights) via the CLI entry point and `curl` against every endpoint.

**Claude in Chrome connected successfully for the first time all session** — every prior feature
(`specs/002-flight-log-ui`, `v0.4.0`'s icon fix, `specs/003-igc-ingest-analysis`) had shipped without
this and only got real-browser confirmation later or via the pilot's own manual testing. This time: all
four new pages (Hikes, Groundhandling, Tandem flights, Goals) confirmed rendering correctly with real
data via actual screenshots, plus the Goals add/edit drawer exercised interactively (create → edit-drawer
pre-fill → mark-done → delete). One screenshot-capture timeout occurred partway through (CDP's
`Page.captureScreenshot` hung on the tab after clicking "Mark done") — confirmed via direct API calls
that the mark-done and subsequent delete had both already succeeded server-side before the timeout, so
this was a transient extension/tab glitch, not an application bug. The tab was closed cleanly rather than
force-retried, per the browser-automation guidance against looping on a failing tool.

**XContest score import (v0.6's Phase 5) remains deferred** — confirmed with the pilot at implementation
kickoff that no real "My Flights" export sample was available; `flights.xc_official_score`/`_type`/
`_url` stay unpopulated until one exists. This is the one piece keeping `Flugbuch.xlsx` from being fully
retired.

**Three roadmap corrections were made to `features.md` overnight, during planning** (not code changes):
v0.6 now explicitly owns the `/goals` page (v0.7's original wording had listed it too); v0.9's entry had
two already-shipped items (buddy invite/accept, the `allow_self_registration` flag) removed from its
description, replaced with the real remaining gap (self-registration seeding).

## Next Step

1. **Tag and deploy `v0.6.0`** (or wait for a real XContest sample first and ship both together as a
   slightly later tag — pilot's call; nothing about the shipped subset depends on XContest existing).
2. **Get a real XContest "My Flights" export sample** to unblock v0.6's Phase 5 — the only remaining
   piece of this milestone. `specs/004-secondary-sheets-xcontest/research.md` has the exact resolution
   plan once a sample exists.
3. **v0.7 (statistics) is fully planned and ready to implement next** (`specs/005-statistics/`), once
   v0.6 is settled — or `v0.8`/`v0.9` if there's a reason to prioritize differently; nothing forces
   strict roadmap order at the code level (see each plan's own dependency diagram).
4. **Config tuning on `v0.5`'s IGC parsing may still need iteration** — the shipped `igc.parsing:`
   defaults are `libigc`'s own sailplane-tuned values; still unconfirmed whether the pilot's real
   thermal/glide figures looked right against what they remember of those flights.
5. **Decide on `specs/002-flight-log-ui`'s Phases 9–11** (`/contacts`, CSV export, remember-last-filters)
   — still open, not tied to any particular tag.

## Open Questions

- Whether to tag `v0.6.0` now or wait for XContest — see step 1 above.
- Which of `v0.7`/`v0.8`/`v0.9` to implement next once v0.6 is settled — see step 3 above.
- `features.md`'s backlog, unchanged this session: grant the deploy `gh` token `read:packages`, the
  `bootstrap_admin_email`/`bootstrap_admin_password` `set=%s`-style logging gap.

## Context

- **`specs/004-secondary-sheets-xcontest/` through `specs/007-sharing-public-readiness/`** each hold a
  complete spec/research/data-model/contracts/plan/tasks set for `v0.6`–`v0.9`. `specs/004`'s `tasks.md`
  is checked off through Phase 4 (T001–T017, T025–T030); Phase 5 (T018–T024) is explicitly marked
  deferred, not forgotten.
- **A running theme worth remembering for whichever milestone comes next**: this session repeatedly
  found that an existing doc or an old spec's prose had drifted from reality — stale roadmap version
  numbers, `01-project-overview.md`/`02-backend-conventions.md` describing code that doesn't exist yet,
  unread sheets, a third-party repo solving a different problem than expected. Verify against the real
  source (code, real files, real PyPI/GitHub metadata, an actually-booted dev server) before designing
  on top of any existing doc's claims — including this file's own claims, once enough time has passed.
- **`v0.5`'s own spec/tasks live in `specs/003-igc-ingest-analysis/`**, 35/35 checked off — no longer
  active work, kept for reference.
- **The dev server needs a restart after every backend edit** (no `--reload`). See
  [[flightlog-dev-server-workflow]].
- **The Windows-only WAL gotcha**: `data/flightlog.db`'s main file is often stale on its own — real,
  current data lives in the accompanying `.db-wal`/`.db-shm` sidecar files until SQLite checkpoints them.
  Copying just the `.db` file (as a first attempt this session did) silently produces an
  apparently-empty database. Copy all three together, or better, just point directly at the real path.

This file is a pointer, not a duplicate — `.ai/context/features.md`, `architecture.md`, and each
feature's own `specs/` folder have the detail.
