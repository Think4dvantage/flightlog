# Architecture Reference

This is the source of truth for the data model, the domain algorithms and the deployment shape.
It records not just *what* the design is, but *why it is not the obvious alternative*, and what breaks
if someone "fixes" it.

Status: **v0.1 in progress.** Only the tables and routes marked shipped exist.

---

## SQLite Tables

| Table | Status | Key columns |
|---|---|---|
| `users` | v0.1 | `id`, `email` (unique), `display_name`, `hashed_password`, `role`, `is_active`, `locale`, `timezone`, `units`, `seeded_at`, `created_at` |
| `api_keys` | v0.7 | `id`, `owner_id`, `name`, `key_prefix` (unique), `key_hash`, `scopes`, `last_used_at`, `revoked_at` |
| `regions` | v0.2 | `id`, `name`, `sort_order` — global reference data, not user-scoped |
| `sites` | v0.2 | `id`, `owner_id` (nullable), `name`, `is_launch`, `is_landing`, `lat`, `lon`, `elevation_m`, `region_id`, `coord_source`, `wind_directions` |
| `user_site_prefs` | v0.2 | `(user_id, site_id)` PK, `alias`, `elevation_m`, `is_favourite`, `is_hidden` |
| `site_observations` | v0.4 | `id`, `site_id`, `lat`, `lon`, `alt_m`, `track_id`, `kind` |
| `gliders` | v0.2 | `id`, `owner_id`, `brand`, `model`, `size`, `nickname`, `en_class`, `is_own`, `retired_at` |
| `harnesses` | v0.2 | `id`, `owner_id`, `brand`, `model`, `size`, `harness_type`, `reserve_next_repack`, `retired_at` |
| `flight_categories` | v0.2 | `id`, `owner_id`, `name`, `slug`, `is_hike_fly`, `is_training`, `sort_order`, `archived_at` |
| `buddies` | v0.2 | `id`, `owner_id`, `display_name`, `linked_user_id`, `link_state` |
| `flights` | v0.2 | see below |
| `flight_buddies` | v0.2 | `(flight_id, buddy_id)` |
| `media_links` | v0.3 | `id`, `flight_id`, `owner_id`, `url`, `kind`, `provider` |
| `tracker_links` | v0.3 | `id`, `flight_id`, `owner_id`, `provider`, `url`, `external_id` |
| `flight_links` | v0.7 | `id`, `flight_id`, `kind`, `external_id`, `url`, `label` — VidFactory pushes here |
| `igc_tracks` | v0.4 | one per flight; file on disk, aggregates here |
| `igc_segments` | v0.4 | thermals / glides / markers with takeoff-relative offsets |
| `hikes` | v0.5 | `Fitnessprogramm` sheet; nullable `flight_id` |
| `groundhandling` | v0.5 | `date`, `place`, `duration_min`, `comment` |
| `tandem_flights` | v0.5 | flights as a passenger — deliberately NOT in `flights` |
| `goals` | v0.5 | `Ziele` sheet |

### Tables that do NOT exist — do not code against them

- **`igc_fixes`.** Track points are never stored in SQLite. 600 tracks × ~3000 fixes is ~2M rows for data
  already on disk. `igc_tracks.track_simplified_json` holds a ~500-point polyline for map rendering, and
  the raw `.igc` is re-parsed for the rare full-resolution request.
- **`outings`.** That is VidFactory's name for the same concept. This project's table is `flights`.
- **`lookups`.** VidFactory keeps gliders/harnesses/categories in one key-value `lookups` table. Here
  they are three first-class tables with their own columns.
- **`stats_cache`.** Nothing is materialised except IGC analysis. Add one only if `/stats/overview`
  measurably exceeds ~200 ms — not speculatively.

### Foreign keys are NOT enforced

`PRAGMA foreign_keys=ON` is never set, so `ondelete="CASCADE"` is documentation. The ORM's
`cascade="all, delete-orphan"` on the relationship is what actually deletes children. Write both; rely
on the relationship.

---

## Derived values — computed on read, never stored

The Excel and VidFactory both use a field called `height_diff`, and **they mean different things**.
Three unambiguous names are used instead, and none of them is a column:

```
alt_gain_m      = max_alt_m - eff_launch_elev_m         # Excel "Altgain"
site_drop_m     = eff_launch_elev_m - eff_landing_elev_m # Excel "Höhe diff." (post-2023 form)
total_descent_m = max_alt_m - eff_landing_elev_m         # VidFactory's height_diff_m
```

"Effective" elevation is `COALESCE(flight override, user_site_prefs override, sites.elevation_m)`.

