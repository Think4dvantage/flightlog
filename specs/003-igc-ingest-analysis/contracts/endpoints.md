# API Contracts: IGC Ingest & Analysis

Same convention as `specs/001-core-data-import/contracts/endpoints.md`: a table, not full OpenAPI YAML —
the router file is the source of truth, per `architecture.md`. Every route requires
`Depends(get_current_user)` unless noted; every route is owner-scoped via `_get_own_<x>()`, returning 404
whether a row is missing or simply belongs to another pilot, never 403 (`04-constraints.md`).

## `/api/flights/{flight_id}/igc` — `igc.py`

| Method | Path | Notes |
|---|---|---|
| POST | `/api/flights/{flight_id}/igc` | Multipart, one file field. Create-or-replace (FR-004): 200 either way — there is no pilot-visible difference between "first track" and "replacing one" worth a 201/200 split. Rejects (422, `VALIDATION_FAILED`) an invalid/unparseable file or one over `storage.max_igc_bytes`, with a specific reason. Identical-file re-upload (same `sha256` already attached to this flight) is a no-op 200, not a re-analysis (FR-003) |
| GET | `/api/flights/{flight_id}/igc` | The track's summary/aggregates. 404 `ENTITY_NOT_FOUND` if the flight has no track yet — same code as "flight doesn't exist," per this app's existing not-yours-vs-missing convention, extended here to missing-vs-no-track since neither should be distinguishable from outside |
| GET | `/api/flights/{flight_id}/igc/segments` | List of `igc_segments` rows for this flight's track, ordered by `start_offset_s` |
| GET | `/api/flights/{flight_id}/igc/track.geojson` | `LineString` geometry, `[lon, lat, alt_m]` per coordinate (GeoJSON's optional third position element), plus `properties.offsets_s` — a parallel array of seconds-since-takeoff per point. One response serves both the map (coordinates) and the barogram (`offsets_s` + each coordinate's altitude) without a second endpoint or a raw-file re-parse. Derived from `igc_tracks.track_simplified_json`, not the raw file |
| DELETE | `/api/flights/{flight_id}/igc` | Detaches the track (FR-012): deletes the `igc_tracks` row, its `igc_segments`, and its `site_observations`, then re-triggers the affected site(s)' coordinate recompute (which may drop back below the ≥3 threshold and clear `coord_source`/`lat`/`lon` if this was one of only 3) |

## `/api/igc/bulk` and `/api/igc/pending` — `igc.py`

| Method | Path | Notes |
|---|---|---|
| POST | `/api/igc/bulk` | Multipart, multiple file fields. Synchronous (`research.md`) — analyzes every file in the request, auto-attaches unambiguous matches, writes everything else to `igc_pending_uploads`. Response: per-file outcome (`auto_attached` with the `flight_id`, `needs_resolution` with `candidate_flight_ids`, or `rejected` with a reason) — FR-009 |
| GET | `/api/igc/pending` | Lists this pilot's unresolved `igc_pending_uploads` rows (`status != null`, i.e. everything not yet resolved) — the review queue a pilot returns to after closing the bulk-upload response (`research.md`) |
| POST | `/api/igc/pending/{id}/resolve` | Body: `{"flight_id": "..."}`. Attaches the pending row's already-stored file to that flight (same path as the single-flight `POST`, reading stored bytes rather than requiring re-upload), marks the row resolved — FR-011 |
| DELETE | `/api/igc/pending/{id}` | Dismisses a pending row without attaching it anywhere (e.g. a rejected file the pilot has no fix for, or a duplicate they don't want) |

## `/api/admin/reanalyze` — `igc.py`

| Method | Path | Notes |
|---|---|---|
| POST | `/api/admin/reanalyze` | `Depends(require_admin)`, not `get_current_user` — 403 for a non-admin pilot account, not 404 (this is a capability check, not an ownership check, so the existing not-yours-vs-missing 404 convention doesn't apply here). Re-processes every `igc_tracks` row whose `analyzer_version` differs from the running build's, from each track's stored file. Response: count re-analyzed |

## Ownership & validation rules applying to all of the above

- `owner_id` is set from `current_user.id`, never accepted from a request body — same rule as every
  other router (`04-constraints.md`).
- A flight-scoped route (`/api/flights/{flight_id}/igc*`) 404s exactly like every other
  `_get_own_flight()`-gated route if `flight_id` doesn't exist or belongs to another pilot, before it
  even looks at the uploaded file.
- Every list endpoint returns only the caller's own rows.
- File-size and parse-validity rejections are `422 VALIDATION_FAILED` with the specific reason in
  `details`, not a generic `500` — per `04-constraints.md`'s "never swallow an exception" rule, a corrupt
  upload must produce a typed, diagnosable error, never a flight that silently ends up with no track.
