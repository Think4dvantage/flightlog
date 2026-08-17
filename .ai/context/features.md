# Feature History & Backlog

## Current Version: v0.9.3 — three small pilot-requested additions on top of v0.9.0 (sharing & public readiness)

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
a config change at all. **Resolved 2026-08-16**: the pilot confirmed re-authenticating to the SSO fixed
it — "Add goal" works now. No `traefik-oidc-auth` config change was needed; the diagnosis (two stacked
session lifetimes, not an app bug) was correct.

### v0.8 — Public API + VidFactory integration (tag `v0.8.0`)

API keys with scopes, `/api/integration/v1`, `flight_links` push-back. VidFactory switches to the API
and drops its own flight tables.

**No data migration** — this service already holds the authoritative 600 flights. VidFactory's copy is
discarded, not reconciled.

**Implemented per `specs/006-public-api-vidfactory/tasks.md`'s all 5 phases**, prompted directly by the
pilot asking whether the v0.5 IGC analysis (thermals, glides, launch/landing) could be exposed via API
for a highlight-video tool — it already was the exact `igc_segments` shape `architecture.md` had committed
to for this consumer since v0.5, just never exposed under a scoped, machine-authenticated surface:

1. **`api_keys` / `flight_links` tables**, `services/apikeys.py` (mint `flg_<prefix:8>_<secret:43>`,
   SHA-256 hash of the *full* key, `hmac.compare_digest` verify), and `ApiPrincipal` /
   `get_api_principal` / `require_scope(...)` in `dependencies.py` — all genuinely new code; `research.md`
   confirmed `01-project-overview.md`/`02-backend-conventions.md` had documented this shape since v0.1
   as though it already existed, when it didn't (both docs corrected this session).
2. **`/api/keys`** (JWT-authenticated) — create/list/revoke/delete. The plaintext key is returned exactly
   once, at creation, and is never retrievable again — the key-management UI (`/api-keys`) has a dedicated
   non-accidentally-dismissible reveal state for this, a genuinely new pattern for this app. `DELETE`
   requires the key already revoked (`409` otherwise).