**Why not stored:** a site elevation correction must retroactively fix every flight. The Excel proves
the failure mode — its `Höhe diff.` column silently changed formula at row 472 (2023-01-25), from
`max_alt − landing_elev` to `launch_elev − landing_elev`, leaving 48 rows whose stored value
contradicts both definitions.

---

## Sites — one table, two roles

`is_launch` and `is_landing` are independent booleans with
`CheckConstraint("is_launch = 1 OR is_landing = 1")`. The Excel kept two separate lists, but
`Schiltgrat` (2090 m) and `Schwandfeldspitz` (2045 m) appear in both at identical elevations — they are
one place, used two ways.

`owner_id IS NULL` is reserved to mean "official shared catalogue". **No site uses it yet** — every site
is user-owned until the shared layer ships. The column is nullable from day one so that layer needs no
migration.

**Do not add a `scope` enum.** It would duplicate what `owner_id` nullability already says and permit
the meaningless state `scope='official' AND owner_id='u1'`.

### Coordinates are backfilled, never geocoded

The Excel has no lat/lon anywhere. Geocoding is rejected: `Amisbühl`, `Lehn`, `Bergbo`, `Lutzi` are
local launch names, not addresses, and a confidently wrong pin that renders on a map is worse than a
blank one.

Instead, every IGC analysis appends its takeoff and landing fix to `site_observations`. At ≥3
observations the site's `lat`/`lon` is set to the **median** — robust against a single GPS cold-start
outlier — with `coord_source='igc_median'` and `coord_accuracy_m` recording the spread. A manual pin
drop sets `coord_source='manual'`, and the backfill never overwrites that.

Elevation stays from the hand-curated `DropDownData` list, which is better than a GNSS takeoff fix, but
`elevation_igc_m` is persisted alongside for comparison. A disagreement over 100 m is a real data-quality
signal.

---

## Flight categories — flags, not string matching

`is_hike_fly` and `is_training` are booleans on the category row. VidFactory hardcodes
`HIKEFLY_CATEGORY = "Hike&Fly"` and matches on that literal; renaming the category there silently zeroes
every Hike&Fly statistic. The flags also express the Excel's "Average Airtime special" (28.56 min vs
26.14 min overall) as `AVG(duration) WHERE NOT is_training`.

---

## Buddy account linking — two-sided handshake

`link_state ∈ none | pending | confirmed | declined`.

`POST /api/buddies/{id}/link` returns **202 whether or not the email belongs to a registered user**. A
404 on an unknown address would make the endpoint a user-enumeration oracle. The linked user's
`display_name` is exposed only once `link_state == 'confirmed'`.

The buddy row always belongs to its creator. `linked_user_id` is enrichment, never ownership — deleting
a buddy never touches the linked account.

---

## IGC analysis

Library: **`libigc`**. Wrapper lives in `core/igc.py`.

