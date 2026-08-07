# API Contracts: Core Data & Excel Import

Deliberately **not** full OpenAPI YAML, matching this project's own stated convention in
`architecture.md`: *"Routes are not enumerated here beyond the prefix — read the router file, which is
the source of truth."* FastAPI generates the real OpenAPI schema from the routers themselves; a
hand-maintained YAML copy would drift the day someone adds a query parameter. This table is the
implementation checklist for `tasks.md`, not a contract to keep in sync by hand afterward.

The one-shot import (`python -m flightlog.core.importer`) is a CLI entry point, not an HTTP endpoint —
see `01-project-overview.md`'s repository layout. No route is added for it in this feature.

Every route below requires `Depends(get_current_user)` unless noted. Every list/get/update/delete is
owner-scoped via each router's own `_get_own_<entity>()` helper. **That helper returns 404 whether the
row is missing or simply belongs to another pilot — never a 403.** A 403 would confirm the id exists,
which is the same existence-leak class `04-constraints.md` calls out for the buddy-link endpoint;
`06-testing-conventions.md`'s coverage table states it as a hard requirement. `02-backend-conventions.md`
is corrected to match as part of this feature — its `_get_own_glider` sample previously showed a 403 for
"not yours," which was the outlier, not the rule. Collections return `{"data": [...], "total": N}`;
single entities return the object directly, per `07-api-conventions.md`.

## `/api/regions` — `regions.py`

| Method | Path | Notes |
|---|---|---|
| GET | `/api/regions` | Not owner-scoped — shared list, same result for every pilot |

## `/api/sites` — `sites.py`

| Method | Path | Notes |
|---|---|---|
| GET | `/api/sites` | Filters: `is_launch`, `is_landing`, `region_id` |
| POST | `/api/sites` | |
| GET | `/api/sites/{id}` | |
| PUT | `/api/sites/{id}` | |
| DELETE | `/api/sites/{id}` | Only if no flight references it — otherwise `409 CONFLICT` |
| PUT | `/api/sites/{id}/prefs` | Upserts the caller's `user_site_prefs` row for that site |

## `/api/gliders` — `gliders.py`

| Method | Path | Notes |
|---|---|---|
| GET | `/api/gliders` | Filter: `include_retired` (default `false`) |
| POST | `/api/gliders` | |
| GET | `/api/gliders/{id}` | |
| PUT | `/api/gliders/{id}` | |
| POST | `/api/gliders/{id}/retire` | Sets `retired_at`; never a hard delete once a flight references it |
| DELETE | `/api/gliders/{id}` | Only if no flight references it |

## `/api/harnesses` — `harnesses.py`

Same shape as `/api/gliders`.

## `/api/categories` — `categories.py`

| Method | Path | Notes |
|---|---|---|
| GET | `/api/categories` | Filter: `include_archived` (default `false`) |
| POST | `/api/categories` | |
| GET | `/api/categories/{id}` | |
| PUT | `/api/categories/{id}` | |
| PUT | `/api/categories/reorder` | Body: ordered list of ids → rewrites `sort_order` |
| POST | `/api/categories/{id}/archive` | Sets `archived_at`; a flight can still reference it |
| DELETE | `/api/categories/{id}` | Only if no flight references it |

## `/api/buddies` — `buddies.py`

| Method | Path | Notes |
|---|---|---|
| GET | `/api/buddies` | |
| POST | `/api/buddies` | |
| GET | `/api/buddies/{id}` | |
| PUT | `/api/buddies/{id}` | |
| DELETE | `/api/buddies/{id}` | Never touches `linked_user_id`'s account |
| POST | `/api/buddies/{id}/link` | Body: contact info to link against. **Always 202**, regardless of whether it matches a registered pilot — FR-007 / the enumeration-safety rule in `04-constraints.md` |
| POST | `/api/buddies/{id}/link/accept` | Called by the *linked* pilot, not the buddy's owner |
| POST | `/api/buddies/{id}/link/decline` | Same caller as accept |

## `/api/flights` — `flights.py`

| Method | Path | Notes |
|---|---|---|
| GET | `/api/flights` | Filters: `year`, `category_id`, `glider_id`, `site_id`, `region_id`; this feature ships the raw filtering capability — sort/pagination polish is v0.3's UI concern, not blocking here |
| POST | `/api/flights` | `import_key` is never accepted from the request body — server-generated `NULL` for API-created flights |
| GET | `/api/flights/{id}` | Response includes computed `alt_gain_m` / `site_drop_m` / `total_descent_m` (never stored) |
| PUT | `/api/flights/{id}` | |
| DELETE | `/api/flights/{id}` | |

## Ownership & validation rules applying to all of the above

- `owner_id` is set from `current_user.id` in every `POST`; a value supplied in the body is ignored
  (FR-018 / `04-constraints.md`).
- A cross-owner reference (e.g. creating a flight with another pilot's `glider_id`) is rejected with
  `404 ENTITY_NOT_FOUND` — same as if the referenced row didn't exist, never a `403`.
- Every list endpoint returns only the caller's own rows except `GET /api/regions`.
