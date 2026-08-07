# Data Model: Core Data & Excel Import

All tables follow `User`'s conventions exactly (`database/models.py`): `String` UUID primary key via
`new_uuid`, every timestamp `UtcDateTime` via `utcnow`, `owner_id` a `ForeignKey("users.id",
ondelete="CASCADE")` that is documentation only (`PRAGMA foreign_keys` stays off — the ORM relationship's
`cascade="all, delete-orphan"` is what actually deletes children), `owner_id` indexed and never accepted
from a request body.

`site_observations` is explicitly **not** part of this feature — deferred to v0.4 per the Clarifications
section of `spec.md`.

## `regions`

Shared reference data. Not owner-scoped.

| Column | Type | Notes |
|---|---|---|
| `id` | String PK | `new_uuid` |
| `name` | String, unique, not null | e.g. `Interlaken` |
| `sort_order` | Integer, not null | Display order |

Seeded from `db.py` at startup (Python list + existence check), transcribed once from the workbook's
"Flight Area" formulas per `research.md`. 12 rows.

## `sites`

| Column | Type | Notes |
|---|---|---|
| `id` | String PK | |
| `owner_id` | String FK → `users.id`, **nullable**, indexed | `NULL` reserved for a future shared catalogue (v0.8+) — no row uses `NULL` yet; every v0.2 site is owner-set |
| `name` | String, not null | |
| `is_launch` | Boolean, not null, default `False` | |
| `is_landing` | Boolean, not null, default `False` | `CheckConstraint("is_launch = 1 OR is_landing = 1")` |
| `lat`, `lon` | Float, nullable | Set manually via the API in v0.2; IGC-median backfill arrives v0.4 |
| `elevation_m` | Integer, nullable | Hand-curated value, from `DropDownData` at import time |
| `elevation_igc_m` | Integer, nullable | Not written before IGC backfill exists (v0.4); declared now because `sites` is being created fresh in this feature — same reasoning as `flights.takeoff_time`/`landing_time` below. Adding it later, once `sites` already exists, is what would need a `_run_column_migrations()` guard |
| `region_id` | String FK → `regions.id`, nullable | Null when a site's region can't be resolved (see `research.md`); landings are not region-mapped in the source data |
| `coord_source` | String, nullable | `manual` only in v0.2; `igc_median` is a v0.4 value, not written here |
| `coord_accuracy_m` | Float, nullable | Not written before IGC backfill exists (v0.4) — same free-now-vs-migration-later reasoning as `elevation_igc_m` |
| `created_at`, `updated_at` | UtcDateTime | |

## `user_site_prefs`

| Column | Type | Notes |
|---|---|---|
| `user_id` | String FK → `users.id` | Part of composite PK |
| `site_id` | String FK → `sites.id` | Part of composite PK |
| `alias` | String, nullable | Personal display name override |
| `elevation_m` | Integer, nullable | Personal elevation override — 2nd in the `COALESCE` chain (`architecture.md`) |
| `is_favourite` | Boolean, not null, default `False` | |
| `is_hidden` | Boolean, not null, default `False` | |

`PrimaryKeyConstraint("user_id", "site_id")`.

## `gliders`

| Column | Type | Notes |
|---|---|---|
| `id` | String PK | |
| `owner_id` | String FK, not null, indexed | |
| `brand`, `model` | String, not null | |
| `size` | String, nullable | e.g. `28`, `31` — kept as text; sizes like "M" appear in the source data |
| `nickname` | String, nullable | The workbook's parenthetical names (`Ragnar`, `Dumbo`, …) |
| `en_class` | String, nullable | EN/LTF wing class, not in the legacy data — left null on import |
| `is_own` | Boolean, not null, default `True` | |
| `retired_at` | UtcDateTime, nullable | |
| `created_at`, `updated_at` | UtcDateTime | |

## `harnesses`

| Column | Type | Notes |
|---|---|---|
| `id` | String PK | |
| `owner_id` | String FK, not null, indexed | |
| `brand`, `model` | String, not null | |
| `size` | String, nullable | |
| `harness_type` | String, nullable | Not in the legacy data — left null on import |
| `reserve_next_repack` | UtcDateTime, nullable | Not in the legacy data — left null on import |
| `retired_at` | UtcDateTime, nullable | |
| `created_at`, `updated_at` | UtcDateTime | |

## `flight_categories`

