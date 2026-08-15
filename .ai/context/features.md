# Feature History & Backlog

## Current Version: v0.7.4 tagged and deployed to `fl.sdh.lol`; v0.7.5 (contacts/secondary CRUD/import removal/progression fix) implemented, tagged, deployed this session

v0.1 through v0.7.4 are all tagged (`v0.1.0`–`v0.7.4`) and each triggered `docker-publish.yml`. v0.6
shipped the secondary-sheet imports (hikes, ground-handling, tandem flights) and full goals CRUD; the
XContest score import originally scoped alongside it has moved to the Backlog below rather than staying
an open phase of that milestone — see its entry there. **v0.7 (statistics) shipped and is live at
`fl.sdh.lol`**, followed by a round of small post-ship enhancements shipped as `v0.7.1`–`v0.7.4` (on-bar
chart value labels, "Best by month", five coaching-oriented stats from a pilot-review pass, and a
sortable IGC-track-present/missing flag on `/flights`).

**`v0.7.5` closes four real gaps the pilot found on the live `fl.sdh.lol` deployment**: no way to create
buddies/contacts, no way to add a hike/groundhandling session/tandem flight by hand, an outdated and
unwanted "Import findings" page, and a "Cumulative flights over time" chart that was a straight diagonal
line with zero information content. See that entry's note below for the full detail — all four are
implemented, tested, live-verified, and shipped this session. See `RESUME.md` for the moment-to-moment
state.

---

## Shipped Milestones

### v0.2 — Core data + Excel import

Spec, plan, research and data model live in `specs/001-core-data-import/`. Nine new tables
(`regions`, `sites`, `user_site_prefs`, `gliders`, `harnesses`, `flight_categories`, `buddies`,
`flights`, `flight_buddies`), owner-scoped CRUD across seven routers, `core/flights.py`'s
COALESCE-chain altitude figures (computed on read, never stored), `core/aliases.py`'s
byte-verified normalization tables, and `core/importer.py` — dry-run by default, idempotent via
`import_key`, with region reconciliation, a formula cross-check, and buddy-name proposals.

**The 600 flights land here** — verified against the real `olddata/Flugbuch.xlsx`: exactly 600
flights import, a second `--write` run changes nothing, and the importer's own checks surface
(rather than silently resolve) three real data-quality findings inherited from the spreadsheet — the
region-formula bug behind the 596-vs-600 gap (see `architecture.md`'s Statistics section for the
confirmed root cause), one `Altgain` figure that disagrees with a recomputed value (row 387), and one
harness (`Advance Success 2`, 3 flights) that is retired gear absent from the current master list.

