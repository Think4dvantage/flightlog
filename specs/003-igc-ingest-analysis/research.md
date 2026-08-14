# Research: IGC Ingest & Analysis

Confirms the IGC design already recorded in `.ai/context/architecture.md`'s "IGC analysis" section
against the real `libigc` package (not just the prose), and resolves the technical unknowns `spec.md`
deliberately left open (upload mechanics, bulk-review persistence, config shape).

## Decision: `libigc` 1.2.0 is current, and its core parsing API matches architecture.md

- **Decision**: Use `libigc>=1.2.0,<2.0.0` — the pin already declared under the `igc` extra in
  `pyproject.toml` — with no change.
- **Rationale**: Re-verified against the PyPI JSON API (`pypi.org/pypi/libigc/json` → `"version":
  "1.2.0"`) per `02-backend-conventions.md`'s dependency-freshness rule; no drift since the extra was
  declared. The package's GitHub README (`surajmandalcell/libigc`, `master` branch) confirms the core
  shape architecture.md's algorithm section assumes: `Flight.create_from_file(path)` as the entry point;
  `flight.valid` / `flight.notes` for rejection; `flight.thermals` / `flight.glides` / `flight.fixes` /
  `flight.takeoff_fix` / `flight.landing_fix`; `Thermal.time_change()` / `.alt_change()` /
  `.vertical_velocity()`; `Glide.time_change()` / `.speed()` / `.alt_change()` / `.glide_ratio()` /
  `.track_length`; each `GNSSFix` carries `timestamp`, `lat`, `lon`, `alt`, `ground_speed`, `bearing`,
  `bearing_change_rate`, `flying`, `circling`.
- **Alternatives considered**: None — this is the dependency already chosen and declared in a prior
  session; this research re-verifies it rather than re-deciding it.

## Resolved (T005): both open items checked against the installed 1.2.0 source, not just the README

- **Altitude source: `libigc` already resolves this itself — do not reimplement architecture.md's
  ">50% non-None" heuristic.** `GNSSFix.press_alt` / `.gnss_alt` do both exist on every fix, parsed
  directly from each B-record's two fixed-width altitude fields — but they are **floats, never `None`**
  (a logger with no baro sensor typically writes literal zeros, not a missing field), so a
  "non-None" count wouldn't do anything useful against real data anyway. `libigc.core.Flight` already
  runs a proper validity check on *both* streams during construction (`_check_altitudes()`: per-fix
  rate-of-change limits, absolute min/max bounds, and a minimum-average-change check to catch a sensor
  stuck reporting a constant value) and sets `press_alt_valid` / `gnss_alt_valid` booleans, then:
  `alt_source = PRESSURE if press_alt_valid else (GNSS if gnss_alt_valid else <flight invalid>)`. If
  *neither* is valid, `flight.valid` is set `False` and construction returns early — so architecture.md
  rule 1's "reject `not flight.valid`" already covers the "no usable altitude at all" case for free.
  **Decision**: `core/igc.py` reads `flight.alt_source` directly for the persisted `alt_source` column;
  it does not recompute a source selection from the raw fixes itself. Architecture.md's rule 2 should be
  corrected to say this at `sync.md` time (Phase 8 / T035) — the current wording describes a heuristic
  this project would have had to invent redundantly, over one the chosen library already implements more
  rigorously.
