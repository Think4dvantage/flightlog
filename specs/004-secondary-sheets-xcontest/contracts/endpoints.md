# API Contracts: Secondary Sheets & XContest Import

Same convention as every prior feature's contracts file: a table, not full OpenAPI YAML — the router
file is the source of truth. Every route requires `Depends(get_current_user)`; every route is
owner-scoped via `_get_own_<x>()`, 404 whether a row is missing or belongs to another pilot, never 403.

## `/api/hikes` — `hikes.py`

| Method | Path | Notes |
|---|---|---|
| GET | `/api/hikes` | List, owner-scoped. Filter: `linked` (bool) — has/doesn't have a `flight_id` |
| GET | `/api/hikes/{id}` | |

Import-and-view only per `spec.md`'s Out of Scope — no `POST`/`PUT`/`DELETE` in this feature.

## `/api/groundhandling` — `groundhandling.py`

| Method | Path | Notes |
|---|---|---|
| GET | `/api/groundhandling` | List, owner-scoped |
| GET | `/api/groundhandling/{id}` | |

Import-and-view only, same as `hikes`.

## `/api/tandem-flights` — `tandem_flights.py`

| Method | Path | Notes |
|---|---|---|
| GET | `/api/tandem-flights` | List, owner-scoped |
| GET | `/api/tandem-flights/{id}` | |

Import-and-view only, same as `hikes`.

## `/api/goals` — `goals.py`

| Method | Path | Notes |
|---|---|---|
| GET | `/api/goals` | Filter: `status` |
| POST | `/api/goals` | `import_key` never accepted from the request body — same rule as `flights` |
| GET | `/api/goals/{id}` | |
| PUT | `/api/goals/{id}` | |
| DELETE | `/api/goals/{id}` | |
| POST | `/api/goals/{id}/mark-done` | Sets `status = "done"` — a dedicated action, not a bare `PUT` field
  edit, mirroring `gliders.py`'s `POST /{id}/retire` pattern for a status transition that's really an
  event, not an ordinary field update |

Full CRUD, per `spec.md`'s FR-006 — the one type in this feature that behaves like every other
owner-scoped domain entity already in the app.

## `/api/xcontest-import` — `xcontest_import.py`

| Method | Path | Notes |
|---|---|---|
| POST | `/api/xcontest-import` | Multipart, one file field (the "My Flights" JSON export). Matches every entry against untracked-by-this-import flights by date; unambiguous matches attach `xc_official_score`/`_type`/`_url` immediately. Response: per-entry outcome (`attached` with the `flight_id`, `needs_resolution` with candidate flight ids, or `unmatched`) — same response shape as `specs/003-igc-ingest-analysis/contracts/endpoints.md`'s `BulkUploadOutcomeOut`, reused rather than redesigned |
| GET | `/api/xcontest-import/pending` | Lists this import's unresolved entries — same persisted-review-queue pattern as `igc_pending_uploads` (`specs/003-igc-ingest-analysis`), not held only in the POST response |
| POST | `/api/xcontest-import/pending/{id}/resolve` | Body: `{"flight_id": "..."}`. Attaches the pending entry's score/type/url to the chosen flight |
| DELETE | `/api/xcontest-import/pending/{id}` | Dismisses a pending entry without attaching it anywhere |

The exact shape of what an "unmatched" or "pending" entry carries (which fields from the source JSON are
shown to help the pilot pick the right flight) depends on `research.md`'s still-open schema question —
finalized once a real sample export is read, per that section's resolution plan.

## Ownership & validation rules applying to all of the above

- `owner_id` is set from `current_user.id`, never accepted from a request body.
- `flights.xc_official_url` is validated as `http://`/`https://` only, in the Pydantic model, per
  `04-constraints.md`'s URL-validation rule (same rule already applied to `media_links.url` /
  `tracker_links.url`).
- File-parse rejections (an XContest export that isn't valid JSON, or a `Fitnessprogramm`-shaped import
  file that fails to parse) are `422 VALIDATION_FAILED` with a specific reason, never a generic `500`.