3. **`/api/integration/v1`** (API-key-authenticated via `X-API-Key`) — `GET /flights/{id}` and
   `.../segments`, gated by `flights:read`; `PUT /flights/{id}/links/{kind}/{external_id}`, gated by
   `flight_links:write`, idempotent create-or-replace on `UniqueConstraint(flight_id, kind, external_id)`.
   `FlightMetadataOut` resolves site/glider/harness/category **names** server-side (unlike the pilot-facing
   `FlightOut`, which returns bare ids for the browser's own refdata cache to resolve) and merges in the
   `igc_tracks` summary (`thermal_count`, `best_climb_ms`, `peak_climb_ms`, `glide_ratio`,
   `alt_gain_igc_m`) — a deliberate addition beyond the original spec's metadata list, since a highlight
   video wants those numbers as captions, not just the segment timeline. A "sink" moment (part of the
   pilot's original ask) is a `glide` segment with `alt_change_m < 0`, not a new stored kind — the existing
   `igc_segments.kind` enum (thermal\|glide\|takeoff\|landing\|max_alt\|top_of_climb) already covers
   launch/landing/climb/sink/highest-point/best-climb-peak without a schema change.
4. **`FlightOut.links`** — the pilot's own `/api/flights` (list and single) now includes any
   VidFactory-pushed link, one small per-flight query, same precedent as `buddy_ids`; `flight-detail.js`
   renders it as a clickable "Linked resources" row, only when non-empty (FR-009).
5. **22 new tests** (`test_api_keys.py`, `test_integration_v1.py`) — mint/verify round-trip, tampered-key
   rejection, revoke-wins-over-expiry, cross-owner 404-not-403, wrong-scope 403, segment-shape parity
   against the JWT-gated equivalent, idempotent link replace, invalid URL scheme rejected, expiry
   round-trips through create and list. 212/212 passing project-wide, `ruff check`/`ruff format --check`
   clean. `FlightOut.links` uses its own minimal Pydantic type in `models/flights.py`, deliberately
   **not** the frozen `models/integration.py` one — a first pass imported the latter directly, coupling
   the pilot-facing shape to the versioned-separately integration contract; caught before commit.

**Live-boot verified via `curl` against the local dev server**, exactly as an external tool would use it:
minted a real key, read a real flight's metadata (resolved names confirmed correct against a real glider/
site), pushed a video link then re-pushed it to confirm the idempotent replace, confirmed the pilot's own
`GET /api/flights/{id}` immediately showed the link with no action taken, revoked the key and confirmed
the very next call was rejected, deleted the now-revoked key. Test artifacts cleaned up afterward. The
Chrome extension was not connected this session (see `env-no-browser-extension` memory) — the `/api-keys`
and flight-detail UI were verified by cross-checking every DOM id referenced in JS against the HTML and
every `data-i18n` key against `en.json`, plus `node --check` on the new/changed JS, rather than an actual
rendered screenshot.

**Doc drift fixed before shipping, not just flagged**: `media_links`/`tracker_links`/site `webcam_url`/
`rules_url` had been cited in `architecture.md`, `04-constraints.md`, and `03-frontend-conventions.md`
as existing tables/columns and as URL-validation precedent since this project's first revision — none
of them ever existed in `database/models.py`, and no code validated a URL before this session's real
`flight_links.url`. Corrected in all three files; see `RESUME.md`'s Context section for the detail.

`pyproject.toml` bumped `0.7.5` → `0.8.0` (`poetry install` re-run so `APP_VERSION` isn't stale),
committed, tagged `v0.8.0`, and pushed this session.

### v0.8.1 — Bulk IGC upload removed + track data reset

Prompted directly by the pilot after a real bulk import against `fl.sdh.lol` mismatched flights:
"I have bulk imported and it got horribly wrong." Rather than debug the bulk-match heuristic, the
feature is gone outright.

1. **Bulk upload + its pending-review queue removed entirely** — `POST /api/igc/bulk`, `GET
   /api/igc/pending`, `POST /api/igc/pending/{id}/resolve`, `DELETE /api/igc/pending/{id}`, the
   `/igc` page (`static/igc.html`/`igc.js`), its nav link, and the `IgcPendingUpload` model/
   `igc_pending_uploads` table are all gone — not just hidden, unlike the `/import` page's v0.7.5
   precedent. **No new work was needed for "link an IGC file from the flight edit page"** — the
   pilot's own edit form has had unambiguous-by-construction upload/replace/detach
   (`POST`/`DELETE /api/flights/{id}/igc`) since v0.5; that was always the primary path, bulk was
   always the secondary one. See `architecture.md`'s "Attaching an uploaded IGC to a flight" and
   "Tables that do NOT exist" sections for the full detail.
2. **`core/reset_igc.py`** — a new one-shot script, `python -m flightlog.core.reset_igc [--write]`
   (dry-run default, matching `core/importer.py`'s own shape), that deletes every `igc_tracks`/
   `igc_segments`/`site_observations` row, drops the now-modelless `igc_pending_uploads` table, and
   undoes the two things those bad tracks wrote elsewhere: nulls `flights.takeoff_time`/
   `landing_time` (the legacy workbook has no time-of-day anywhere — every value there came from a
   track) and clears any site's `coord_source == "igc_median"` coordinate (a median of the
   observations being deleted). Not owner-scoped — one pilot account, same assumption the importer
   makes. 3 new tests (`tests/backend/test_reset_igc.py`): dry-run makes zero writes, `--write`
   clears both tracks and their two side effects, and a simulated leftover `igc_pending_uploads`
   table (raw SQL, since the ORM model is gone) is dropped correctly.
3. **Run against the local dev DB this session**: `data/flightlog.db` had 3 `igc_tracks`, 21
   `igc_segments`, 3 `site_observations`, 2 `igc_pending_uploads`, and 1 site with
   `coord_source == "igc_median"` — all cleared, 5 `.igc` files deleted from `data/igc/`, 0 flights
   had `takeoff_time`/`landing_time` set (that dev DB's mismatch was small; the pilot's real damage
   is on `fl.sdh.lol`). **Not yet run against prod** — `04-constraints.md` forbids direct SSH/
   `docker-compose` there; the pilot runs `python -m flightlog.core.reset_igc --write` themselves
   inside the deployed container once this release's image is live, e.g. via
   `docker exec <container> python -m flightlog.core.reset_igc --write`.

211 tests passing project-wide (`test_igc_bulk.py` deleted with the feature; 3 new tests added in
`test_reset_igc.py`), `ruff check`/`ruff format --check` clean. `pyproject.toml` bumped `0.8.0` →
`0.8.1` (`poetry install` re-run).
Live-boot verified via `curl` against a local dev boot: `/igc` and every bulk/pending route 404,
`/api/flights/{id}/igc` and its `segments`/`track.geojson` siblings still resolve, the nav no
longer renders a Tracks link.

### v0.9 — Sharing & public readiness (tag `v0.9.0`)

Per-flight visibility (private / unlisted / public), public flight page, public pilot profile, rate
limiting on the public surface.

**Implemented per `specs/007-sharing-public-readiness/tasks.md`'s all 5 phases, tested, live-verified
this session.** Two items in this feature's original wording were already stale by the time planning
happened: the buddy invite/accept/decline flow has been **shipped since v0.2**
(`architecture.md`'s API Contracts table already lists it), and `allow_self_registration` was already a
working, flippable config flag. The real, still-open gap this feature closed was the starter-category
seeding self-registration had been missing since v0.2's own planning — see `architecture.md`'s "Sharing
& public readiness" section for the full detail on every part of this milestone.

1. **`flights.visibility`** (`private`\|`unlisted`\|`public`, default `private`) and
   **`users.public_profile_enabled`** (boolean, default `False`) — two new columns via
   `_run_column_migrations()`'s idempotent guard, no new tables. `PUT /api/flights/{id}` and
   `PUT /api/auth/me` each accept one more field on their existing owner-scoped routes — no new routes
   for the pilot's own write path.
2. **`/api/public`** (`api/routers/public.py`) — unauthenticated by design, the second and third
   consumer (after `health.py`) of this app's "absence of a dependency is what makes a route public"
   convention. `GET /flights/{id}` and `GET /profiles/{user_id}`, both 404-byte-identical whether the
   row is missing or simply not public. `models/public.py`'s `PublicFlightOut`/`PublicProfileOut` are an
   explicit field allowlist, never inherited from the private `FlightOut`/`UserOut` schemas.
3. **`slowapi` 0.1.10** (new dependency, re-verified current against PyPI at implementation time) —
   per-route `@limiter.limit(...)` decorators inside `public.py` only, never a global middleware, so the
   authenticated surface is never throttled by public-route traffic. The limit value is a callable
   reading `config.api.public_rate_limit` (default `"30/minute"`) fresh per request, not a string frozen
   at import time. Keyed on `dependencies.client_ip` (X-Forwarded-For-aware), not `slowapi`'s own
   remote-address default, which would collapse every visitor behind this deployment's Traefik proxy
   into one shared bucket. A dedicated `RateLimitExceeded` handler in `main.py` maps a 429 to this app's
   own `{"error": {"code": "RATE_LIMITED", ...}}` envelope.
4. **`core/user_seed.py`** — five starter categories (`Thermal`, `Soaring`, `XC`, `Hike&Fly`,
   `Sled run`) seeded on `POST /api/auth/register`, guarded by `users.seeded_at IS NULL` — the first real
   consumer of that column since it was reserved in v0.2. Deliberately generic English categories, not
   this pilot's own 12 legacy German ones, several of which are personal/jurisdiction-specific
   (`Schwarzflug`, `Prüfung`, `Startleiter`).
5. **Frontend**: `static/public-flight.html`/`.js` and `static/public-profile.html`/`.js` — new,
   unauthenticated-by-design pages (plain `fetch()` not `fetchAuth()`). A visibility `<select>` +
   shareable-link display added to `flight-detail.html`/`.js`, live-updating its hint text on every
   selection change before Save (NFR-003's "make the exposure level unambiguous" without a second
   confirmation click) — the hint text explicitly names notes as part of what becomes visible, after a
   live curl pass returned a real flight comment naming a friend. A "Public profile" card (toggle +
   shareable link) added to `api-keys.html`/`.js` — the closest existing pilot-account-settings page,
   reused rather than standing up a new settings page for one toggle.
6. **A post-implementation advisor review caught a real bug curl could not**: the two public pages
   originally called `bootstrapPage({ requireAuth: false })`, which still ran the authenticated-nav path
   whenever any token happened to sit in `localStorage` — a visitor holding a stale/expired token got
   silently redirected to `/login`, exactly the FR-013 leak this feature exists to prevent. Fixed by a
   genuine `anonymous: true` option on `bootstrapPage()` (`static/bootstrap.js`) that skips the token
   check and the authenticated nav links entirely. Mechanically proven with a Node harness importing the
   real `bootstrap.js` under a stubbed DOM/localStorage — not just reasoned about — confirming both that
   the fix works and that the harness itself reproduces the bug when `anonymous` is reverted to `false`.
7. **14 new tests** (`test_public_routes.py`, `test_user_seed.py`): all three visibility states'
   unauthenticated access, byte-for-byte identical private-vs-nonexistent and disabled-vs-nonexistent
   404s (`response.content`, not `.json()` — `plan.md`'s Risk section specifically asks for this rigor),
   opt-in/opt-out taking effect immediately, rate-limit 429 with the correct envelope, the authenticated
   surface unaffected during a public-route burst, exactly-five-editable-categories on registration, and
   the seed being a no-op on a second call. 225/225 passing project-wide, `ruff check`/`ruff format
   --check` clean.

**Live-boot verified via `curl` against the local dev server**, not just under pytest: set a real flight
to public, confirmed the unauthenticated `GET` succeeded and a private flight 404'd byte-identically to a
made-up id; opted the real dev account into a public profile, confirmed its `GET /api/public/profiles/
{id}` listed exactly the one public flight; fired 33 quick requests at the default 30/minute limit and
confirmed 429s kicked in while the authenticated `/api/flights` call succeeded throughout the same burst;
registered a fresh account and confirmed exactly 5 editable categories. All test-only state (the public
flight, the opted-in profile, the registered throwaway account) was reverted/deleted from the real dev DB
afterward — the pilot's own real account and data were untouched by the end of the session.

**`olddata/Flugbuch.xlsx` was deliberately not scrubbed from git history as part of this feature's own
implementation** — `specs/007-.../research.md` scoped that as a separate, explicitly pilot-confirmed
action, never bundled into a routine task list. **The pilot explicitly requested it in a follow-up
message the same session, and it was performed then**: `git filter-repo --path olddata/Flugbuch.xlsx
--invert-paths` removed the file from every commit in history; every existing tag (`v0.1.0`–`v0.9.0`)
was rewritten as a result (new SHAs throughout — an irreversible operation, not a revertible commit). A
full-repo bundle backup (`git bundle create --all`) and a copy of the file itself were taken first,
outside the repo, before the rewrite. The file is now `/olddata/`-gitignored and kept on disk
**untracked** so the importer and the real-workbook regression tests (already `skipif`-gated on its
presence) keep working locally. **Force-pushed to `origin`** (`main` + all 15 rewritten tags) after
explicit confirmation, and independently verified against a fresh `git clone` of the real GitHub
remote (not just local state) — zero commits, zero blob objects referencing the file anywhere in the
server's own history. See `04-constraints.md`'s Personal Data section for the exact command
and rationale.

### v0.9.1–v0.9.3 — small pilot-requested additions on `/sites` and `/stats`

Three point releases, each a single small change requested directly by the pilot rather than a
new spec cycle, following `v0.7.1`–`v0.7.5`'s existing precedent for post-ship increments.

**`v0.9.1` — landing sites get a green map pin.** `static/sites.js`'s `/sites` Leaflet map drew
every site with the default blue marker regardless of role. Landing-only sites now render a green
pin (inline SVG `divIcon`, no new binary asset); a site that's both launch and landing keeps the
default blue marker, so launch always wins. `static/shared.css` gained one rule
(`.site-pin { background: none; border: none; }`) to strip Leaflet's default `divIcon` box.

**`v0.9.2` — optional flight nickname.** `flights.nickname` (nullable `VARCHAR`, migrated via the
usual `_run_column_migrations()` guard) is a short free-text label alongside `notes`, threaded
through the existing generic `FlightCreate`/`FlightUpdate`/`FlightOut` update path — no router
change needed. Shown as a new sortable/searchable column on `/flights`, folded into the
`/flights/{id}` and `/public/flights/{id}` page titles when set, and added as a column on
`/public/profiles/{id}`. Gets the same public-exposure rule as `notes` (visible only when a
flight's `visibility` is `unlisted`/`public`) — confirmed with the pilot rather than assumed, since
it's the kind of exposure decision `04-constraints.md`'s "never leak more than the pilot chose"
principle exists to protect. `PublicFlightOut`/`PublicProfileFlightOut` (`models/public.py`) both
extended; the `visibility_hint_unlisted`/`visibility_hint_public` copy on `flight-detail.html`
updated from "including your notes" to "including your notes and nickname" so it stays accurate.

**`v0.9.3` — IGC-derived thermal and airtime stats.** The pilot noticed self-reported flight
duration routinely disagrees with the IGC track's actual recorded time, and asked for the IGC
numbers to sit beside the self-reported ones rather than be trusted blindly. `core/stats.py`'s
`igc_rollup()` — already the single home for every IGC-derived figure on `/stats` — gained three
fields, all plain aggregates over already-stored per-track columns from v0.5 (`igc_tracks.
thermal_count`/`duration_s`), no new analysis: `total_thermals` (a SUM), `total_igc_airtime_min`
(a SUM, rendered as a "Total airtime (IGC)" tile directly next to the existing self-reported
"Total airtime" tile in the Totals grid — the pilot's own "beside the self reported one"), and
`avg_thermals_by_month` (a new per-calendar-month average, mirroring `_max_by_month()`'s existing
null-vs-zero convention, rendered as a new bar chart in the "IGC rollups" card via the existing
`barChart()` helper). Live-verified against a real fixture (`tests/backend/fixtures/valid_flight.
igc`): a flight self-reported as 30 min measured 602s (~10 min) in the track — exactly the
discrepancy the pilot described, now visible side by side on the page.

All three: `pytest`/`ruff` clean, live-verified via `curl` against a local dev boot with
test-only state cleaned up afterward. The Chrome extension was not connected in the sessions that
shipped them, so the actual rendered UI (pin colors, the nickname column/title, the new stat tiles
and chart) is unconfirmed visually — first thing to check next time a browser is connected.

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
