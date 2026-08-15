# Data Model: Public API & VidFactory Integration

Two new tables, following every existing table's conventions: `String` UUID primary key via `new_uuid`,
every timestamp `UtcDateTime` via `utcnow`, `owner_id` a `ForeignKey("users.id", ondelete="CASCADE")` —
documentation only, `PRAGMA foreign_keys` stays off, the ORM relationship's `cascade="all,
delete-orphan"` does the real deleting. New tables need no migration (`Base.metadata.create_all()`).

## `api_keys`

| Column | Type | Notes |
|---|---|---|
| `id` | String PK | |
| `owner_id` | String FK → `users.id`, not null, indexed | |
| `name` | String, not null | Pilot-chosen label (e.g. `"VidFactory"`) |
| `key_prefix` | String, not null, unique, indexed | First 8 chars of the secret portion — the lookup key; never secret itself |
| `key_hash` | String, not null | SHA-256 of the full key; never the reverse of `key_prefix`'s plaintext, never reversible (`research.md`) |
| `scopes` | String, not null | Space- or comma-separated scope names (e.g. `"flights:read flight_links:write"`) — a short enumerable list, not a generic permissions table (`spec.md`'s Assumptions) |
| `expires_at` | UtcDateTime, nullable | `NULL` = never expires (`research.md`'s doc-inconsistency resolution) |
| `last_used_at` | UtcDateTime, nullable | Updated best-effort on successful verification |
| `revoked_at` | UtcDateTime, nullable | Immediate kill switch — always wins over `expires_at`, per `spec.md`'s Edge Cases |
| `created_at` | UtcDateTime, not null | |

The plaintext key is never stored anywhere, at any point past the creation response
(`research.md`).

## `flight_links`

| Column | Type | Notes |
|---|---|---|
| `id` | String PK | |
| `flight_id` | String FK → `flights.id`, not null, indexed | |
| `kind` | String, not null | e.g. `"video"` — open-ended, not an enum column, so a future integration can introduce a new kind without a migration |
| `external_id` | String, not null | The external tool's own identifier (e.g. VidFactory's `project_id`) |
| `url` | String, not null | Validated `http://`/`https://` only, per `04-constraints.md`'s existing URL-validation rule |
| `label` | String, nullable | Pilot-facing display text (e.g. a video title) |
| `created_at`, `updated_at` | UtcDateTime | `updated_at` set on a `PUT`-replace (`research.md`'s idempotency decision) |

`UniqueConstraint("flight_id", "kind", "external_id")` — this triple is exactly what
`PUT /api/flights/{id}/links/{kind}/{external_id}` addresses; the constraint is what makes that route's
create-or-replace semantics enforceable at the schema level, not just in application code.

No `owner_id` on `flight_links` — reached through its parent `flights` row, which already has one;
adding a second copy would just be another spelling to keep in sync for no new query this feature needs
(same reasoning already applied to `igc_segments` not carrying its own `owner_id` in
`specs/003-igc-ingest-analysis/data-model.md`).

## Relationships summary

```
User 1──* ApiKey            (owner_id)
Flight 1──* FlightLink       (flight_id)
```

No relationship between `ApiKey` and `Flight` directly — an API key's access to a flight is enforced by
scope + the flight's own `owner_id` matching the key's `owner_id` at query time, not by a stored
association.
