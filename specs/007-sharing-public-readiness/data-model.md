# Data Model: Sharing & Public Readiness

One new column on an existing table, one new column on another existing table — both need
`_run_column_migrations()`'s idempotent `ALTER TABLE` guard, since `flights` and `users` already exist.
No new tables.

## `flights` — one new column

| Column | Type | Notes |
|---|---|---|
| `visibility` | String, not null, default `"private"` | `private`\|`unlisted`\|`public` (`research.md` — plain string, matching every other enum-shaped column already in this schema) |

## `users` — one new column

| Column | Type | Notes |
|---|---|---|
| `public_profile_enabled` | Boolean, not null, default `False` | Opt-in only (`spec.md` FR-005). No new "profile" table — the profile *is* the user row plus their public flights, computed at request time, nothing separately stored |

No new `profile_slug`/username column (`research.md`) — the public profile URL uses the existing
`users.id`.

## Starter category seed data (not a table — a Python constant, mirroring `core/aliases.py`'s existing pattern)

| `name` | `is_hike_fly` | `is_training` |
|---|---|---|
| `Thermal` | `False` | `False` |
| `Soaring` | `False` | `False` |
| `XC` | `False` | `False` |
| `Hike&Fly` | `True` | `False` |
| `Sled run` | `False` | `False` |

Written through the exact same `FlightCategory` creation path a pilot's own manual category creation
already uses (`POST /api/categories`) — not a special-cased insert, so every existing validation and
`sort_order` assignment behavior applies unchanged. `users.seeded_at` is set to the current time
immediately after, guarding this from ever running twice for the same account (`research.md`).

## Relationships summary

No new tables, no new foreign keys. `flights.visibility` and `users.public_profile_enabled` are both
plain columns on tables that already exist and already have every relationship they need.

```
User.public_profile_enabled  (existing table, +1 column)
Flight.visibility            (existing table, +1 column)
```
