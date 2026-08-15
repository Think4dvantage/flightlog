# API Contracts: Sharing & Public Readiness

## `/api/flights/{id}` — `flights.py` (existing router, one new field)

| Method | Path | Notes |
|---|---|---|
| PUT | `/api/flights/{id}` | `visibility` becomes an accepted field on the existing update body — no new route, this already-owner-scoped, already-JWT-gated endpoint just accepts one more field |

## `/api/public` — `public.py` (**unauthenticated by design** — no `Depends(get_current_user)` anywhere in this file, per `research.md`'s `health.py`-precedent decision, rate-limited via `slowapi`)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/public/flights/{id}` | 404 unless the flight's `visibility` is `unlisted` or `public` — a private flight's id returns exactly the same 404 shape as an id that doesn't exist at all, never a distinguishing signal |
| GET | `/api/public/profiles/{user_id}` | 404 unless that user has `public_profile_enabled = True`. Returns display name + a list of that user's `public`-visibility flights only (never `unlisted` — an unlisted flight is reachable only by its own direct link, never listed anywhere, including its own owner's public profile) |

## `/public/flights/{id}` and `/public/profiles/{user_id}` — `pages.py` (existing router, new unauthenticated page routes)

| Method | Path | Notes |
|---|---|---|
| GET | `/public/flights/{id}` | Serves a page that calls the public API above — no JWT, no redirect-to-login the way every existing authenticated page route implies |
| GET | `/public/profiles/{user_id}` | Same |

Distinct URL prefix (`/public/...`) from the existing authenticated `/flights/{id}` page, so a shared
link is unambiguous about which surface it's hitting and CSP/caching rules can differ cleanly between
the two if ever needed.

## Ownership & validation rules applying to all of the above

- `GET /api/public/*` never accepts or requires any credential — a request carrying a valid JWT for a
  *different* pilot must be treated identically to no credential at all; this surface never uses the
  caller's own identity for anything.
- Every `/api/public/*` route is rate-limited by `slowapi`, independently of the authenticated surface
  (`research.md`) — a rate-limited response is a typed `429`, following this app's existing error-
  envelope shape (`{"error": {"code": ..., "message": ..., "details": {}}}`), not `slowapi`'s own default
  response shape.
- A visibility change via `PUT /api/flights/{id}` takes effect on the very next `GET
  /api/public/flights/{id}` — no cache header on the public route implies staleness beyond normal HTTP
  caching semantics already in place elsewhere.
