# Resume Notes — 2026-08-16

## In Progress

**Nothing in progress — `v0.7.5` is implemented, tested, live-verified, committed, tagged, and pushed
this session, closing out a live pilot-feedback pass against the deployed `fl.sdh.lol` instance.**
`v0.7.0`–`v0.7.4` were already tagged/deployed from earlier in this session; `v0.7.5` continues straight
on from there with the pilot's explicit go-ahead to decide any open design questions and ship
autonomously (given at the point they went to sleep mid-session).

### What shipped in `v0.7.5`

The pilot reviewed the live `fl.sdh.lol` deployment and reported four real gaps plus one bug report
(the bug turned out to be infrastructure, not app code — see below). All four gaps are fixed:

1. **`/contacts` — full buddy CRUD.** Backend (`/api/buddies`) already had complete CRUD +
   link/accept/decline since v0.2 (Phase 9 of `specs/002-flight-log-ui` spec'd this page since v0.3); it
   was simply never built. This was also the actual root cause of "I can't tag buddies on flights" — the
   flight drawer's buddy multi-select was always empty because nothing could create a buddy. Verified
   live end-to-end: created a contact named "Tom," tagged it on a real flight via the existing flights
   drawer, confirmed the contact's flight-count went 0→1 on `/contacts`. Both test records deleted after.
2. **Full CRUD for hikes, groundhandling sessions, and tandem flights.** All three were deliberately
   "import-and-view only" since v0.6 — reasonable until a pilot with a newborn on the way and less flying
   time wants to log a ground-handling session or a solo hike going forward, with no way to. New
   `HikeCreate`/`HikeUpdate`/`GroundhandlingSessionCreate`/`Update`/`TandemFlightCreate`/`Update` schemas,
   `POST`/`PUT`/`DELETE` added to all three routers, matching `goals.py`'s existing CRUD pattern exactly
   (including `import_key` staying server-only). `HikeCreate`/`Update` additionally accept an optional
   `flight_id` so a pilot can link/unlink a hike to a flight by hand — never ownership-validated, matching
   how `flights.py` already treats other cross-referenced ids (`launch_site_id`, `category_id`). New
   `tests/backend/test_secondary_crud.py`, 8 tests, all three entities × create/get/update/delete +
   ownership-scoping (404-not-403). Verified live: added a groundhandling session (9→10), edited a hike
   (confirmed the flight-link dropdown pre-selects the real linked flight), added a tandem flight
   (17→18) — all three deleted after.
3. **"Import findings" page removed.** Pilot's own words: "outdated and not needed." Nav link and
   `/import` route deleted, `static/import.html`/`import.js` deleted. `/api/import-report` and
   `core/import_history.py`'s frozen snapshot are deliberately untouched — kept in case the historical
   record is ever wanted again, just no longer surfaced in the UI. Confirmed `GET /import` now 404s
   cleanly.
4. **"Cumulative flights over time" chart replaced.** Pilot's own words: "just a straight line from
   bottom left to top right — has no use at all," and they're right — a running total by date is
   monotonically increasing by construction, so it could never show a slowdown or a comeback. Replaced
   with "Monthly pace, by year" — one line per year across Jan–Dec, built entirely client-side from
   `time-breakdown`'s already-fetched `year_month_matrix` (no new backend call). `ProgressionOut.
   cumulative_series`, `ProgressionPoint`, and `core/stats.py`'s `cumulative_progression()` were deleted
   outright, not left as dead code. Verified live: the new chart renders 9 distinctly-colored year lines
   with a bottom legend, showing real month-to-month variation per year — including the daughter-related
   2024+ slowdown as an honest dip rather than an invisible non-event.

### The "Add goal doesn't work" report — investigated, root-caused, deliberately not touched

Tested locally against the exact `v0.7.4` build running in prod: worked perfectly, clean `201` on create.
Traced the real cause via `ssh sdh` (the pilot's own offer): `fl.sdh.lol` sits behind a Traefik
`traefik-oidc-auth` (Pocket-ID) middleware protecting the **entire host**, layered on top of flightlog's
own independent JWT login. Confirmed by hitting the live site unauthenticated from outside the network —
got a 401 in that proxy's own RFC9110-style error shape, and the flightlog container's own logs show zero
trace of that request ever arriving. Two independent session lifetimes stacked on one host is almost
certainly why writes (POST) silently fail for the pilot while reads (page loads, GETs) keep working.
**Deliberately not touched**: this is shared infrastructure fronting other public services on the same
host, the config file has live credentials in it, and the pilot chose to self-test (re-login to the SSO,
retry) before deciding whether an actual config change is warranted. See Open Questions below.

### Tests, lint, verification

190/190 passing project-wide (24 new: 8 in `test_secondary_crud.py`, plus `test_stats.py` updates for
the removed `cumulative_series` field). `ruff check`/`ruff format --check` clean. Every change verified
in a real connected browser against the local dev server (Claude in Chrome connected successfully again
this session) — screenshots plus direct `javascript_tool`/console introspection where CDP screenshot
capture hit its now-familiar transient flakiness. `pyproject.toml` bumped `0.7.4` → `0.7.5`.

### Committed, tagged, pushed

The pilot explicitly authorized finishing autonomously (deciding any open design questions themselves)
and shipping via commit/tag/push before going to sleep mid-session — done. `v0.7.5` is live in the
`docker-publish.yml` pipeline same as every prior tag.

## Next Step

1. **Confirm with the pilot whether re-logging into the SSO fixed "Add goal"** on `fl.sdh.lol` — they
   were going to self-test this. If it didn't help, the next step is proposing an actual `traefik-
   oidc-auth` config change (e.g., excluding API POST/PUT/DELETE paths from the OIDC session requirement,
   or extending its session lifetime) — get explicit sign-off before touching shared infra with live
   credentials in it.
2. **v0.8 (public API + VidFactory) or v0.9 (sharing) are both fully planned** (`specs/006-public-api-
   vidfactory/`, `specs/007-sharing-public-readiness/`) and ready to implement next, in either order.
3. **XContest score import remains a backlog item** — see `features.md`'s Backlog entry.
4. **Config tuning on `v0.5`'s IGC parsing may still need iteration** — still unconfirmed whether the
   pilot's real thermal/glide figures looked right against what they remember of those flights.
5. **Decide on `specs/002-flight-log-ui`'s Phases 10-11** (CSV export, remember-last-filters) — Phase 9
   (contacts) is now done; these two remain open, not tied to any particular tag.

## Open Questions

- Whether the OIDC/Traefik layer in front of `fl.sdh.lol` needs an actual config change, or whether
  re-authenticating to the SSO resolves the write-failure symptom on its own — pilot is self-testing.
- None blocking v0.8/v0.9 — both are ready to implement as planned, in either order.
- `features.md`'s backlog, unchanged this session: grant the deploy `gh` token `read:packages`, the
  `bootstrap_admin_email`/`bootstrap_admin_password` `set=%s`-style logging gap.

## Context

- **`specs/002-flight-log-ui/tasks.md`'s Phase 9 (contacts)** is now implemented — its own checkboxes
  aren't marked (implemented directly from live pilot feedback, not by walking that task list), but the
  delivered scope matches what T037–T041 originally specified.
- **`specs/005-statistics/`** holds the complete spec/research/data-model/contracts/plan/tasks set for
  the original v0.7 scope. Every post-ship enhancement since (v0.7.1 through v0.7.5) was implemented
  directly from pilot chat feedback, not through new spec cycles — deliberately, given their size; if
  `/stats` or the secondary-sheet pages keep growing like this, a lightweight addendum spec might be worth
  writing rather than continuing to fold everything into `architecture.md`/`features.md` prose only.
- **`specs/006-public-api-vidfactory/` and `specs/007-sharing-public-readiness/`** hold complete spec sets
  for v0.8/v0.9 — ready whenever picked up.
- **This session's SSH access to the prod host (`ssh sdh`) was pilot-offered**, used only for read-only
  diagnosis (docker logs/inspect, reading — never editing — the Traefik dynamic config). No config was
  changed, no container was restarted, no secret was echoed back to the pilot in chat.
- **A running theme worth remembering for whichever milestone comes next**: prior sessions repeatedly
  found that an existing doc or an old spec's prose had drifted from reality — this session's "Add goal"
  investigation is the sharpest example yet: the app-level bug report was real (writes fail) but the root
  cause was one layer below the application entirely. When a pilot reports something "not working" on a
  live deployment, reproduce against the exact same build locally before assuming the app code is at
  fault — it wasn't, here.
- **The dev server needs a restart after every backend edit** (no `--reload`). See
  [[flightlog-dev-server-workflow]].
- **The Windows-only WAL gotcha**: `data/flightlog.db`'s main file is often stale on its own — real,
  current data lives in the accompanying `.db-wal`/`.db-shm` sidecar files until SQLite checkpoints them.
  Copy all three together, or better, just point directly at the real path.

This file is a pointer, not a duplicate — `.ai/context/features.md`, `architecture.md`, and each
feature's own `specs/` folder have the detail.