121 tests passing (61 new since v0.1's 60, including a post-deploy regression test — see below);
`ruff check` and `ruff format --check` clean.

**Deferred:** IGC, statistics, any UI beyond the raw API, the secondary Excel sheets (hiking,
ground-handling, tandem, goals), XContest import.

**Verified against a live boot**, including running the importer itself inside the deployed container
(not just under pytest): dry-run and `--write` both exercised via `docker exec` against the real
workbook, all 600 flights landed. That run surfaced one real bug — `database/db.py`'s region-seed list
had the same transcription typo (`Dürstetten` vs the byte-verified `Därstetten`) that `aliases.py` had
already been corrected for — which silently created a 13th, orphaned region row. Fixed on `main`, with a
regression test asserting a real-workbook import creates zero new regions. Not yet redeployed to prod;
the orphan row and the fix are both still pending as of this note — see `RESUME.md`.

### v0.1 — Skeleton & auth (2026-08-06, tag `v0.1.0`)

App factory + lifespan, `/health` with liveness/readiness semantics, typed error envelope with three
global handlers (registered against **Starlette's** `HTTPException`, not FastAPI's subclass — see
`context/architecture.md`), security headers + CSP `script-src 'self'`, GZip, `?v=` cache-busting from
`pyproject.toml` with a `tomllib` fallback for the no-root container install, `init_db()` + WAL pragmas
+ `_run_column_migrations()`, the `users` table with a `UtcDateTime` type decorator, JWT
register/login/refresh/`/me`/password-change via PyJWT + bcrypt, `auth.allow_self_registration: false`
gate, login/register/index pages, `shared.css` / `bootstrap.js` / `auth.js` / `i18n.js`, vendored
Leaflet 1.9.4 + Chart.js 4.5.1, Docker on `python:3.14-slim` + compose + dev overlay, both GitHub
Actions workflows, `conftest.py` with the StaticPool and ASGITransport traps documented.

**Deploy note:** multi-arch (amd64+arm64) image built and pushed in 5m29s — `python:3.14-slim` is
proven for this dependency set. Not yet proven for `libigc` (arrives v0.5); re-run the build gate then.

**Verified in production shape**, not just under test: booted with a real `config.yml`, exercised
`/health`, login, `/me`, the 401/404/422 error envelopes and static cache headers over live HTTP.

60 tests passing; `ruff check` and `ruff format --check` clean on Python 3.13 and 3.14.

**Deferred:** OAuth, roles beyond pilot/admin, any flight data.

---

## Roadmap

### v0.3 — Flight log UI · **← MVP BOUNDARY** (MVP implemented on `main`, not yet deployed)

Spec, plan, research, data model and the 49-task breakdown live in `specs/002-flight-log-ui/`.

**MVP done (Phases 1–8, T001–T036):** `/flights` with free-text search plus year / category / glider /
launch-site / region filters, sortable columns, client-side pagination, URL-synced filter state, and an
inline add/edit/delete drawer with per-field validation rendered from the `VALIDATION_FAILED` envelope.
`/flights/{id}` detail, fresh-load safe. `/sites` with a self-hosted-Leaflet map — click an unpinned
site's row to arm placement, click the map to drop the pin, drag an existing pin to move it; both paths
set `coord_source = "manual"` server-side (`sites.py`, new behavior, no schema change). `/equipment` —
create/edit/retire for gliders and harnesses; retired gear stays visible (styled distinct) but is
excluded from the flights drawer's default dropdowns. `/import` — a read-only page rendering
`core/import_history.py`'s `HISTORICAL_IMPORT_SUMMARY`, a frozen constant generated from a fresh dry-run
of `run_import()` against `olddata/Flugbuch.xlsx` (not hand-transcribed from `RESUME.md`) behind the new
`GET /api/import-report`. `static/refdata.js` is the shared fetch-once join cache every list/detail page
uses to resolve ids to display names. 127 backend tests passing (6 new: 4 for `coord_source`, 2 for the
import report), `ruff check`/`ruff format --check` clean. Verified live via `curl` against a local dev
boot with the real 600-flight workbook re-imported — every route, every new/changed endpoint, and the
full flight CRUD lifecycle exercised end-to-end.

**Not yet done:** visual browser verification (T047 — no browser automation tool was connected this
session, so rendering, the map's click/drag interactions, and keyboard navigation (NFR-002) are
unconfirmed), Phases 9–11 (`/contacts`, CSV export, remember-last-filters — all P2/P3, droppable from
the first shippable cut), a version tag, and deployment. `pyproject.toml` was bumped to `0.3.0` (static
assets changed — the version is the cache key) but nothing has been tagged or shipped yet.

**At v0.3 the `Flugbuch` sheet is fully replaced and the Excel is never opened again.** That is the MVP
definition — everything after it is upside, not table stakes.

**Deferred:** everything IGC, all statistics, all sharing.

**v0.4.0 shipped as a `/sites`-and-`/import` bugfix release**, not a new epic — an edit drawer for
sites (name/flags/region/elevation/coordinates together, replacing the old click-to-place-only flow), a
fix for a Leaflet marker-icon path doubling bug, and in-app explanations for the `/import` findings
that were already correctly root-caused in code comments but never surfaced to the pilot. It consumed
the version number this roadmap had reserved for IGC, so the epics below are numbered one higher than
originally planned (v0.4 IGC → v0.5, and so on through v0.10 Enrichment; v1.0 Polish is unchanged).

### v0.5 — IGC ingest + analysis

**Implemented on `main`, not yet deployed.** Per-flight upload/replace/detach with eight computed
figures (duration, distance, max altitude, altitude gain, thermal count, best/peak climb, glide ratio),
bulk upload with date+duration auto-matching and a persisted `igc_pending_uploads` review queue
(resolve/dismiss), automatic site-coordinate backfill from track data that never overwrites a manual
pin, `flights.takeoff_time`/`landing_time` writeback, admin-gated re-analysis, a Leaflet track map, and
a Chart.js barogram with thermal/glide phases shown via per-segment line coloring (no annotation
plugin — none is vendored). Four new tables (`igc_tracks`, `igc_segments`, `site_observations`,
`igc_pending_uploads`); `igc_pending_uploads` is a plan-level addition beyond what this roadmap entry
originally named. 17 new backend tests (144 total passing project-wide), `ruff check`/`ruff format
--check` clean. `pyproject.toml` bumped to `0.5.0`.

Two of `core/igc.py`'s design assumptions were corrected against the real installed `libigc` 1.2.0
package rather than shipped as guessed: altitude-source selection reads the library's own
`flight.alt_source` instead of reimplementing a heuristic that wouldn't have matched real data anyway,
and `FlightParsingConfig`'s three real tunable parameter names replace four differently-named,
differently-shaped ones originally assumed. See the IGC analysis section above for the full detail and
`specs/003-igc-ingest-analysis/research.md` for how each was resolved.

**Verified live via `curl` against a local dev boot** for every endpoint, including the full bulk-upload
→ ambiguous → resolve/dismiss cycle and a real fixture's figures cross-checked by hand — not just unit
assertions. Two real bugs were caught only because of that live pass: `auth.js`'s `fetchAuth()` forced
`Content-Type: application/json` onto every request with a body, silently breaking `FormData` multipart
uploads (fixed, now skips that header for `FormData`); and dismissing a pending upload left its
`UniqueConstraint(owner_id, sha256)` slot occupied, silently blocking any later re-upload of that exact
file (fixed, covered by a regression test).

**Not yet done: actual browser rendering.** No browser automation tool was connected this session either
(same gap `v0.3`/`v0.4.0` already noted) — the map, the barogram's per-segment coloring, the file-input
controls, and keyboard navigation are all unconfirmed. First thing to do the moment a browser is
available, same as `specs/002-flight-log-ui`'s still-open T047.

**Deferred:** XC scoring, AGL/DEM, 3D.

### v0.6 — Secondary sheets + goals (tag `v0.6.0`)

`hikes`, `groundhandling_sessions`, `tandem_flights`, `goals` imported in one pass from the workbook's
four remaining sheets.

**Shipped and tagged.** Hikes/ground-handling/tandem-flights import (read-only list views) and goals
(full CRUD, imported from `Ziele`) are implemented, tested, tagged `v0.6.0`, and live in
`data/flightlog.db` — 85 hikes (35 correctly linked to a `Hike&Fly` flight), 9 ground-handling sessions,
17 tandem flights, 11 goals, confirmed against the real workbook and verified in a real connected browser
(Claude in Chrome, its first successful connection all session).

**XContest score import (`xc_official_score`/`_type`/`_url`), originally scoped alongside this
milestone, has moved to the Backlog below** (2026-08-15) rather than staying an open phase of this
milestone — v0.6 ships complete without it, and no real "My Flights" export sample was available to
build the parser against. See the Backlog entry to resume; the design record is
`specs/004-secondary-sheets-xcontest/` (Phase 5, T018–T024).

Scopes the `/goals` page here, not in v0.7 — a pilot who just had their goals imported should be able to
see and manage them immediately, not wait for the statistics milestone. **v0.7's roadmap entry below
still says "`/stats` and `/goals` pages" from before this was decided** — that's now stale; `/goals` is a
v0.6 deliverable, v0.7 is `/stats` only. Left as a visible historical trace rather than silently
rewritten.

**`Flugbuch.xlsx` is not yet fully retired** — every sheet except the XContest-adjacent columns on
`flights` is now reproduced elsewhere in the app; the workbook's exact XContest scores are the one
remaining reason it might still be opened.

### v0.7 — Statistics (implemented on `main`, not yet tagged or deployed)

The full catalogue: totals, averages (including excluding-training), per-year / per-month / year×month,
duration buckets and histograms, distance and altitude distributions, personal bests each linking to
their flight, per-site / per-region / per-glider / per-harness / per-category / per-buddy year matrices,
launch-technique split, Hike&Fly totals, IGC rollups (cumulative thermal climb — the headline number the
Excel cannot produce), streaks and YTD pace, cumulative progression series. `/stats` page only — `/goals`
already shipped as part of v0.6 (see that entry's note above).

**Implemented and verified live.** `core/stats.py` batches one load of the owner's flights plus every
reference row needed to resolve them (sites, `user_site_prefs`, categories, gliders, harnesses, regions,
`flight_buddies`), then computes every figure in pure Python from there — deliberately not reusing
`core/flights.py`'s per-flight `compute_altitude_figures()`, which would reintroduce the exact N+1
`04-constraints.md` warns against. Only the cumulative thermal-climb rollup stays a genuine SQL aggregate.
No new tables, no cache — matches the project's explicit non-speculative-caching stance
(`architecture.md`). `api/routers/stats.py`'s 8 `GET` endpoints are thin wrappers; `matrix/{dimension}`
takes a plain `str` + allowlist (never `Literal[...]`) so an unknown dimension is a `404
ENTITY_NOT_FOUND`, not FastAPI's own `422`. 180 tests passing project-wide (23 new — a pure-logic set
duck-typing flights with `SimpleNamespace`, per `06-testing-conventions.md`'s own pinned example, plus API
tests against a small hand-built fixture covering a personal-best tie, a "not recorded" dimension bucket,
and zero-track/zero-buddy states), `ruff check`/`ruff format --check` clean. `pyproject.toml` bumped
`0.6.0` → `0.7.0`.

**Verified live via `curl` and a real connected browser** (Claude in Chrome connected successfully again
this session) against the real 603-flight dev database — every one of the 8 endpoints exercised, the full
`/stats` page scrolled and screenshotted end-to-end with zero console errors, the buddy-matrix sparse
state and a "View flight" personal-best link both confirmed interactively (the link resolved to the
correct flight: 3h30min / 3645m, matching the `longest_airtime`/`max_altitude` figures shown on `/stats`).
`spec.md`'s Success Criteria were confirmed against real numbers, not just plausible-looking output: the
reverse-launch share (209/603 ≈ 34.66%) still disagrees with the workbook's stale 33.5%, as expected, and
the denominator has grown from 600 to 603 — exactly the live-not-frozen behavior FR-001 requires, not a
bug; `total_alt_gain_m` (60841) differs from the workbook's own reference Total Altgain (61191) by exactly
350 — the already-known row-387 correction, with no unexplained residual; and the buddy year matrix
returned empty (`rows: []`), confirming zero `flight_buddies` rows exist yet — the "legitimately sparse"
state the spec predicted, not a defect. See `architecture.md`'s Statistics section for the full detail,
now updated from "two" to **four** confirmed workbook disagreements (the `Buddys`-tally name/count
mismatch discovered while planning this feature is the newly-added one).

**Deployed to `fl.sdh.lol`. Two small post-ship enhancements shipped as `v0.7.1`/`v0.7.2`**, driven by
pilot feedback against the live instance rather than new spec work: every bar chart on `/stats` now draws
each bar's own value directly on the bar (no hover needed) via a small inline Chart.js plugin, and a new
"Best by month" section (`GET /api/stats/monthly-extremes`) shows the single best duration/distance/
altitude-gain flight in each calendar month across all years — deliberately the max, not an average,
matching the pilot's literal ask ("in what months did I get my longest flights"). `v0.7.1`'s
bar-value-label plugin shipped with a real bug (see `architecture.md`'s Chart.js gotcha note) caught only
by a live re-verification pass, not by the test suite — fixed in `v0.7.2`.

**`v0.7.3` adds five coaching-oriented stats from a direct pilot-review pass** (asked as "review my
flightlog as an X-Alps pilot/instructor, run every idea by me first") — see `architecture.md`'s
"Coaching-oriented additions" note for the full list (XC progression, currency, site diversity, IGC
coverage, personal-best recency) and what was proposed-but-declined (a safety-incident-category tile).
Framed around the pilot's own life context (a newborn on the way, deliberately less flying time and
higher safety margins) rather than pushing volume — recorded in this session's memory, not just here,
since it should shape how future `/stats` copy is worded too.

**`v0.7.4` adds a sortable IGC-track flag to `/flights`** — a green ✓/dim – badge per row so it's obvious
at a glance which flights are missing a track, requested directly by the pilot as a follow-up. Purely
additive (`FlightOut.has_igc_track`, batched not per-row — see `architecture.md`'s `/api/flights` entry);
no `/stats` or `flight-detail` change needed.

**`v0.7.5` — four fixes from a live pilot-feedback pass against the deployed `fl.sdh.lol` instance,
tagged and shipped this session:**

1. **`/contacts` (Phase 9 of `specs/002-flight-log-ui`, spec'd since v0.3, never built until now)** —
   full CRUD for buddies. The backend (`/api/buddies`) already had complete CRUD + link/accept/decline
   since v0.2; the only gap was a page. Also fixes the actual root cause of "I can't tag buddies on a
   flight" — the flight drawer's buddy multi-select was always empty because there was no way to create
   a buddy in the first place, not a bug in the drawer itself. Verified live end-to-end: created a
   contact, tagged it on a real flight, confirmed the contact's flight-count updated from 0 to 1.
2. **Full CRUD for hikes, groundhandling sessions, and tandem flights** — all three were "import-and-view
   only" by original v0.6 design (`specs/004-secondary-sheets-xcontest`), which made sense before the
   pilot pointed out there was no way to add one by hand afterward. `HikeCreate`/`HikeUpdate` add an
   optional `flight_id` a pilot can link/unlink manually (never ownership-validated, matching this app's
   existing convention for other cross-referenced ids in `flights.py`); `import_key` stays server-only
   across all three. New `tests/backend/test_secondary_crud.py` (8 tests) covers create/get/update/delete
   and ownership scoping for all three.
3. **The "Import findings" page is gone** — nav link and `/import` route removed, `static/import.html`/
   `import.js` deleted. The pilot's own words: "outdated and not needed." `/api/import-report` and
   `core/import_history.py`'s frozen snapshot are deliberately untouched, in case the historical record is
   ever wanted again — only the UI surfacing it is gone.
4. **The useless "Cumulative flights over time" chart is replaced** — a running total by date is
   monotonically increasing by construction, so the chart was always a straight line bottom-left to
   top-right regardless of the pilot's actual activity pattern; the pilot called this out directly as
   having "no use at all." Replaced with "Monthly pace, by year" — one line per year across Jan-Dec,
   built entirely client-side from `time-breakdown`'s already-fetched `year_month_matrix` (no new backend
   call). `ProgressionOut.cumulative_series`/`ProgressionPoint`/`core/stats.py`'s `cumulative_progression()`
   were deleted outright rather than left as dead code.

**Also investigated, not fixed in-app**: the pilot separately reported "Add goal" not working on
`fl.sdh.lol`. Tested locally against the exact same deployed version (`v0.7.4`) — worked perfectly,
201 on create. Traced the real cause via SSH to the prod host: `fl.sdh.lol` sits behind a Traefik
`traefik-oidc-auth` (Pocket-ID) middleware protecting the *entire* host, layered on top of flightlog's
own independent JWT login — confirmed by an unauthenticated external request returning a 401 in that
proxy's own RFC9110-style error format, with no trace of the request ever reaching the flightlog
container's own logs. This is almost certainly why writes silently fail for the pilot while reads (page
loads) keep working — two separate session lifetimes stacked on the same host. Deliberately **not**
touched — shared infrastructure serving other public services on the same host, config file contains
live credentials, and the pilot chose to self-test (re-login to the SSO) before deciding whether it needs
a config change at all. See `RESUME.md`'s Open Questions for the follow-up.

### v0.8 — Public API + VidFactory integration

API keys with scopes, `/api/integration/v1`, `flight_links` push-back. VidFactory switches to the API
and drops its own flight tables.

**No data migration** — this service already holds the authoritative 600 flights. VidFactory's copy is
discarded, not reconciled.

### v0.9 — Sharing & public readiness

Per-flight visibility (private / unlisted / public), public flight page, public pilot profile, rate
limiting on the public surface.

**Full spec/plan/tasks written** (`specs/007-sharing-public-readiness/`), not yet implemented. Two items
in this entry's original wording were already stale by the time planning actually happened: the buddy
invite/accept/decline flow has been **shipped since v0.2** (`architecture.md`'s API Contracts table
already lists it), and `allow_self_registration` is **already a working, flippable config flag** — but
self-registering today produces a broken account with zero flight categories, since the generic
per-account starter-category seeding was explicitly deferred to "once self-registration is live"
(`specs/001-core-data-import/research.md`, written under the pre-renumbering scheme where this milestone
was "v0.8"). That real, still-open gap — not "make the flag flippable," which is already true — is what
this feature's spec actually scopes for self-registration.

**`olddata/Flugbuch.xlsx` must be removed from git history before this ships.** This is a genuinely
destructive, hard-to-reverse repository operation (a history rewrite, not a plain `git rm` —
`04-constraints.md`) and must be explicitly confirmed with the pilot at implementation time, not
performed as a routine task step.

### v0.10 — Enrichment

Lenticularis cross-link ("what were the conditions at this site on this date"), DEM for AGL, weather
snapshot per flight.

### v1.0 — Polish

Mobile-responsive pass, `/help`, `/admin`, one-command backup and export-everything.

---

## Backlog (unordered)

- **XContest "My Flights" score import** (moved here from v0.6, 2026-08-15) — attach an
  independently-verified `xc_official_score`/`_type`/`_url` to matched flights, per
  `specs/004-secondary-sheets-xcontest/` (Phase 5, T018–T024) and its `research.md`/`spec.md`/
  `data-model.md`/`contracts/endpoints.md`, all already written. Blocked on obtaining one real XContest
  "My Flights" export sample (the export requires a logged-in session to inspect, and the one
  third-party integration investigated, `Iv/FlyHigh`, submits a flight for scoring rather than reading
  back an already-scored list) — resolve the schema against that sample before writing the parser, same
  pattern as v0.5's two real `libigc` unknowns. Once unblocked: implement `core/xcontest_import.py`
  (date-based match, unambiguous → attach else → pending, reusing `igc_pending_uploads`'s exact pattern),
  add the three `flights` columns, and pick up `pyproject.toml`'s next open version slot.
- Bulk edit on the flights table (reassign category / glider across a selection)
- Duplicate-flight detection on manual entry (same date + site + duration)
- Gear service reminders — reserve repack due, annual check due
- Per-site wind-window editing with a compass-rose control
- Import from other logbook formats (SkyViz, XCTrack, Flyskyhy)
- Photo thumbnails resolved from `media_links` without hosting the images
- Grant the deploy `gh` token `read:packages` so published image tags can be verified from this repo
  rather than inferred from the workflow config
- `config.py`'s `log_effective_config()` doesn't log `auth.bootstrap_admin_email` or whether
  `auth.bootstrap_admin_password` is set (the way it already does `auth.jwt_secret set=%s`). Surfaced
  while diagnosing a post-v0.2.0-deploy login failure — the fastest signal was `db.py`'s own
  "Bootstrap admin: ..." log line, but confirming whether the deploy pipeline actually delivered the
  secret into `config.yml` at all took longer than it should have. Two log lines would close the gap.

### Shelved

- **XC scoring computed in-app.** Decided against for now: FAI triangle and free-distance optimisation
  is a hard computational-geometry problem, and while XContest is the authority the number that matters
  is theirs, not ours. Official scores are imported instead. **This blocks the far-future direction
  below** and would need revisiting — the candidate is `igc-xc-score` (branch-and-bound, WGS84, supports
  XContest/FFVL/FAI/XCLeague rules, bounded runtime with an optimality flag), invoked as a subprocess.
- **Official shared site catalogue.** The schema reserves `sites.owner_id IS NULL` for it, but with one
  user there is nothing to share yet.

### Never in scope

Live tracking. Competition scoring for organisers. Social feed / comments / likes. A mobile app *in this
repo* — that would be a separate repo against the same API.

---

## Far-future direction (recorded, not planned)

The stated long-term ambition is to grow this into an XContest competitor. Nothing here is scheduled; it
is written down so near-term decisions do not quietly foreclose it.

Already aligned: the API-first design, owner-scoped multiuser from day one, `sites.owner_id` reserved
for a shared catalogue, `igc_segments` persisted rather than recomputed, and the v0.9 visibility flags.

Would need revisiting: **XC scoring must become computed, not imported** — a competitor has to be the
scoring authority. The plan keeps this cheap by isolating everything XC behind `core/xcontest.py` and a
small set of `xc_*` columns, so the swap is a module replacement rather than a schema change.

Would need genuine new work: **SQLite → PostgreSQL** (a public league is a write-concurrency problem and
SQLite's single-writer model is the wall), and **track validation / anti-cheat** (G-record signature
verification, plausibility checks), which a personal log simply does not need.
