# Resume Notes — 2026-08-16

## In Progress

**v0.7.0 (statistics) is tagged, pushed, and deployed — confirmed live by the pilot at `fl.sdh.lol`.**
A growing set of small follow-up enhancements, driven directly by pilot feedback against that live
instance, is implemented and live-verified locally as `v0.7.1`→`v0.7.4` but **not yet committed, tagged,
or pushed**. The pilot was explicitly asked and said to hold off on shipping this round — do not commit/
tag/push it without asking again.

### `v0.7.4`: IGC track flag on `/flights`

Smallest addition of the round: a "Track" column on the `/flights` list — a green ✓ (`.track-yes`) or dim
– (`.track-no`) badge showing at a glance which flights have an uploaded IGC track, sortable like any
other column. `FlightOut.has_igc_track` is new; `api/routers/flights.py`'s list endpoint batches one
`IgcTrack.flight_id IN (...)` query for the whole page rather than checking `flight.igc_track` per row
(would've been the exact N+1 `04-constraints.md` warns against) — single-flight routes (create/get/update)
still check directly, since that's one row, not a loop. Purely additive: no change to `flight-detail`
(already shows the full track section) or to any `/stats` endpoint. 1 new backend test
(`test_has_igc_track_reflects_presence_on_list_and_single_get`), 183/183 passing, verified live via
`curl` and a real browser (sorted by the new column, confirmed the 3 tracked flights sort to the top with
the green badge, everything else shows dim).

### What's in this round

1. **Every bar chart on `/stats` draws each bar's own value on the bar** (no hover needed) — a small
   inline Chart.js plugin (`barValueLabelPlugin` in `static/stats.js`), not a vendored dependency.
2. **"Best by month"** (`GET /api/stats/monthly-extremes`) — the single best (max, never average)
   duration/distance/altitude-gain flight per calendar month across all years.
3. **A pilot-coaching review pass**: asked to role-play an X-Alps pilot/instructor and propose new stats
   aimed at motivation + safety. Pulled the real 603-flight dataset first (not generic ideas), presented a
   menu of concrete proposals with rationale, and only built what the pilot greenlit:
   - **XC progression** (`GET /api/stats/xc-progression`) — % of flights ≥10km per year (reuses
     `distribution()`'s own first distance-bucket boundary rather than inventing a number, and is
     deliberately category-name-independent — `flight_categories.name` is free text, never matched
     against). Tells a real story in this pilot's own data: 0%→33% growth 2018-2023, dropping to 11-12%
     in 2024-2025 — see the life-context note below before reading that drop as a regression.
   - **Currency indicator** — "N days since your last flight" on the Momentum section, colour-banded
     (green ≤14d / amber ≤45d / red beyond, via `--success`/`--warm`/`--danger`) — a safety nudge, not a
     guilt trip. Backend: `ProgressionOut.days_since_last_flight`/`last_flight_date`.
   - **Site diversity / comfort-zone note** — "62% of your flights are at your top 5 sites (34 sites
     flown in total)" under the dimension-matrix section, only shown on the "site" tab. Computed entirely
     client-side from already-fetched `matrix/site` data — no backend change.
   - **IGC track-coverage nudge** — "Track coverage: 0.5% (3/603)" tile, always shown (even at 0%),
     separate from the cumulative-climb empty state. Also client-side only, combining `totals.total_flights`
     (now cached in a module-level `totalFlights`, `loadTotals()` awaited before the rest of `init()`'s
     `Promise.all` so it's ready in time) with the existing `igc-rollup` response.
   - **"Set N days/years ago" on each personal best** — `PersonalBestOut` gained a `flight_date` field;
     the personal-bests table gained a 4th column computed client-side from it.
   - Proposed but **declined by the pilot**: surfacing `Bruchflug`/`Schwarzflug` category counts as a
     dedicated safety-incident tile. Not built — don't re-propose without new signal.

### A real bug, caught only by live re-verification

The first version of the bar-value-label plugin stored its per-chart formatter function at
`chart.options.plugins.barValueLabel.formatter`. Chart.js auto-invokes *any* function found while
resolving its `options` tree as a "scriptable option," passing its own internal context object instead of
the bar's value — this crashed every `Math.round()`/`toFixed()` call inside the formatter the moment the
plugin read it back, which froze the browser tab (screenshots timed out; the page's JS thread itself was
fine per direct console/JS introspection — the render loop was what wedged, not the page). Fixed by
stashing the formatter directly on the chart instance (`chart.$barValueLabelFormatter`), outside `options`
entirely, where Chart.js's resolver never looks. Full write-up in `architecture.md`'s Statistics section
and in memory as `flightlog_chartjs_scriptable_option_trap` — read before touching any Chart.js
scriptable-option-shaped code in this repo again.

### Personal context that shaped this round's framing

The pilot's daughter is due/was born around 29 Oct 2026 — much higher safety margins and much less time
to fly, going forward, by explicit choice. The 2024–2026 dip in flight frequency/length visible in the
real data is **not a regression to fix**; every stat and any coaching-style commentary going forward
should support confident, occasional, safety-first flying rather than push volume. Recorded in memory as
`flightlog_pilot_life_context` — read it before framing any future stats/coaching copy for this pilot.

### Mechanics gotchas hit (again) this session

- `pyproject.toml`'s version bump alone doesn't refresh `importlib.metadata`'s cached install info —
  `poetry install` must re-run (see [[flightlog-dev-server-workflow]]).
- Versioned static assets are `immutable` — once a `?v=` URL has been fetched once by the browser (even
  mid-debug, even in a since-closed tab), fixing the file's *content* requires *another* version bump
  before a fresh fetch happens anywhere, including brand-new tabs on the same profile. This round bumped
  `0.7.1`→`0.7.2` (bug fix) and `0.7.2`→`0.7.3` (the five coaching stats) for exactly this reason.

**Tests**: 182/182 passing project-wide (backend: `test_xc_progression_uses_distance_threshold_not_
category_name`, personal-bests/progression/zero-state assertions extended for the new fields). `ruff
check`/`ruff format --check` clean. No frontend test suite exists in this repo (per
`06-testing-conventions.md`), so the five frontend-only additions (currency tile, site-diversity note,
IGC coverage nudge, personal-best "set X ago") are covered by live-browser verification only, not
automated tests — re-verify visually if touched again.

**Verified live**: booted the real dev server (603 real flights), confirmed every new/changed endpoint via
`curl`, then — Claude in Chrome connected again this session — logged in via a real tab (token injected
into `localStorage`) and visually confirmed every item above renders correctly with zero console errors:
on-bar labels across every chart, the XC-progression bar chart showing the real 0%→33%→11-12% arc, the
site-diversity note ("62%... 34 sites"), the IGC coverage tile ("0.5% (3/603)"), the currency tile
("34 days since your last flight", rendered in amber), and "set 3.0 years ago"/"set 6.0 years ago" on the
personal-bests table. Screenshot capture was flaky partway through (CDP `Page.captureScreenshot` timing
out repeatedly, same transient extension/tab glitch documented in prior sessions) — confirmed via direct
`javascript_tool`/console introspection that the page itself was never frozen; screenshots did eventually
succeed on retry and show everything working.

**Not yet done**: `git add`/commit, a version tag, and pushing/deploying this round. Ask before doing so.

## Next Step

1. **Ask the pilot before committing/tagging/pushing this round** (they said "hold off" earlier in this
   session — that's a standing answer until they say otherwise, not just for that specific ask). If they
   say go: this whole round (bar labels + fix + five coaching stats) can land as a single `v0.7.3` release,
   since 0.7.1/0.7.2 were never pushed.
2. **v0.8 (public API + VidFactory) or v0.9 (sharing) are both fully planned** (`specs/006-public-api-
   vidfactory/`, `specs/007-sharing-public-readiness/`) and ready to implement next, in either order.
3. **XContest score import remains a backlog item** — see `features.md`'s Backlog entry.
4. **Config tuning on `v0.5`'s IGC parsing may still need iteration** — still unconfirmed whether the
   pilot's real thermal/glide figures looked right against what they remember of those flights.
5. **Decide on `specs/002-flight-log-ui`'s Phases 9–11** (`/contacts`, CSV export, remember-last-filters)
   — still open, not tied to any particular tag.

## Open Questions

- Whether the pilot wants an *average*-per-month variant alongside "Best by month"'s current max — a
  deliberate scope call, not an oversight; easy to add if asked (see `flightlog_feature_proposal_workflow`
  memory for how to run that kind of addition by them first).
- None blocking v0.8/v0.9 — both are ready to implement as planned, in either order.
- `features.md`'s backlog, unchanged this session: grant the deploy `gh` token `read:packages`, the
  `bootstrap_admin_email`/`bootstrap_admin_password` `set=%s`-style logging gap.

## Context

- **`specs/005-statistics/`** holds the complete spec/research/data-model/contracts/plan/tasks set for
  the original v0.7 scope. Every post-ship enhancement (bar labels, monthly extremes, XC progression,
  currency, site diversity, IGC coverage, PB recency) was implemented directly from pilot chat feedback,
  not through a new spec cycle — deliberately, given their size; if `/stats` grows much larger than this,
  consider a lightweight addendum spec rather than continuing to fold everything into
  `architecture.md`/`features.md` prose only.
- **`specs/006-public-api-vidfactory/` and `specs/007-sharing-public-readiness/`** hold complete spec sets
  for v0.8/v0.9 — ready whenever picked up.
- **A running theme worth remembering for whichever milestone comes next**: prior sessions repeatedly
  found that an existing doc or an old spec's prose had drifted from reality, and this session found a
  real *runtime* bug (the Chart.js scriptable-option trap) that only a live browser re-verification pass
  caught — the test suite could not have caught it, since it's a DOM/canvas rendering behavior with no
  backend surface. Live-boot + real-browser verification earns its keep again.
- **The dev server needs a restart after every backend edit** (no `--reload`). See
  [[flightlog-dev-server-workflow]].
- **The Windows-only WAL gotcha**: `data/flightlog.db`'s main file is often stale on its own — real,
  current data lives in the accompanying `.db-wal`/`.db-shm` sidecar files until SQLite checkpoints them.
  Copy all three together, or better, just point directly at the real path.

This file is a pointer, not a duplicate — `.ai/context/features.md`, `architecture.md`, and each
feature's own `specs/` folder have the detail.
