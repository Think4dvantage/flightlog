# Research: Flight Log UI

## Historical import findings — how the read-only `/import` page gets its data

- **Decision**: Generate a small frozen constant module (`core/import_history.py`) once, by literally
  running `run_import(db, "olddata/Flugbuch.xlsx", owner_id, write=False)` and capturing its
  `ImportReport` fields programmatically — never by hand-transcribing the numbers already seen in this
  session's chat transcript or in `RESUME.md`. A new read-only endpoint serves that frozen structure.
- **Rationale**: The v0.2 import already happened in production; its findings are historical fact, not a
  live query. The workbook (`olddata/Flugbuch.xlsx`) is deliberately **not** shipped in the container
  image or mounted as a volume (see `RESUME.md` — it had to be `docker cp`'d in for the one-shot write
  and removed afterward), and it must be scrubbed from git history entirely before v0.8. A page that
  re-runs a dry-run against the workbook at request time would need the workbook present in the running
  container forever, which contradicts both facts. A one-time generated, committed constant has neither
  problem, and matches this project's existing pattern for one-time-verified data (`core/aliases.py`,
  `db.py`'s `_REGIONS` list) — a Python literal, not a database table, is proportionate to data that will
  never change again after this feature ships.
- **Alternatives considered**:
  - *Persist `ImportReport` to new DB tables, backfilled once.* Rejected — the project explicitly avoids
    materializing data "unless measurably needed" (see `architecture.md`'s "Tables that do NOT exist");
    a table that will only ever hold rows from one historical event is the same shape of unnecessary
    abstraction the constitution warns against ("don't create helpers or abstractions for one-time
    operations").
  - *Re-run the importer dry-run live, on each page load.* Rejected — requires the workbook to be
    reachable by the running server indefinitely, which conflicts with both the current deployment
    (workbook not present in the container) and the v0.8 requirement to remove it from git history.
  - *Hardcode the numbers already known from this session.* Rejected in favor of generating from source —
    this project's own `aliases.py` file explicitly documents catching two transcription typos by
    re-verifying against raw bytes instead of trusting a summarized view; the same discipline applies
    here.

## Flights list: search, sort, pagination, CSV export — client-side, not server-side

- **Decision**: `GET /api/flights` stays as-is (existing `year`/`category_id`/`glider_id`/`site_id`/
  `region_id` filters, unpaginated, sorted by date). The flights page fetches the pilot's full flight
  list once, then performs free-text search, additional sort orders, pagination, and CSV generation
  entirely in the browser.
- **Rationale**: The dataset is ~600 rows today and grows by a few hundred a year at most — trivially
  small for in-browser filtering/sorting with vanilla JS, no build step, and no added backend surface.
  Extending the API with `q`, arbitrary `sort`, `page`/`page_size` params, and a CSV response format
  would be real scope this feature doesn't need yet, and risks constraining `/api/flights` — the frozen
  contract `core/architecture.md` says other consumers (VidFactory, a future mobile app) will also use —
  around one UI's pagination scheme before there's a second consumer to design it against.
- **Alternatives considered**:
  - *Server-side search/sort/pagination now.* Rejected as premature for the current data scale; revisit
    if/when a consumer other than this UI needs it, or the flight count grows enough that NFR-001's
    responsiveness target is actually at risk.
  - *Server-side CSV export endpoint.* Rejected for the same reason — the full flight list is already in
    the browser after the initial fetch, so generating the file client-side needs no round-trip.

## Display names on the flights/detail views — resolved client-side, not embedded server-side

- **Decision**: `FlightOut` keeps returning IDs only (`launch_site_id`, `glider_id`, etc.), unchanged.
  The frontend fetches and caches the pilot's sites/gliders/harnesses/categories/buddies lists once (each
  already a small, existing `GET` endpoint) and joins them client-side to render names.
- **Rationale**: Keeps the machine contract stable — `architecture.md`'s stated differentiator is that
  the API is the product, and denormalizing display names into `FlightOut` for this one UI's convenience
  would bloat the response VidFactory and a future mobile app also consume. Reference lists are small
  (tens of rows each), so caching them client-side is cheap and avoids N+1-shaped joins entirely.

## Site coordinates: `coord_source` becomes server-enforced, not client-settable

- **Decision**: Neither `SiteCreate` nor `SiteUpdate` gains a client-settable `coord_source` field.
  Instead, `sites.py`'s create/update handlers set `site.coord_source = "manual"` themselves whenever the
  incoming request includes `lat` and/or `lon`.
- **Rationale**: `architecture.md` already documents the invariant — `coord_source` distinguishes a
  manual pin drop from the future IGC-median backfill (v0.4), and "the backfill never overwrites"
  a manual pin. That invariant has no code behind it yet: today `coord_source` isn't settable through
  either schema at all, and the importer explicitly writes `coord_source=None`. If a client could set
  `coord_source` directly, it could claim `"igc_median"` for a pin it typed in itself, which would let a
  later real IGC backfill silently overwrite a manual correction it should never touch. Server-setting it
  alongside `lat`/`lon` closes that gap the same way `owner_id` is never accepted from a request body.
- **Alternatives considered**: *Accept `coord_source` from the client, validated against an enum.*
  Rejected — there is no legitimate reason for a v0.3 client to ever send `"igc_median"`; that value is
  only ever written by v0.4's backfill job, which doesn't go through this HTTP surface.

## Map tiles for the site pin-drop map

- **Decision**: Use the public OpenStreetMap raster tile server (`tile.openstreetmap.org`) as Leaflet's
  base layer, with the standard `© OpenStreetMap contributors` attribution Leaflet's attribution control
  renders by default.
- **Rationale**: `main.py`'s CSP already allows this without any change — `img-src 'self' data: https:`
  permits an image from any HTTPS host, and Leaflet loads tiles as images, not scripts. This is a
  different mechanism from the CDN-script prohibition in `03-frontend-conventions.md` (which is about
  `script-src 'self'` blocking a `<script src="https://...">` tag); tile images were never blocked by
  that rule or that CSP directive. Self-hosting a raster tile set is real infrastructure (a tile
  generation/serving pipeline) disproportionate to a personal project's single pilot dropping pins on a
  few dozen sites.
- **Alternatives considered**: *Self-host tiles.* Rejected as disproportionate scope for this milestone;
  revisit only if OSM's usage policy ever becomes a real constraint (it is a free service with fair-use
  limits, fine at this traffic level).

