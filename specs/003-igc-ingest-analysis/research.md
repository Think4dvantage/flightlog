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

## Open: two architecture.md claims not confirmed by the README — verify against the installed package before implementing

- **`press_alt` / `gnss_alt` per-fix fields.** Architecture.md's altitude-source rule (`prefer press_alt
  when >50% of fixes carry a non-None baro value, else gnss_alt`) assumes each fix exposes both readings
  separately. The README only documents a single `GNSSFix.alt` plus a flight-level `alt_source` (`PRESS`
  or `GNSS`) — it's unclear from the README alone whether `alt_source` is libigc's own resolved choice
  (in which case architecture.md's per-fix comparison may be redundant with what the library already
  does) or whether `press_alt`/`gnss_alt` exist on the fix object but are simply undocumented in the
  README. **Resolve by inspecting the installed package's actual source/docstrings once the `igc` extra
  is installed during implementation** — this is a Phase 1 (backend prerequisites) task, not a blocker
  for this plan, since either outcome is a small, contained change to `core/igc.py`.
- **`FlightParsingConfig` and its tuning parameter names.** Architecture.md names four specific
  parameters (`min_time_for_thermal_s`, `min_bearing_change_circling_deg`, `min_time_for_glide_s`,
  `max_time_between_thermals_s`) as `config.yml`-tunable. The README does not document this class at
  all. **Resolve the same way** — inspect the installed package before finalizing `config.yml.example`'s
  `igc.parsing:` key names and defaults; `data-model.md`/this plan use architecture.md's names as the
  working assumption, flagged here so a mismatch is expected to surface early in Phase 1, not discovered
  mid-feature.

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

## Decision: CPU-bound analysis runs via `asyncio.to_thread`, never inline in an `async def` handler

- **Decision**: Every call into `core/igc.py`'s parse/analyze function from an API route goes through
  `await asyncio.to_thread(analyze, ...)`.
- **Rationale**: `04-constraints.md`'s Performance section states this exact rule for IGC parsing by
  name — a large track's analysis takes seconds, and calling it directly from `async def` stalls every
  other request in the process. Non-negotiable, not a new decision so much as applying an existing one.

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
