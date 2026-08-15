# API Contracts: Public API & VidFactory Integration

Two distinct auth models in this one feature — say clearly, for every route, which one applies.

## `/api/keys` — `api_keys.py` (JWT-authenticated, pilot's own browser session)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/keys` | Lists the caller's own keys — `key_prefix` only, never `key_hash` or the plaintext |
| POST | `/api/keys` | Body: `name`, `scopes` (list), optional `expires_at`. **Response includes the full plaintext key exactly once** (`research.md`) — this is the only place it ever appears |
| POST | `/api/keys/{id}/revoke` | Sets `revoked_at`; effective immediately on the key's next use, per FR-002 |
| DELETE | `/api/keys/{id}` | Hard delete of the *management row* (name/scopes/metadata) once already revoked — does not un-revoke or resurrect access; kept separate from `revoke` the same way `gliders.py`'s retire/delete split already works in this app |

Every route here uses `Depends(get_current_user)` and `_get_own_key()`, same 404-not-403 pattern as
every other router.

## `/api/integration/v1` — `integration.py` (API-key authenticated, `X-API-Key` header)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/integration/v1/flights/{id}` | Requires `flights:read` scope. Flight metadata: date, launch/landing site names, duration, distance, computed altitude figures, glider/harness/category names. 404 if the flight doesn't exist or isn't owned by this key's owner — same non-leaking rule as every JWT-gated route |
| GET | `/api/integration/v1/flights/{id}/segments` | Requires `flights:read` scope. Returns `igc_segments` in the exact shape `architecture.md` already commits to (`research.md`) — `kind`, `start_offset_s`, `start_at`, `duration_s`, `alt_change_m`, `vertical_velocity_ms`, `glide_ratio`. 404 if no track, same as the JWT-gated equivalent |
| PUT | `/api/integration/v1/flights/{id}/links/{kind}/{external_id}` | Requires `flight_links:write` scope. Body: `url`, optional `label`. Create-or-replace, idempotent (`research.md`) |

Every route here uses a new `Depends(get_api_principal)` and `Depends(require_scope("..."))` — **not**
`get_current_user`. `_get_own_flight()`-equivalent scoping compares the flight's `owner_id` against
`principal.user.id`, not `current_user.id`, since there is no JWT-authenticated user in this request at
all.

## Ownership & validation rules applying to all of the above

- An API key request scopes every query by the key's owning pilot — never accepts or trusts any
  identifier the caller supplies for *whose* data to read beyond the flight id itself.
- A revoked or expired key is rejected before any route handler runs, at the `get_api_principal`
  dependency level — no route-specific logic needs to re-check this.
- A wrong-scope request is `403 PERMISSION_DENIED`, never `404` — this is a capability check, not an
  ownership check, matching how `require_admin` already draws this exact distinction elsewhere in this
  app (`specs/003-igc-ingest-analysis/contracts/endpoints.md`'s `POST /api/admin/reanalyze` precedent).
- `flight_links.url` is validated `http://`/`https://` only, in the Pydantic model, per
  `04-constraints.md`.
