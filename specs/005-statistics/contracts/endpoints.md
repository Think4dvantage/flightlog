# API Contracts: Statistics

Same convention as every prior feature: a table, not full OpenAPI YAML. Every route requires
`Depends(get_current_user)` and is owner-scoped — there is no cross-owner concern here at all, since
every figure is computed only from the caller's own data (no `_get_own_<x>()` helper is needed; every
query is pre-filtered by `owner_id` at the aggregation level, not by fetching a row and checking it).

## `/api/stats` — `stats.py`

| Method | Path | Notes |
|---|---|---|
| GET | `/api/stats/totals` | Returns `TotalsOut` |
| GET | `/api/stats/time-breakdown` | Returns `TimeBreakdownOut` |
| GET | `/api/stats/distribution` | Returns `DistributionOut` |
| GET | `/api/stats/personal-bests` | Returns `list[PersonalBestOut]` |
| GET | `/api/stats/matrix/{dimension}` | `dimension ∈ site\|region\|glider\|harness\|category\|buddy`. Returns `DimensionYearMatrixOut`/`BuddyYearMatrixOut`. A `dimension` outside this set is `404 ENTITY_NOT_FOUND`, not `422` — it's a routing concern (which sub-resource), not a body-validation one, consistent with how this app already treats an invalid path segment elsewhere |
| GET | `/api/stats/launch-technique` | Returns `LaunchTechniqueOut` |
| GET | `/api/stats/igc-rollup` | Returns `IgcRollupOut` |
| GET | `/api/stats/progression` | Returns `ProgressionOut` |

Eight small, focused endpoints rather than one giant `GET /api/stats` blob — each is independently
cacheable client-side, independently fast to compute, and the `/stats` page can render each section as
its data arrives instead of blocking the whole page on the slowest aggregate.

## Ownership & validation rules applying to all of the above

- Every query is scoped to `current_user.id` directly in its `WHERE`/`JOIN` clause — there is no
  path-parameter id anywhere in this router to leak another owner's existence through, unlike every
  other router in the app.
- Zero-data cases (`NFR-003`) return the shape's natural zero/empty form (`total_flights: 0`, an empty
  `by_year` dict, `personal-bests: []`, etc.) with `200`, never a `404` or `500` — a brand-new account
  has valid, if uninteresting, statistics.