1. `libigc.Flight.create_from_file(path)`; reject `not flight.valid` with the joined `flight.notes`.
2. **Altitude source**: prefer barometric — use `press_alt` when >50% of fixes carry a non-`None` baro
   value, else `gnss_alt`. Persist `alt_source`.
   ⚠ Test `is not None`, **not** truthiness. VidFactory's `[f.press_alt for f in flight.fixes if
   f.press_alt]` silently discards every 0 m fix.
3. **Thermals**: keep only climbing circles — `[t for t in flight.thermals if t.alt_change() > 0]`.
   ⚠ libigc flags *any* circling as a thermal, including descending spirals and wingovers, both of which
   are routine in paragliding. Without this filter `best_climb` and `avg_climb` are poisoned. This is
   pinned by a regression test in `test_igc_analysis.py`.
4. **Tuning is config, not constants.** `libigc.FlightParsingConfig` overrides live under `igc.parsing:`
   in `config.yml` (`min_time_for_thermal_s`, `min_bearing_change_circling_deg`, `min_time_for_glide_s`,
   `max_time_between_thermals_s`) and every resolved value is logged at startup. Paraglider thermals are
   slower and sloppier than the sailplane defaults; these will need iteration against real tracks.
5. **Glide ratio** = Σ(track_length of descending glides) / Σ(−alt_change of descending glides). This is
   an **over-ground** ratio including air-mass lift, not the wing's still-air L/D. The aggregate form is
   deliberate: one shallow segment cannot inflate it.
6. **`best_climb_ms` is the best thermal *average*, not the instantaneous peak** — peaks are GPS noise.
   `peak_climb_ms` from a 10 s rolling window is a separate, clearly named field.
7. `analyzer_version` is persisted per track. A re-analysis sweep keys on it.

### IGC storage

Content-addressed on disk, never a BLOB:

```
<storage.igc_dir>/<owner_id>/<YYYY>/<sha256>.igc
<storage.igc_dir>/<owner_id>/<YYYY>/<sha256>.track.json   # derived, regenerable
```

Content addressing gives deduplication and idempotent re-upload for free, and collapses the known
device-vs-XContest duplicate problem without a staging folder. The DB keeps `original_filename` for
display.

### `igc_segments` — the VidFactory contract

`kind ∈ thermal | glide | takeoff | landing | max_alt | top_of_climb`.

**`start_offset_s` (seconds since takeoff) is the load-bearing field.** VidFactory maps it onto a video
timeline with one addition, knowing its own `video_start_utc`. Absolute `start_at` is stored too, so a
camera that started rolling before takeoff can still be aligned.

**Never return video-relative offsets from this service** — it has no idea when the camera started.

Storing segments is what makes the highlight query an indexed `ORDER BY` instead of an IGC re-parse.

### Matching an uploaded IGC to a flight

The Excel records no time of day and **117 days carry more than one flight**, so date alone is not
enough.

- **Primary path**: upload from the flight's own edit form — unambiguous by construction.
- **Bulk path**: read only the header for the date (`^HFDTE(?:DATE:)?(\d{2})(\d{2})(\d{2})`, bail on the
  first `B` record, ISO-8859-1). When a date has N files and M free flights, score each file's duration
  against each flight's logged minutes and auto-attach only when `|Δ| ≤ 3 min` **and** the runner-up is
  `> 10 min` away. Everything else is reported for manual assignment, never guessed.
- **Writeback shrinks the problem**: every attach writes `flights.takeoff_time` / `landing_time` from
  the track, so later imports can match on time overlap.

---

## Statistics

Nothing is materialised. Every figure is one or two indexed aggregates over ~600 rows.

Two deliberate disagreements with the Excel's `Übersicht` sheet — **confirm these, do not "fix" them**:

1. The workbook's reverse-launch share (33.5%) is computed over a stale `$N$2:$N$499` range and misses
   102 flights. The correct figure is 209/600 ≈ 34.8%.
2. The workbook's twelve region counts sum to **596**, not 600. The importer recomputes the aggregation
   and reports unassigned launches by name rather than creating an "Other" bucket.

---

## API Contracts

Error envelope on every route — **not RFC 7807**:

```json
{ "error": { "code": "ENTITY_NOT_FOUND", "message": "...", "details": {} } }
```

Codes: `VALIDATION_FAILED` (400/422), `AUTH_REQUIRED` (401), `PERMISSION_DENIED` (403),
`ENTITY_NOT_FOUND` (404), `CONFLICT` (409), `INTERNAL_ERROR` (≥500).

| Prefix | Router | Status |
|---|---|---|
| `/api/auth` | `auth.py` | v0.1 — register (flag-gated), login, refresh, `/me`, `/registration-status` |
| `/health` | `health.py` | v0.1 |
| `/api/sites` `/api/gliders` `/api/harnesses` `/api/categories` `/api/buddies` | — | v0.2 |
| `/api/flights` | `flights.py` | v0.2 |
| `/api/stats` | `stats.py` | v0.6 |
| `/api/integration/v1` | `integration.py` | v0.7 — frozen contract, versioned separately from the UI's models |

Routes are not enumerated here beyond the prefix — **read the router file, which is the source of truth.**

---

## Deployment

### Hostnames

| Environment | Host | Port |
|---|---|---|
| dev | `fl-dev.sdh.lol` | 8002 → 8000 |
| prod | `fl.sdh.lol` | via Traefik |

Port 8002 avoids VidFactory (8000) and Lenticularis dev (8001) on the same box.

### Traefik Label Format

This homelab requires **list format** labels, not map format:

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.flightlog-dev.rule=Host(`fl-dev.sdh.lol`)"
```

When a container is on multiple Docker networks, add `traefik.docker.network=proxy`.

### Healthcheck

The slim base image does not include `curl`. Use Python stdlib:

```yaml
healthcheck:
  test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\""]
```

### Data volume

DB and IGC files share one **named Docker volume**. Never a NAS bind mount — SQLite WAL over SMB/NFS is
unsafe. One volume also makes backup a single `tar` of that volume.

### Versioning

`pyproject.toml`'s version is both the image tag source and the static-asset cache key. A static change
without a version bump leaves returning users on the old file for up to a year.
