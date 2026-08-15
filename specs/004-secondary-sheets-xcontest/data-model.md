# Data Model: Secondary Sheets & XContest Import

Four new tables, following every existing table's conventions (`architecture.md`): `String` UUID primary
key via `new_uuid`, every timestamp `UtcDateTime` via `utcnow`, `owner_id` a
`ForeignKey("users.id", ondelete="CASCADE")` — documentation only, `PRAGMA foreign_keys` stays off, the
ORM relationship's `cascade="all, delete-orphan"` does the real deleting. New tables need no migration
(`Base.metadata.create_all()` is idempotent). Three columns land on the existing `flights` table — those
need `_run_column_migrations()`'s idempotent `ALTER TABLE` guard, since `flights` already exists.

## `hikes`

| Column | Type | Notes |
|---|---|---|
| `id` | String PK | |
| `owner_id` | String FK → `users.id`, not null, indexed | |
| `import_key` | String, nullable | `"fitnessprogramm:<row>"`; `UniqueConstraint("owner_id", "import_key")` — `NULL` for a hike entered directly, matching `flights.import_key`'s existing shape |
| `hike_date` | Date, not null | Source `Datum` |
| `start_place` | String, not null | Source `Start` |
| `destination_place` | String, not null | Source `Ziel` |
| `ascent_m` | Integer, nullable | Source `steigung` |
| `descent_m` | Integer, nullable | Source `gefälle` |
| `distance_km` | Float, nullable | Source `Distanz km` |
| `duration_min` | Integer, nullable | Source `Zeit` |
| `route_description` | Text, nullable | Source `Route` |
| `flight_id` | String FK → `flights.id`, nullable | Linked only when unambiguous (`research.md`'s matching rule); a pure hike (no `Airtime`/`Landeplatz` in the source) is never linked |
| `created_at`, `updated_at` | UtcDateTime | |

`Airtime`/`Landeplatz` from the source sheet are **not separate columns** — they were the signal used at
import time to decide whether to attempt a `flight_id` link, not data worth storing twice once the link
itself (or its absence) is recorded. The linked flight's own duration/landing site are the source of
truth for a hike that became a flight.

## `groundhandling_sessions`

Named with a `_sessions` suffix, not bare `groundhandling` — `session` is the actual noun; the sheet
name is German shorthand, not a naming convention to carry into the schema.

| Column | Type | Notes |
|---|---|---|
| `id` | String PK | |
| `owner_id` | String FK, not null, indexed | |
| `import_key` | String, nullable | `"groundhandling:<row>"`; `UniqueConstraint("owner_id", "import_key")` |
| `session_date` | Date, not null | Source `Datum` |
| `place` | String, not null | Source `Ort` |
| `duration_min` | Integer, nullable | Source `Dauer (min)` |
| `comment` | Text, nullable | Source `Kommentar` |
| `created_at`, `updated_at` | UtcDateTime | |

## `tandem_flights`

| Column | Type | Notes |
|---|---|---|
| `id` | String PK | |
| `owner_id` | String FK, not null, indexed | The pilot who *flew as passenger*, never the tandem operator |
| `import_key` | String, nullable | `"tandemfluege:<row>"`; `UniqueConstraint("owner_id", "import_key")` |
| `flight_date` | Date, not null | Source `Datum` |
| `launch_place` | String, not null | Source `Start` |
| `landing_place` | String, not null | Source `Landung` |
| `tandem_operator` | String, nullable | Source `Pilot` — free text (person or company name, e.g. `"AlpineAir"`); deliberately **not** a FK to `buddies` (`research.md`) |
| `comment` | Text, nullable | Source `Kommentar` |
| `cost` | Float, nullable | Source `kosten`; `0` is a real, meaningful value (a flight-school tandem taken for free), not an absent one — render it as "0", never as "not recorded" |
| `created_at`, `updated_at` | UtcDateTime | |

Deliberately **not** a row in `flights` (`architecture.md`) — this pilot did not fly the wing.

## `goals`

The one entity in this feature that stays editable after import (`research.md`).

| Column | Type | Notes |
|---|---|---|
| `id` | String PK | |
| `owner_id` | String FK, not null, indexed | |
| `import_key` | String, nullable | `"ziele:<row>"`; `UniqueConstraint("owner_id", "import_key")` — identifies which spreadsheet row a goal originated from, if any; irrelevant to a goal created directly through the app (`NULL`) |
| `title` | String, not null | Source `Titel` |
| `wind_direction` | String, nullable | Source `Wetterlage` — free text (`"N"`, `"W, SW"`, `"any"`), not an enum; observed values don't form a closed set |
| `difficulty` | String, nullable | Source `Level` (`leicht`\|`mittel`\|`schwer` observed) — kept as free text, not an enum column, since a fourth value appearing later shouldn't need a migration |
| `category` | String, nullable | Source `Kategorie` (`H&F`\|`Abgleiter`\|`Teacher` observed) — same free-text reasoning as `difficulty` |
| `description` | Text, nullable | Source `Beschreibung` |
| `links` | Text, nullable | Source `Links` |
| `target_season` | String, nullable | Source `Saison` — stored as text (`"2025"` observed); not assumed to always be a bare year |
| `status` | String, not null, default `"open"` | Source `Status` (`open`\|`done` observed); not an enum-typed column for the same forward-compatibility reason as `difficulty`/`category`, but FR-007's status filter only needs to compare against whatever value is actually stored |
| `created_at`, `updated_at` | UtcDateTime | |

## `flights` — three new columns (existing table, needs `_run_column_migrations()`)

| Column | Type | Notes |
|---|---|---|
| `xc_official_score` | Float, nullable | From an XContest import; independent of the flight's existing hand-entered `distance_km` |
| `xc_official_type` | String, nullable | Which XContest rule set scored it (exact value set depends on the schema resolved in `research.md`'s open item) |
| `xc_official_url` | String, nullable | Link back to the flight's XContest page; validated as `http://`/`https://` only, per `04-constraints.md`'s URL-validation rule for any stored external link |

These three exact names and the decision to add them to `flights` directly (not a separate
`xcontest_attachments` table) were already committed in `specs/001-core-data-import/data-model.md` and
`architecture.md` — this feature is the first to actually populate them, not the first to design them.

## Relationships summary

```
User 1──* Hike, GroundhandlingSession, TandemFlight, Goal   (owner_id, not null)
Flight 0..1──* Hike   (flight_id, nullable — set only on an unambiguous match)
Flight (existing table) + xc_official_score / _type / _url   (populated by this feature's XContest import)
```

No relationship from `tandem_flights` or `groundhandling_sessions` to `flights` — both are deliberately
standalone, per `architecture.md`.
