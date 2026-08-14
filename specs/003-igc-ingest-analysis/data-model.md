# Data Model: IGC Ingest & Analysis

Three tables follow `architecture.md`'s "SQLite Tables" list by name (`igc_tracks`, `igc_segments`,
`site_observations`) — their columns below are this feature's first full definition of them. A fourth,
`igc_pending_uploads`, is a plan-level addition not named in `architecture.md` or `spec.md` (see
`research.md`'s "bulk-upload results persist" decision).

All four follow the same conventions as every other table (`architecture.md`): `String` UUID primary key
via `new_uuid`, every timestamp `UtcDateTime` via `utcnow`, `owner_id` a `ForeignKey("users.id",
ondelete="CASCADE")` — documentation only, since `PRAGMA foreign_keys` stays off; the ORM relationship's
`cascade="all, delete-orphan"` is what actually deletes children. New tables need no migration
(`Base.metadata.create_all()` is idempotent) — none of this feature's columns land on an *existing*
table, so `_run_column_migrations()` is not touched.

## `igc_tracks`

One per flight — a flight either has no track or exactly one (FR-004: a re-upload replaces it wholesale,
never accumulates a second row).

| Column | Type | Notes |
|---|---|---|
| `id` | String PK | |
| `owner_id` | String FK → `users.id`, not null, indexed | Present even though `flight_id` could reach it via a join — every other owner-scoped table in this app resolves ownership without a join, and this feature's `_get_own_track()` helper (`02-backend-conventions.md`'s pattern) should too |
| `flight_id` | String FK → `flights.id`, not null | `UniqueConstraint("flight_id")` — enforces the one-track-per-flight rule at the schema level, not just in application code |
| `original_filename` | String, not null | For display only |
| `sha256` | String, not null | `UniqueConstraint("owner_id", "sha256")` — the dedup key (FR-003); not globally unique, matching `flights.import_key`'s existing per-owner-not-global reasoning |
| `file_path` | String, not null | Relative path under `storage.igc_dir`, per architecture.md's `<owner_id>/<YYYY>/<sha256>.igc` layout |
| `duration_s` | Integer, nullable | From `takeoff_fix`/`landing_fix` |
| `distance_km` | Float, nullable | Sum of glide `track_length` (architecture.md's over-ground glide-ratio note applies to the ratio, not this raw sum) |
| `max_alt_igc_m` | Integer, nullable | From the track's fixes — kept distinct from `flights.max_alt_m`, which stays the hand-entered/legacy-import figure; the two are allowed to disagree, same spirit as `sites.elevation_m` vs `elevation_igc_m` |
| `alt_gain_igc_m` | Integer, nullable | Computed from the track, independent of `flights`' own derived `alt_gain_m` (`architecture.md`'s "Derived values" section) — this feature does not change how `flights.alt_gain_m` is computed on read |
| `thermal_count` | Integer, nullable | Post-filter count — descending spirals/wingovers already excluded (architecture.md rule 3) |
| `best_climb_ms` | Float, nullable | Best thermal *average* — never the instantaneous peak (architecture.md rule 6) |
| `peak_climb_ms` | Float, nullable | 10 s rolling-window peak; separate field, never conflated with `best_climb_ms` |
| `glide_ratio` | Float, nullable | Aggregate over-ground ratio (architecture.md rule 5) |
| `alt_source` | String, nullable | `press \| gnss` (architecture.md rule 2; exact field mapping pending `research.md`'s open item) |
| `track_simplified_json` | Text, nullable | A reduced-resolution point series (~500 points: offset-seconds, lat, lon, alt) — derived and regenerable, never the source of truth; backs both the map view and the barogram so neither needs a full re-parse of the raw file on ordinary viewing (`GET /track.geojson`, see `contracts/`) |
| `analyzer_version` | String, not null | Keys the re-analysis sweep (architecture.md rule 7 / `research.md`) |
| `analyzed_at` | UtcDateTime, not null | |
| `created_at`, `updated_at` | UtcDateTime | |

**Raw fixes are never stored** — `architecture.md`'s "Tables that do NOT exist" section already rules
out an `igc_fixes` table; this feature does not introduce one. The original `.igc` file on disk is the
only full-resolution source; `track_simplified_json` is the everyday-use derivative.

## `igc_segments`

Multiple per track — thermals, glides, and point markers.

| Column | Type | Notes |
|---|---|---|
| `id` | String PK | |
| `track_id` | String FK → `igc_tracks.id`, not null, indexed | |
| `kind` | String, not null | `thermal \| glide \| takeoff \| landing \| max_alt \| top_of_climb` (architecture.md's exact enum) |
| `start_offset_s` | Integer, not null | Seconds since takeoff — **the load-bearing field** for any future video-timeline consumer (architecture.md: "never return video-relative offsets from this service") |
| `start_at` | UtcDateTime, not null | Absolute time, so a track can still be aligned by a consumer that knows its own separate start time |
| `duration_s` | Integer, nullable | Null for the four point-marker kinds; set for `thermal`/`glide` |
| `alt_change_m` | Float, nullable | `thermal`/`glide` only |
| `vertical_velocity_ms` | Float, nullable | `thermal` only |
| `glide_ratio` | Float, nullable | `glide` only |

No `owner_id` — always reached through its parent `igc_tracks` row, which already carries one; adding a
second copy here would just be another spelling to keep in sync for no new query this feature needs.

## `site_observations`

One per takeoff or landing fix contributing to a site's automatic coordinate refinement (FR-013).

| Column | Type | Notes |
|---|---|---|
| `id` | String PK | |
| `site_id` | String FK → `sites.id`, not null, indexed | |
| `track_id` | String FK → `igc_tracks.id`, not null | Named in architecture.md's table list; also lets a re-analysis or a track replacement (FR-004) find and replace this track's prior observations rather than double-count them |
| `kind` | String, not null | `takeoff \| landing` — which end of the flight this fix is |
| `lat`, `lon` | Float, not null | |
| `alt_m` | Float, nullable | |
| `created_at` | UtcDateTime, not null | |

Not directly pilot-visible as its own view or endpoint — it only feeds the median recompute in
`core/site_backfill.py` (`research.md`). Replacing a track (FR-004) deletes and re-inserts this track's
two observation rows before any recompute, so a corrected upload doesn't leave a stale fix from the old
file permanently skewing a site's median.

## `igc_pending_uploads`

Plan-level addition (not in `spec.md`'s Key Entities, not in `architecture.md`'s table list) — persists a
bulk-uploaded file that didn't auto-attach, so the pilot's review queue survives a closed tab
(`research.md`).

| Column | Type | Notes |
|---|---|---|
| `id` | String PK | |
| `owner_id` | String FK → `users.id`, not null, indexed | |
| `sha256` | String, not null | `UniqueConstraint("owner_id", "sha256")` — a file already fully attached elsewhere, or already pending, is recognized rather than duplicated on a second bulk upload |
| `file_path` | String, not null | Same content-addressed layout as `igc_tracks.file_path` — the file is written to disk immediately on upload, whether or not it resolves right away |
| `original_filename` | String, not null | |
| `status` | String, not null | `needs_resolution \| rejected` |
| `reason` | String, nullable | Human-readable — e.g. the rejection reason, or which candidate flights tied |
| `candidate_flight_ids_json` | Text, nullable | For `needs_resolution`: the flight ids the bulk-match algorithm couldn't disambiguate between, so the resolution UI doesn't need to recompute candidates from scratch |
| `resolved_flight_id` | String FK → `flights.id`, nullable | Set once the pilot resolves it — the row is kept (not deleted) as a record of what happened to this upload, mirroring how `flights.import_key` rows are never deleted after the historical import either |
| `created_at`, `resolved_at` | UtcDateTime | `resolved_at` nullable until resolved |

Resolving a pending row (FR-011) is implemented as attaching its stored file to the chosen flight through
the same path as a single-flight upload (`POST /api/flights/{id}/igc`, `contracts/`) — reading the
already-on-disk bytes rather than requiring a re-upload — followed by marking this row resolved.

## Relationships summary

```
Flight 1──1 IgcTrack        (flight_id, unique — at most one track per flight)
IgcTrack 1──* IgcSegment    (track_id)
IgcTrack 1──* SiteObservation  (track_id — one per takeoff/landing fix it contributed)
Site 1──* SiteObservation   (site_id)
User 1──* IgcTrack, IgcPendingUpload  (owner_id)
Flight 0..1──* IgcPendingUpload  (resolved_flight_id, nullable — set only once resolved)
```

## Config additions

New `igc:` section in `config.yml` / `config.yml.example` (alongside the existing `storage:` section,
which already carries `igc_dir` and `max_igc_bytes` — those are unchanged by this feature):

```yaml
igc:
  parsing:
    min_time_for_thermal_s: <TBD — research.md>
    min_bearing_change_circling_deg: <TBD — research.md>
    min_time_for_glide_s: <TBD — research.md>
    max_time_between_thermals_s: <TBD — research.md>
```

Exact defaults are a Phase 1 task (`research.md`'s open item) — inspect the installed `libigc` package
rather than guess values into a config file that then silently disagrees with the library's own
sailplane-tuned defaults. `config.py` gets a matching `IgcParsingConfig`/`IgcConfig` pair of Pydantic
models, following `StorageConfig`/`SitesConfig`'s existing shape, and every resolved value is logged at
INFO on startup per `02-backend-conventions.md`.