| Column | Type | Notes |
|---|---|---|
| `id` | String PK | |
| `owner_id` | String FK, not null, indexed | |
| `name` | String, not null | The 12 legacy German category names, verbatim (data, not translated — see `03-frontend-conventions.md`) |
| `slug` | String, not null | `UniqueConstraint("owner_id", "slug")` |
| `is_hike_fly` | Boolean, not null, default `False` | True only for `Hike&Fly` |
| `is_training` | Boolean, not null, default `False` | True for `Grundkurs`, `Flugschule`, `Prüfung`, `Startleiter`, `SiKu` — drives the "Average Airtime special" stat |
| `sort_order` | Integer, not null | |
| `archived_at` | UtcDateTime, nullable | Never hard-deleted once a flight references it |

## `buddies`

| Column | Type | Notes |
|---|---|---|
| `id` | String PK | |
| `owner_id` | String FK, not null, indexed | The buddy row always belongs to its creator |
| `display_name` | String, not null | |
| `linked_user_id` | String FK → `users.id`, nullable | Enrichment only, never ownership — deleting a buddy never touches the linked account |
| `link_state` | String, not null, default `"none"` | `none \| pending \| confirmed \| declined` |
| `created_at`, `updated_at` | UtcDateTime | |

## `flights`

| Column | Type | Notes |
|---|---|---|
| `id` | String PK | |
| `owner_id` | String FK, not null, indexed | |
| `flight_date` | Date, not null | No time component in the source; `takeoff_time`/`landing_time` are separately nullable |
| `takeoff_time`, `landing_time` | UtcDateTime, nullable | Null until IGC attach (v0.4) backfills them; declared now since the table is being created fresh — free, unlike a whole unused table |
| `launch_site_id` | String FK → `sites.id`, not null | A source row that can't be resolved to a known site is **not written** — it's reported by the import instead (FR-014), never inserted with a placeholder |
| `landing_site_id` | String FK → `sites.id`, nullable | Nullable for a logged-but-unknown landing |
| `category_id` | String FK → `flight_categories.id`, not null | Same "skip and report, never guess" rule as `launch_site_id` |
| `glider_id` | String FK → `gliders.id`, nullable | |
| `harness_id` | String FK → `harnesses.id`, nullable | |
| `duration_min` | Integer, nullable | Source `Flugzeit` |
| `distance_km` | Float, nullable | Source `Distanz` |
| `max_alt_m` | Integer, nullable | Source `Max Alt` — stored; **not** the same as the derived `alt_gain_m` |
| `launch_elev_override_m`, `landing_elev_override_m` | Integer, nullable | 1st in the `COALESCE` chain (`architecture.md`) — a per-flight elevation correction |
| `launch_technique` | String, nullable | `forward \| reverse`, from source `Startart` (`f`/`r`) |
| `notes` | Text, nullable | Free text, ~3300 char ceiling observed in the source; rendered with `textContent`, never `innerHTML`, on any future page |
| `import_key` | String, nullable | `"xlsx:<row>"` for imported rows; `NULL` for flights entered directly — see `research.md`. **Unique per owner, not globally** (`UniqueConstraint("owner_id", "import_key")`) — a global unique constraint would break the day-one tenancy rule the moment a second pilot imports their own workbook and produces the same `"xlsx:5"` |
| `created_at`, `updated_at` | UtcDateTime | |

`alt_gain_m`, `site_drop_m`, `total_descent_m` are **not columns** — computed on read from
`max_alt_m` and the effective launch/landing elevations, per `architecture.md`. `xc_official_score` /
`_type` / `_url` are v0.5 (XContest import) and not added here.

## `flight_buddies`

| Column | Type | Notes |
|---|---|---|
| `flight_id` | String FK → `flights.id` | Part of composite PK |
| `buddy_id` | String FK → `buddies.id` | Part of composite PK |

`PrimaryKeyConstraint("flight_id", "buddy_id")`.

## Relationships summary

```
User 1──* Site (owner_id, nullable)
User 1──* Glider, Harness, FlightCategory, Buddy, Flight  (owner_id, not null)
User *──* Site   through user_site_prefs (personal overrides on a site the user doesn't necessarily own)
Region 1──* Site (region_id, nullable)
Site 1──* Flight (as launch_site_id, not null)
Site 1──* Flight (as landing_site_id, nullable)
FlightCategory 1──* Flight
Glider 1──* Flight (nullable)
Harness 1──* Flight (nullable)
Flight *──* Buddy   through flight_buddies
Buddy *──1 User (linked_user_id, nullable, enrichment only)
```