- **`FlightParsingConfig`'s real shape does not match the four names architecture.md guessed.** The
  installed 1.2.0 source (`flight_parsing_config.py`) declares many *file-validity* parameters
  (`min_fixes`, `max_seconds_between_fixes`, `max_alt`, `min_alt`, etc.) that are not this feature's
  concern to expose, plus exactly **three** thermal-detection parameters — and no separate glide-tuning
  parameter exists at all:
  | Architecture.md's guess | Real parameter | Default | Meaning |
  |---|---|---|---|
  | `min_bearing_change_circling_deg` | `min_bearing_change_circling` | `6.0` (deg/s) | Minimum bearing-change rate to enter a thermal |
  | *(not anticipated)* | `min_time_for_bearing_change` | `5.0` (s) | Minimum time between fixes before a bearing-change rate is computed at all — exists specifically to avoid noise from fixes that are too close together in time |
  | `min_time_for_thermal_s` | `min_time_for_thermal` | `60.0` (s) | Minimum circling duration to count as a thermal, not noise |
  | `min_time_for_glide_s` | **does not exist** | — | Glides are simply "the gap between two thermals" (`glide.py`'s own docstring); there is no separate minimum-duration knob for them |
  | `max_time_between_thermals_s` | **does not exist** | — | No such parameter anywhere in the class |
  **Decision**: `config.yml`'s `igc.parsing:` block exposes exactly these three real parameter names,
  at their real library defaults, not the four architecture.md guessed. `create_from_file` takes a
  **config class**, not an instance (`config = config_class()` is called internally) — `core/igc.py`
  builds a small `FlightParsingConfig` subclass from `config.yml`'s resolved values and passes the
  subclass, not an instance, as `create_from_file`'s `config_class=` argument.
- **`create_from_file` takes a filesystem path, not bytes.** Confirms (does not change) the already-
  planned storage design: an uploaded file's bytes are hashed and written to content-addressed disk
  storage *before* `core/igc.py` ever calls into `libigc`, never handed to it as an in-memory buffer.

## Decision: file upload uses FastAPI's `UploadFile`, whole-body-in-memory, not streamed

- **Decision**: `python-multipart`-backed `UploadFile` (FastAPI's standard file-upload mechanism),
  reading the full contents into memory before hashing and writing to disk, gated by
  `storage.max_igc_bytes` (already `5 MiB` in `config.yml.example`).
- **Rationale**: This is the first file-upload endpoint in the app — no existing pattern to follow. A
  5 MiB ceiling is small enough that reading the whole file into memory (to compute its sha256 and hand
  it to `libigc`, which itself expects a file path or file-like object, not a stream) is simpler and
  fully sufficient; a genuinely large multi-file bulk upload still processes one file at a time; sizing
  is enforced before any parsing work happens (reject oversized bodies immediately, per FR-002's spirit
  of a clear, immediate rejection reason). `python-multipart` is already a transitive dependency of
  FastAPI's form/file support and needs no separate version decision.
- **Alternatives considered**: Streaming to a temp file first. Rejected as unnecessary complexity for a
  5 MiB ceiling — the whole point of a small `max_igc_bytes` is that in-memory handling stays cheap.

## Decision: CPU-bound analysis stays off the event loop by keeping every route a sync `def`, not by wrapping it in `asyncio.to_thread`

- **Decision**: Every route in `api/routers/igc.py` is a plain sync `def`, matching every other
  router already in this app (`flights.py`, `sites.py`, etc., are 100% sync `def` — there is no
  `async def` route handler anywhere in the codebase today). `core/igc.py`'s `analyze()` is called
  directly, with no `asyncio.to_thread` wrapper.
- **Rationale**: `04-constraints.md`'s rule ("never call IGC parsing directly from an `async def`
  handler") is about the specific failure mode of blocking the event loop from inside an `async def`
  — FastAPI already runs a sync `def` path function in its own worker threadpool automatically (the
  same mechanism `02-backend-conventions.md` already relies on for `get_db` and the auth dependencies
  being sync), so the underlying concern is satisfied by construction without introducing this app's
  first `async def` route and a second offloading mechanism alongside it. `UploadFile.file` (the
  underlying `SpooledTemporaryFile`) supports a plain sync `.read()`, so nothing about file upload
  itself requires `async def` either.
- **Alternatives considered**: An `async def` handler with `await asyncio.to_thread(analyze, ...)`,
  literally as `04-constraints.md`'s example shows. Rejected as unnecessary complexity that would also
  make this feature's routes the only asynchronous ones in the app — the constraint the example is
  guarding against doesn't arise if the handler is never `async def` in the first place.

## Decision: bulk-upload results persist server-side as pending rows, not just in the HTTP response

- **Decision**: A new table (`igc_pending_uploads` — see `data-model.md`) stores every bulk-uploaded file
  that didn't auto-attach (ambiguous match or rejected), with the file itself already written to
  content-addressed storage. The bulk endpoint's response is a summary of what happened; the pending
  list is then a normal `GET`-able resource the pilot can return to.
- **Rationale**: `spec.md`'s FR-010/FR-011 require showing every file's outcome and letting the pilot
  resolve ambiguous ones — for a realistic backfill batch (the historical importer's own precedent is
  ~600 flights), holding that state only in one HTTP response risks losing it to a closed tab or a
  refresh, which would mean re-running analysis on every file again. This is a plan-level addition beyond
  `spec.md`'s three named entities (IGC Track, Track Segment, Site Observation) — the spec deliberately
  stayed at the FR level ("the pilot can see outcome... and resolve later"); how that persists is exactly
  the kind of decision `plan.md` is for.
- **Alternatives considered**: Response-only, client holds state (e.g. in browser storage). Rejected —
  fragile against a lost tab, and every other durable-review pattern in this app (the `/import` findings
  page) is server-backed, not client-cached.

## Decision: bulk upload is a synchronous HTTP request, not a background job

- **Decision**: `POST /api/igc/bulk` processes every uploaded file in the same request/response cycle
  (each file's analysis still individually offloaded via `asyncio.to_thread`), returning the full outcome
  list when done. No job queue, no polling endpoint.
- **Rationale**: `04-constraints.md` rules out this app carrying scheduler/collector-style infrastructure
  outright ("No InfluxDB, no scheduler, no collectors"), and nothing resembling a background-job runner
  exists anywhere in the codebase today — `core/importer.py`, the closest precedent for a many-record
  one-shot operation, is itself fully synchronous. A single pilot's realistic batch sizes (a folder of a
  few dozen to a few hundred historical files, uploaded rarely) make a long-held HTTP request acceptable;
  documented as a risk in `plan.md` rather than solved with new infrastructure this feature doesn't need.
- **Alternatives considered**: A job queue with a status-polling endpoint. Rejected as infrastructure
  this single-pilot tool has never needed anywhere else, for a feature that runs rarely.

## Decision: site coordinate backfill recomputes on every new observation, not as a separate sweep

- **Decision**: After a track successfully attaches, `core/site_backfill.py` inserts the takeoff/landing
  `site_observations` rows for that track, then immediately re-checks the affected site(s): if
  `coord_source` is not `"manual"` and observation count has reached the ≥3 threshold architecture.md
  already sets, recompute the median and write `lat`/`lon`/`coord_source="igc_median"`/
  `coord_accuracy_m`.
- **Rationale**: Keeps the whole feature free of any new scheduled/batch job (consistent with the
  synchronous-bulk decision above) and makes the behavior trivially idempotent — recomputing a median
  from the same observation set twice is a no-op.
- **Alternatives considered**: A periodic sweep job. Rejected for the same reason as above — no
  scheduler infrastructure exists or is wanted.

## Decision: re-analysis sweep is a full pass filtered by `analyzer_version`, not a partial/targeted API

- **Decision**: `POST /api/admin/reanalyze` re-processes every `igc_tracks` row whose stored
  `analyzer_version` does not match the current build's constant, from each track's already-stored file
  (never re-uploaded). No request body / filtering options.
- **Rationale**: Matches architecture.md's stated mechanism exactly ("`analyzer_version` is persisted
  per track. A re-analysis sweep keys on it.") and `spec.md`'s P3 acceptance criteria ask for nothing
  more granular. A single pilot's full track count is small enough (bounded by total flight count) that
  a full filtered sweep is cheap; per-track/date-range filtering would be speculative scope.
- **Alternatives considered**: Accepting a flight-id list or date range to reanalyze a subset. Rejected
  as unrequested complexity — nothing in `spec.md` asks for partial re-analysis.