## Vendored Leaflet is missing its marker/icon images — a pre-existing gap, not new scope

- **Finding**: `static/vendor/leaflet/leaflet.css` references `images/marker-icon.png`,
  `images/marker-icon-2x.png`, `images/marker-shadow.png`, `images/layers.png`, `images/layers-2x.png`,
  but `static/vendor/leaflet/` has no `images/` subfolder — only `leaflet.js` and `leaflet.css` were
  vendored in v0.1. Every Leaflet map today would render with a broken/missing marker icon.
- **Decision**: Vendor the missing five PNGs now, from the same Leaflet **1.9.4** release already pinned
  (`.ai/instructions/02-backend-conventions.md`'s dependency table) — not a newer version, to keep the
  vendored library internally consistent. They land under `static/vendor/leaflet/images/`, already
  covered by the existing `static/vendor/** -text` `.gitattributes` rule.
- **Rationale**: This is a prerequisite for FR-010 (site pin-drop), not new scope this feature invents —
  it's closing a gap the original v0.1 vendoring step left, discovered only now because this is the first
  feature to actually render a Leaflet map.

## No automated frontend tests for this feature

- **Decision**: This feature adds no Playwright (or other) frontend test suite. New pages are verified
  manually against a live boot (per this project's own standing instruction to test UI changes in a
  browser before reporting done). Only the two backend additions (the import-report endpoint, the
  `coord_source` enforcement) get `pytest` coverage.
- **Rationale**: `06-testing-conventions.md` states explicitly that there is "no Playwright setup yet"
  and that adding one later is "straightforward" — an intentional deferral, not an oversight. Introducing
  a frontend test framework as a side effect of this feature would be scope this plan wasn't asked to
  take on; six new pages is exactly the point at which it'd be worth a dedicated decision, not something
  to bundle in silently.

## New endpoint's response shape follows shipped routers, not the unused `{data, total}` doc pattern

- **Finding**: `.ai/instructions/07-api-conventions.md` documents collections as `{"data": [...], "total":
  N}`, but no shipped router actually does this — `flights.py`, `sites.py`, `gliders.py`, etc. all return
  a bare `list[...]` via `response_model=list[XOut]`. This is a pre-existing doc/code drift, not
  something this feature introduces.
- **Decision**: The new `GET /api/import-report` endpoint returns a single object (not a list) with the
  shape in `data-model.md`, matching the pattern every existing router actually uses. Not proposing to
  fix the `07-api-conventions.md` drift in this feature — it's orthogonal to flight-log-ui and touches
  every existing router if addressed, which is a separate decision for the user to make.

## Homepage copy is stale

- **Finding**: `static/index.html`'s `home.empty_hint` i18n string reads "The flight log lands in v0.2.
  Nothing to show yet." — accurate when v0.2 shipped API-only, stale now that the flight log UI exists.
- **Decision**: Update the string (and, once logged in, offer a direct link to `/flights`) as part of
  this feature's file changes. Not a redesign of the homepage — same page, corrected copy plus one link.
