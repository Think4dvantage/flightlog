# Resume Notes — 2026-08-21

## In Progress

Nothing in flight. `v0.9.11` — the latest tag — is committed and pushed to `origin/main`.

## Recently shipped

- **`v0.9.9`** — one-line `/sites` bugfix: a Leaflet marker-creation path passed an explicit
  `icon: undefined` for launch sites instead of falling back to the default pin, crashing the
  page's own render loop before the table ever painted. Diagnosed from the pilot's own pasted
  browser console trace against `fl.lenti.cloud`.
- **`v0.9.11`** — two pilot-requested features shipped together as one release (no separate
  `0.9.10` tag, per the pilot's explicit request):
  - **Combined airtime per calendar month** on `/stats` and `/public/stats/{id}` — a stacked
    bar chart where each bar is built from its own contributing flights (a hairline seam
    between segments so many-short-flights vs. few-long-flights months look visibly
    different), with a total-duration label above each bar.
  - **IGC altitude calibration to a known launch elevation** — `core/igc.py::
    calibrate_altitude()` anchors a *barometric*-sourced track's absolute altitude
    (`max_alt_igc_m`, takeoff/landing fixes, the map/barogram's altitude column) to the
    launch site's own known elevation, fixing a QNH/altitude-reference miscalibration that
    otherwise still passes `libigc`'s own per-fix validity check. Deliberately left alone for
    GNSS-sourced tracks (per-fix noise, not a constant bias) and for every difference-based
    figure (`alt_gain_igc_m`, climb rates, glide ratio — a constant shift cancels out of a
    difference by construction). `ANALYZER_VERSION` bumped `"1"` → `"2"` so `POST
    /api/admin/reanalyze` recalibrates every already-uploaded track.

Full detail on both, plus every earlier release back through v0.1, lives in
`.ai/context/features.md` — this file is a pointer, not a duplicate.

## Next steps / open backlog

- **Prod (`fl.lenti.cloud`) is still on `v0.9.7`** — three releases behind. Once the `v0.9.11`
  image is deployed there, run `POST /api/admin/reanalyze` (admin-only) to actually recalibrate
  the pilot's own 23.07.2026 flight and any other barometric tracks — that's the step this
  session's live verification (against a throwaway account and a test fixture, not against real
  prod data) couldn't reach.
- **No visual/browser confirmation** of any UI shipped since `v0.9.4` — the Chrome extension has
  not connected in any recent session. Every one of these has instead been verified via `curl`
  against a live dev boot plus programmatic DOM-id/`data-i18n` cross-checks. First thing to do
  the moment the extension connects: open `/sites`, `/stats`, `/public/stats/{id}`, and a flight
  with an attached IGC track, and just look at them.
- Carried forward, unchanged for several sessions:
  - Confirm whether Traefik replaces or appends to `X-Forwarded-For` (affects the public
    rate-limiter's per-visitor bucketing).
  - Repo visibility is still private — pilot's call; the `Flugbuch.xlsx` git-history scrub is
    done and stable.
  - `C:\git\flightlog-pre-scrub-backup\` can be deleted once that scrub is confirmed stable.
  - XContest score import, and `specs/002-flight-log-ui`'s Phases 10–11 (CSV export,
    remember-last-filters), remain open backlog items — see `features.md`'s Backlog section.
  - `sites.elevation_igc_m` is declared in the schema and exposed on `SiteOut` but has no
    writer anywhere (found while building `v0.9.11`, corrected in `architecture.md` as doc
    drift) — a real, un-scoped gap if that comparison is ever wanted.

## Context — lessons worth keeping

- The dev server needs a restart after every backend edit (no `--reload`) — see
  [[flightlog_dev_server_workflow]]. Static-file-only changes (`static/*.js`, `*.html`) are live
  immediately, no restart needed.
- **`igc_tracks.alt_source` is `"PRESS"` / `"GNSS"`** (libigc's `AltitudeSource` `StrEnum`
  values) — not `"PRESSURE"`. Confirmed by reading the installed `libigc` source directly, not
  guessed; any new code gating on this value must match the literal, not the enum member name.
- **`core/igc.py::calibrate_altitude()` must run on the *raw* analysis before `site_backfill.
  record_observations()`** — that function feeds `site_observations.alt_m`, and calibrating
  first would make any future `sites.elevation_igc_m` comparison tautological. This ordering bug
  was caught by an advisor review before shipping, not found the hard way afterward.
- **`igc_tracks.sha256` is unique per owner, not per flight** (the `v0.9.7` lesson) —
  `import_runs`' own idempotency deliberately reuses a *different* existing mechanism
  (`flights.import_key`), not this one; don't conflate the two content-addressing schemes.
- **A `hidden` (or `display:none`) ancestor hides descendants regardless of their own `hidden`
  state** (`v0.9.7`) — check for this whenever a new show/hide panel nests inside another one.
- **Never fuzzy-match reference data** — every importer (`core/importer.py`,
  `core/spreadsheet_import.py`) does exact-string matching only, a lesson `v0.8.1`'s bulk-IGC-
  matcher removal already paid for once.
- **Live-verification pattern**: for backend changes, a pytest suite plus a real dev-server boot
  with a throwaway account/site/flight, cleaned up afterward via the API (or a direct DB script
  when no API path exists, e.g. deleting a throwaway user); for frontend-only changes or when the
  Chrome extension is down, `curl` the served markup and cross-check DOM ids / `data-i18n` keys
  programmatically.
- **Windows/Git Bash path gotcha**: this repo is worked on from a Windows machine via a Bash
  tool. `/tmp/...` paths written by `curl`/bash are not visible to a Windows-native `python`
  invocation (different path-root translation) — use the actual scratchpad directory (an
  absolute Windows path) for any file a Python script also needs to read.
- **Prod is `fl.lenti.cloud` / `flightlog.lenti.cloud`** — see [[flightlog_prod_oidc_layer]] and
  `architecture.md`'s Deployment section. Never touched directly (no SSH/`docker-compose`); the
  pilot deploys and runs any prod-side one-shot command themselves.
