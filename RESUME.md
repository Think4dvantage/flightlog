# Resume Notes — 2026-08-15

## In Progress

**v0.5 — IGC ingest + analysis is fully implemented on `main` (backend + frontend), tested, committed
and pushed, but not tagged or deployed.** `v0.4.0` (the `/sites` drawer + Leaflet icon-path fix) shipped
and was confirmed live at `fl.sdh.lol` earlier this session — that part of the work is done and closed.
Everything below is new.

**What shipped in this pass**: per-flight IGC upload/replace/detach with eight computed figures
(duration, distance, max altitude, altitude gain, thermal count, best/peak climb, glide ratio); a
Leaflet track map and a Chart.js barogram with thermal/glide phases shown via per-segment line coloring
(no annotation plugin — none is vendored, so the line itself is colored per phase using Chart.js 4's
`segment.borderColor` callback); bulk upload with date+duration auto-matching and a persisted
`igc_pending_uploads` review queue (resolve/dismiss survives a closed tab); automatic site-coordinate
backfill from track data that never overwrites a manual pin; `flights.takeoff_time`/`landing_time`
writeback on attach, cleared on detach; and admin-gated re-analysis (`POST /api/admin/reanalyze`, the
app's first use of `require_admin` anywhere). Four new tables: `igc_tracks`, `igc_segments`,
`site_observations`, `igc_pending_uploads` (the last a plan-level addition, not in the original spec).
17 new backend tests, 144/144 passing project-wide, `ruff check`/`ruff format --check` clean.
`pyproject.toml` bumped `0.4.0` → `0.5.0`.

**Two of `core/igc.py`'s design assumptions were wrong and got corrected against the real installed
`libigc` 1.2.0 package, not shipped as guessed** (`specs/003-igc-ingest-analysis/research.md` has the
full detail): altitude-source selection reads the library's own `flight.alt_source` directly rather
than reimplementing a ">50% non-`None`" heuristic that wouldn't have matched real data anyway (its
`press_alt`/`gnss_alt` fields are always floats, never `None`); and `FlightParsingConfig`'s three real
tunable parameter names (`min_bearing_change_circling`, `min_time_for_bearing_change`,
`min_time_for_thermal`) replaced four differently-named, differently-shaped ones the original design
had guessed before the package was actually inspected.

**Verified live via `curl` against a local dev boot for every endpoint** — not just `pytest` — including
a real fixture's figures cross-checked by hand, and the full bulk-upload → ambiguous → resolve/dismiss
cycle end to end. Two real bugs were caught only because of that live pass, both fixed:
- `auth.js`'s `fetchAuth()` forced `Content-Type: application/json` onto every request with a body,
  including `FormData` — silently breaking multipart file uploads. This is the app's first file-upload
  feature, so nothing had exercised this path before. Fixed: skips that header when the body is
  `FormData`, letting the browser set its own boundary-bearing content type.
- Dismissing a pending upload didn't clear its `UniqueConstraint(owner_id, sha256)` slot, so re-
  uploading that exact file afterward was silently swallowed (matched the stale row, reported
  "already awaiting resolution" even though it wasn't anymore, and the pending list wouldn't show it).
  Fixed: a dismissed/resolved row is reused on re-upload instead of blocking it. Covered by a new
  regression test.
- Also closed while writing up the `sync.md` documentation pass, not found live: `flights.takeoff_time`/
  `landing_time` writeback was speced (`architecture.md`'s "writeback shrinks the problem") but never
  actually wired into `_attach_track`/`delete_igc`. Added, with its own test.

**Not yet done: actual browser rendering.** No browser automation tool was connected this session either
— see [[env-no-browser-extension]]. The map, the barogram's per-segment coloring, every file-input
control, and keyboard navigation are all unconfirmed. This is the same gap `specs/002-flight-log-ui`'s
T047 was left open for, now repeated for a third feature in a row for the same reason.

## Next Step

1. **Get a real browser connected and do the T033-equivalent visual pass** on `/flights/{id}`'s new
   track section and the new `/igc` bulk page — the single biggest open risk right now, since three
   features in a row have shipped without ever being actually seen rendered.
2. **Tag and deploy `v0.5.0`** once the browser pass is done (or the pilot decides to deploy first and
   verify live, matching how `v0.3`/`v0.4.0` actually happened this project). `docker-publish.yml`
   triggers on any `v*` tag push; something outside this repo (Watchtower or similar, never confirmed)
   pulls the new image onto `fl.sdh.lol` automatically within minutes of that.
3. **Watch the first multi-arch build that actually carries the `igc` extra.** `libigc` and its
   transitive `simplekml` dependency were confirmed pure-Python via PyPI metadata before enabling
   `--extras igc` in CI and the Dockerfile (de-risking the QEMU/arm64 concern `features.md`'s backlog
   flagged), but the real multi-arch image build only runs on a tag push — that hasn't happened yet for
   a version carrying this extra. The metadata check is evidence, not proof.
4. **Try some real IGC files.** Every test and live-boot check so far used hand-generated fixtures
   (`tests/backend/fixtures/*.igc`) — realistic enough to exercise the full pipeline (a genuine detected
   thermal, a glide, correct GNSS fallback for a no-baro file), but nobody has run this against an actual
   flight recorder's output yet. Config tuning (`igc.parsing:` in `config.yml`) is very likely to need
   iteration once real tracks are tried — the shipped defaults are `libigc`'s own sailplane-tuned ones,
   and `architecture.md` already flags paraglider thermals as slower and sloppier than that.
5. **Decide on Phases 9–11** (`/contacts`, CSV export, remember-last-filters, from `specs/002-flight-log-ui`)
   — still open, not tied to any particular tag.
6. **v0.6 — secondary sheets + XContest is next** on the roadmap after this ships, per `features.md`.

## Open Questions

- Whether Phases 9–11 ship before or alongside `v0.6` — see step 5 above.
- `features.md`'s backlog, unchanged this session: grant the deploy `gh` token `read:packages`, the
  `bootstrap_admin_email`/`bootstrap_admin_password` `set=%s`-style logging gap.

## Context

- **v0.5's spec/plan/research/data-model/contracts/tasks live in `specs/003-igc-ingest-analysis/`** —
  `tasks.md` has the precise, checked-off task-by-task record of what shipped and what (T033 — the
  browser pass) is still open.
- **The dev server needs a restart after every backend edit** (no `--reload`) — hit this repeatedly
  this session (the new `/igc` page 404'd until the server was restarted after adding its route to
  `pages.py`). See [[flightlog-dev-server-workflow]].
- **This is the app's first file-upload feature and first multipart endpoint anywhere** — the
  `fetchAuth()` bug above is exactly the kind of gap that only shows up the first time a new HTTP
  pattern gets used for real; worth remembering if the next feature introduces another new pattern.
- **`igc_pending_uploads` rows are never hard-deleted** — dismiss and resolve both just set
  `resolved_at`; the row (and its stored file) stays as a record of what happened to that upload,
  mirroring how `flights.import_key` rows from the historical import are never deleted either.

This file is a pointer, not a duplicate — `.ai/context/features.md`, `architecture.md` and
`specs/003-igc-ingest-analysis/` have the detail.
