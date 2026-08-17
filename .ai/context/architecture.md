# Architecture Reference

This is the source of truth for the data model, the domain algorithms and the deployment shape.
It records not just *what* the design is, but *why it is not the obvious alternative*, and what breaks
if someone "fixes" it.

Status: **v0.9 shipped.** Sharing & public readiness — see `specs/007-sharing-public-readiness/` for
the spec, plan and research behind it. (v0.2's Core data + Excel import remains the foundation
everything since builds on — see `specs/001-core-data-import/`.)

---

## SQLite Tables

| Table | Status | Key columns |
|---|---|---|
| `users` | **shipped v0.1**, `public_profile_enabled` added v0.9 | `id`, `email` (unique), `display_name`, `hashed_password`, `role`, `is_active`, `locale`, `timezone`, `units`, `seeded_at`, `public_profile_enabled`, `last_login_at`, `created_at`, `updated_at` — `seeded_at` was reserved-but-unused plumbing from v0.2 through v0.8; v0.9's `core/user_seed.py` is its first real consumer |
| `api_keys` | **shipped v0.8** | `id`, `owner_id`, `name`, `key_prefix` (unique), `key_hash`, `scopes`, `expires_at`, `last_used_at`, `revoked_at`, `created_at` — `expires_at` added during v0.8 planning to resolve a doc inconsistency (`specs/006-public-api-vidfactory/research.md`): `revoked_at` always wins, regardless of expiry |
| `regions` | **shipped v0.2** | `id`, `name`, `sort_order` — global reference data, not user-scoped |
| `sites` | **shipped v0.2** | `id`, `owner_id` (nullable), `name`, `is_launch`, `is_landing`, `lat`, `lon`, `elevation_m`, `elevation_igc_m`, `region_id`, `coord_source`, `coord_accuracy_m` |
| `user_site_prefs` | **shipped v0.2** | `(user_id, site_id)` PK, `alias`, `elevation_m`, `is_favourite`, `is_hidden` |
| `gliders` | **shipped v0.2** | `id`, `owner_id`, `brand`, `model`, `size`, `nickname`, `en_class`, `is_own`, `retired_at` |
| `harnesses` | **shipped v0.2** | `id`, `owner_id`, `brand`, `model`, `size`, `harness_type`, `reserve_next_repack`, `retired_at` |
| `flight_categories` | **shipped v0.2** | `id`, `owner_id`, `name`, `slug`, `is_hike_fly`, `is_training`, `sort_order`, `archived_at` |
| `buddies` | **shipped v0.2** | `id`, `owner_id`, `display_name`, `linked_user_id`, `link_state` |
| `flights` | **shipped v0.2**, `visibility` added v0.9 | see below |
| `flight_buddies` | **shipped v0.2** | `(flight_id, buddy_id)` |
| `media_links` | **not built — backlog** | `id`, `flight_id`, `owner_id`, `url`, `kind`, `provider` — photo-thumbnail idea (`features.md`'s Backlog); mislabeled "v0.3" in this doc since inception even though v0.3 shipped without it |
| `flight_links` | **shipped v0.8** | `id`, `flight_id`, `kind`, `external_id`, `url`, `label`, `created_at`, `updated_at` — `UniqueConstraint(flight_id, kind, external_id)`; a `PUT` to that triple replaces, never duplicates. No `owner_id` — reached through the parent `flights` row, same reasoning as `igc_segments`. VidFactory pushes here via `PUT /api/integration/v1/flights/{id}/links/{kind}/{external_id}`; the pilot's own `GET /api/flights/{id}` (and the list endpoint, one small per-flight query each — same precedent as `buddy_ids`) surfaces them back as `FlightOut.links` with no action needed (FR-009) |
| `igc_tracks` | **shipped v0.5** | one per flight (`UniqueConstraint(flight_id)`); file on disk, aggregates here — see IGC analysis section below |
| `igc_segments` | **shipped v0.5** | thermals / glides / markers with takeoff-relative offsets |
| `site_observations` | **shipped v0.5** | `id`, `site_id`, `track_id`, `kind` (takeoff\|landing), `lat`, `lon`, `alt_m` — feeds `core/site_backfill.py`'s median coordinate recompute |
| `hikes` | **shipped v0.6** | `Fitnessprogramm` sheet; nullable `flight_id`, linked only on an unambiguous same-date match against an `is_hike_fly` flight — never guessed |
| `groundhandling_sessions` | **shipped v0.6** | `date`, `place`, `duration_min`, `comment` — named with a `_sessions` suffix, not bare `groundhandling` (the sheet name is German shorthand, not a schema-naming convention) |
| `tandem_flights` | **shipped v0.6** | flights as a passenger — deliberately NOT in `flights`; `tandem_operator` stays free text, never a `buddies` FK (real source values include company names) |
| `goals` | **shipped v0.6** | `Ziele` sheet; the one imported type that stays fully editable afterward (full CRUD + a `mark-done` action) — every other type in this milestone is import-and-view only |

### Tables that do NOT exist — do not code against them

- **`igc_fixes`.** Track points are never stored in SQLite. 600 tracks × ~3000 fixes is ~2M rows for data
  already on disk. `igc_tracks.track_simplified_json` holds a ~500-point polyline for map rendering, and
  the raw `.igc` is re-parsed for the rare full-resolution request.
- **`outings`.** That is VidFactory's name for the same concept. This project's table is `flights`.
- **`lookups`.** VidFactory keeps gliders/harnesses/categories in one key-value `lookups` table. Here
  they are three first-class tables with their own columns.
- **`stats_cache`.** Nothing is materialised except IGC analysis. `/api/stats` (v0.7) confirmed this in
  practice, not just in principle — every figure is a read-time aggregate over ~600 rows and the full
  page loads well under a second live. Add a cache only if a specific figure is later measurably too
  slow — not speculatively.
- **`igc_pending_uploads`.** Shipped v0.5 as the review queue behind bulk IGC upload
  (`POST /api/igc/bulk`), **removed in v0.8.1**: a real bulk import mismatched flights against
  the pilot's real data, and the fix was to drop bulk upload entirely rather than debug its
  matching heuristic — the per-flight upload path (`POST /api/flights/{id}/igc`, unambiguous
  by construction, live since v0.5) already covers the actual need. `core/reset_igc.py`
  (`python -m flightlog.core.reset_igc --write`) is the one-shot cleanup this release shipped:
  it deletes every `igc_tracks`/`igc_segments`/`site_observations` row, drops this table
  outright (its model is gone, so `Base.metadata.create_all()` never recreates it), and undoes
  the two things those bad tracks wrote elsewhere — `flights.takeoff_time`/`landing_time`
  (nulled; the legacy workbook has no time-of-day anywhere, so every value there came from a
  track) and any site's `coord_source == "igc_median"` coordinate (cleared; it was a median of
  the `site_observations` rows being deleted). Not owner-scoped, matching `core/importer.py`'s
  single-pilot assumption.
- **`tracker_links`, and any site `webcam_url` / `rules_url` column.** Unlike the others in this list,
  these were never a deliberate design rejection — they were carried in this doc's own table list
  (mislabeled "v0.3", as though shipped or scheduled) and cited by `04-constraints.md`/
  `03-frontend-conventions.md` as URL-validation precedent since this project's first revision, but no
  milestone, spec, or line of code has ever actually referenced them. Pure blueprint leftover, found
  and corrected during v0.8's documentation sync. If a live-tracker-link feature (a Livetrack24/
  Flymaster beacon URL, a site's own webcam or rules page) is ever wanted, scope it into a real
  milestone first — don't resurrect these rows as-is.

### Foreign keys are NOT enforced

`PRAGMA foreign_keys=ON` is never set, so `ondelete="CASCADE"` is documentation. The ORM's
`cascade="all, delete-orphan"` on the relationship is what actually deletes children. Write both; rely
on the relationship.

---

## Timestamps — `UtcDateTime`, not `DateTime(timezone=True)`

SQLite has no native timestamp type and stores no offset, so a plain `DateTime(timezone=True)` column
silently returns a **naive** datetime on read. The value is UTC, but nothing in the API response says
so — a client receives `2026-08-06T13:12:59.275499` and cannot tell UTC from local time.

`database/models.py` defines a `UtcDateTime` `TypeDecorator` that coerces to UTC on write and
re-attaches UTC on read. **Every datetime column uses it.** Never `DateTime` directly.

This was found by inspecting a live response, not by a test — the naive value round-trips through
SQLAlchemy perfectly well, so nothing fails. It matters because the VidFactory contract publishes
`takeoff_at_utc` and every IGC segment is anchored on absolute UTC; an ambiguous timestamp there is a
misaligned video timeline. Pinned by `test_timestamps_are_serialised_with_an_explicit_utc_offset`.

---

## Error handlers must register against Starlette's `HTTPException`

FastAPI's `HTTPException` subclasses Starlette's. Unmatched routes and other framework-level errors
raise the **parent**, so a handler registered against the FastAPI subclass never fires for them and
those responses escape the typed envelope — a 404 comes back as `{"detail": "Not Found"}`.

`main.py` therefore registers `starlette.exceptions.HTTPException`. Caught by
`test_unknown_route_returns_the_envelope`.

---

## `check_db_health()` takes the engine as an argument

It reads `app.state.engine`, not `db.py`'s module-level `_engine`. Reaching into module state made the
check report `"not initialised"` for any caller that wired its own engine — which is every test, since
they override `get_db` rather than calling `init_db()`.

---

## The app version is resolved with a fallback, and it is the cache key

`importlib.metadata.version()` only works when the package is pip-installed. The container runs
`poetry install --no-root` and puts `src/` on `PYTHONPATH`, so **there is no distribution metadata in
the image** — the naive implementation reported `0.0.0-dev` in production.

Because the version is the static-asset cache key, that would have frozen the cache key across every
future deploy and left returning browsers on stale CSS and JS indefinitely. `_resolve_version()` falls
back to reading `pyproject.toml`, which is copied into the image alongside `src/`. Pinned by
`test_app_version_matches_pyproject`, which asserts it is never `0.0.0-dev`.

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

## Secondary sheets import — `core/secondary_import.py`

**Shipped v0.6.** Mirrors `core/importer.py`'s existing shape exactly: `import_key` of
`"<sheet>:<row>"`, looked up per-owner before writing, so a second run changes nothing. Three of the
four imported types (`hikes`, `groundhandling_sessions`, `tandem_flights`) are import-and-view only —
no write path exists beyond the importer itself. `goals` is the exception: fully editable afterward via
`/api/goals`'s normal CRUD router, the same as every other owner-scoped domain entity in this app.

**Hike-to-flight linking never guesses.** A hike's source row carries `Airtime`/`Landeplatz` values only
when it became a real flight; that presence (not the date alone) is the signal to attempt a link, and
even then only when exactly one same-date flight with `flight_categories.is_hike_fly = True` exists.
Zero or multiple candidates → the hike imports with `flight_id = NULL`, never a guessed match — the same
principle already applied to the IGC bulk-match and the (backlogged) XContest score matching design.
Against the real workbook: 85 hikes, 35 linked.

**`Ziele`'s reported column width (~505) is misleading — real data lives in the first 8 columns only**,
the rest being leftover Excel formatting artifacts, `None` on every real row. The importer reads by
fixed position (0–7), never iterates the sheet's full reported width.

**v0.6 is fully shipped.** XContest "My Flights" score import was originally scoped alongside this
milestone but has moved to `features.md`'s Backlog (2026-08-15), not left as an open phase here — its
exact export JSON schema was never confirmed (the site requires a login session to inspect, and the one
third-party integration investigated, `Iv/FlyHigh`, turned out to implement the opposite direction —
submitting a flight for scoring, not reading back an already-scored list). Resolve by obtaining one real
sample export before writing that parser; `flights.xc_official_score`/`_type`/`_url` (already named in
`specs/001-core-data-import/data-model.md`) remain unpopulated until then. `specs/004-secondary-sheets-
xcontest/` (Phase 5, T018–T024) is the design record to resume from.

---

## IGC analysis

**Shipped v0.5.** Library: **`libigc`** 1.2.0 (pure-Python, `py3-none-any` wheel). Wrapper lives in
`core/igc.py`. Every route is a plain sync `def` (`api/routers/igc.py`) — FastAPI's own threadpool
dispatch keeps this CPU-bound work off the event loop, same as every other route in the app; there is
no `async def` handler anywhere and no `asyncio.to_thread` call for this.

1. `libigc.Flight.create_from_file(path)`; reject `not flight.valid` with the joined `flight.notes`.
   `create_from_file` takes a **path**, not bytes — an upload is written to content-addressed storage
   before this is ever called.
2. **Altitude source**: read `flight.alt_source` directly — do **not** recompute a source selection from
   the raw fixes. `libigc` already validates both the `press_alt` and `gnss_alt` streams per-fix (rate-
   of-change limits, absolute bounds, a stuck-sensor check) and resolves `PRESS`/`GNSS` itself; if
   neither stream is valid, `flight.valid` is already `False` and rule 1 rejects it. An earlier draft of
   this section proposed a ">50% non-`None` fixes" heuristic — abandoned once the real library was
   inspected: `press_alt`/`gnss_alt` are always floats, never `None`, so that heuristic would never have
   fired against real data anyway (`specs/003-igc-ingest-analysis/research.md`).
3. **Thermals**: keep only climbing circles — `[t for t in flight.thermals if t.alt_change() > 0]`.
   ⚠ libigc flags *any* circling as a thermal, including descending spirals and wingovers, both of which
   are routine in paragliding. Without this filter `best_climb` and `avg_climb` are poisoned. Verified
   against a generated fixture with one genuine climbing thermal (`tests/backend/fixtures/valid_flight.igc`).
4. **Tuning is config, not constants.** `libigc.FlightParsingConfig` overrides live under `igc.parsing:`
   in `config.yml` and every resolved value is logged at startup — but the real parameter names, checked
   against the installed 1.2.0 source, are **`min_bearing_change_circling`**,
   **`min_time_for_bearing_change`**, and **`min_time_for_thermal`** — not the four differently-named,
   `_s`/`_deg`-suffixed ones an earlier draft of this section guessed. There is no separate glide-tuning
   parameter: a glide is simply the gap between two thermals. `core/igc.py` builds a small
   `FlightParsingConfig` **subclass** from the resolved config values and passes the subclass (not an
   instance) to `create_from_file`'s `config_class=` argument — that's the shape the library expects.
   Paraglider thermals are slower and sloppier than the sailplane defaults; these will need iteration
   against real tracks.
5. **Glide ratio** = Σ(track_length of descending glides) / Σ(−alt_change of descending glides). This is
   an **over-ground** ratio including air-mass lift, not the wing's still-air L/D. The aggregate form is
   deliberate: one shallow segment cannot inflate it.
6. **`best_climb_ms` is the best thermal *average*, not the instantaneous peak** — peaks are GPS noise.
   `peak_climb_ms` from a 10 s rolling window (`core/igc.py`'s `_peak_climb_ms`, a two-pointer sliding
   window) is a separate, clearly named field.
7. `analyzer_version` is persisted per track. `POST /api/admin/reanalyze` sweeps every track whose stored
   value doesn't match the running build's `igc.ANALYZER_VERSION` constant — admin-only
   (`require_admin`; this is its first use anywhere in the app), no request body, always a full filtered
   pass, never a partial/targeted one (`specs/003-igc-ingest-analysis/research.md`).

### IGC storage

Content-addressed on disk, never a BLOB:

```
<storage.igc_dir>/<owner_id>/<upload_year>/<sha256>.igc
```

Sharded by the **upload** year, not the flight's own year — `create_from_file` needs a real file on
disk before it can be parsed to learn which year a track actually flew in, so sharding by upload time
avoids that ordering problem. `igc_tracks.track_simplified_json` (not a separate `.track.json` file)
holds the derived, regenerable reduced-resolution point series — `[offset_s, lat, lon, alt_m]` per
point, capped at 500 points — and backs both the map view and the barogram from one field, without a
raw-file re-parse on ordinary viewing.

Content addressing gives deduplication and idempotent re-upload for free within *this* app
(`UniqueConstraint(owner_id, sha256)` on both `igc_tracks` and `igc_pending_uploads`). It does **not**
by itself solve the device-vs-XContest cross-source duplicate problem an earlier draft of this section
claimed — two different loggers recording the same real flight produce different bytes and therefore
different hashes; nothing in v0.5 attempts fingerprint-level near-duplicate detection across sources.
The DB keeps `original_filename` for display.

### `igc_segments` — the VidFactory contract

`kind ∈ thermal | glide | takeoff | landing | max_alt | top_of_climb`. `top_of_climb` is the exit fix of
whichever kept thermal has the best `vertical_velocity()` — the peak of the pilot's best climb, not a
per-thermal marker.

**`start_offset_s` (seconds since takeoff) is the load-bearing field.** VidFactory maps it onto a video
timeline with one addition, knowing its own `video_start_utc`. Absolute `start_at` is stored too, so a
camera that started rolling before takeoff can still be aligned.

**Never return video-relative offsets from this service** — it has no idea when the camera started.

Storing segments is what makes the highlight query an indexed `ORDER BY` instead of an IGC re-parse.

### Attaching an uploaded IGC to a flight

The Excel records no time of day and **117 days carry more than one flight**, so date alone is not
enough to guess a flight automatically — which is exactly why there is only one attach path.

- **Upload from the flight's own edit form** (`POST /api/flights/{id}/igc`) — unambiguous by
  construction, since the pilot picks the flight. A second upload for a flight that already has a
  track replaces it wholesale (new segments and site observations, old ones deleted first), never
  accumulates a second row.
- **Writeback shrinks the problem for any future matching feature**: every attach (`_attach_track` in
  `api/routers/igc.py`) writes `flights.takeoff_time` / `landing_time` from the track's takeoff/
  landing fixes, and a detach clears them back to `NULL`.

**Bulk upload (`POST /api/igc/bulk`) and its `igc_pending_uploads` review queue were removed in
v0.8.1.** Shipped in v0.5 with a same-day duration-matching heuristic (auto-attach only when
`|Δ| ≤ 3 min` **and** the runner-up candidate is `> 10 min` away), it mismatched real flights in
practice — the pilot's own words: "bulk imported and it got horribly wrong." Rather than debug the
heuristic, the feature was dropped outright: the per-flight path above already covers the real need
and can never guess wrong, since there's no candidate scoring to get wrong. See the "Tables that do
NOT exist" section above for `igc_pending_uploads` and `core/reset_igc.py`, the one-shot script that
shipped alongside the removal to clean up data the bad heuristic had already written.

---

## Statistics

**Shipped v0.7** (`specs/005-statistics/`). Nothing is materialised — every figure is a read-time
aggregate assembled by `core/stats.py`. One batched load per call (`_load_owner_data`) fetches the
owner's flights plus every reference row needed to resolve them (sites, `user_site_prefs`, categories,
gliders, harnesses, regions, `flight_buddies`), then every other function is pure Python over that
in-memory set — this deliberately does not reuse `core/flights.py`'s `compute_altitude_figures()`, which
does a per-flight `db.get()` and would be the exact N+1 this section already warns against. Only the IGC
thermal-climb rollup stays a genuine SQL aggregate (`SUM(igc_segments.alt_change_m) WHERE kind =
'thermal'`), since `igc_segments` isn't otherwise loaded for any other figure on the page.
`launch_technique_split()`/`hike_fly_total()` are pure functions over a flight list, matching
`06-testing-conventions.md`'s own pinned example — a test can duck-type flights with `SimpleNamespace`
and skip the database entirely.

Four deliberate disagreements with the Excel's `Übersicht` sheet — **confirm these, do not "fix" them**:

1. The workbook's reverse-launch share (33.5%) is computed over a stale `$N$2:$N$499` range and misses
   102 flights. The correct figure is 209/600 ≈ 34.8% — confirmed again live against the real (now
   603-flight) dev database, where `/api/stats/launch-technique` reports 209 reverse of 603 total
   (34.66%): the reverse count is unchanged at 209, the denominator has simply grown by the 3 flights
   added since the original 600-row import, exactly as FR-001 requires ("computed live... not a stale
   snapshot").
2. The workbook's twelve region counts sum to **596**, not 600. **Root cause, confirmed by reading the
   formulas directly** (`specs/001-core-data-import/research.md`): three launch sites (`Ober
   Burgfeldstand`, `Lauberhorn`, `Alp Unterburgfeld`) were added to the workbook after its initial
   version. Every yearly column's `Flight Area` SUM formula was updated to include the new launch rows,
   but the `Total` column's formula was not — it still only sums the original set. A fourth site,
   `Fiescheralp`, is genuinely unreferenced by any region formula, in any column. The importer's own
   `SITE_REGION` mapping (`src/flightlog/core/aliases.py`) is reconstructed from the more complete
   yearly formulas, so it reproduces a *different* residual mismatch than the raw 596-vs-600 gap: it
   counts more flights for `Interlaken` and `Grindelwald` than the stale Total column does, and shows
   `Fiescheralp`'s one flight as genuinely unmapped. Both numbers are reported side by side
   (`ImportReport.region_mismatches`); neither is silently treated as correct.
3. Row 387's stored `Altgain` (350) disagrees with `max_alt_m − launch_elev` (1930 − 1930 = 0) — the one
   altitude-figure mismatch found across all 600 flights by the importer's formula cross-check
   (`ImportReport.altgain_mismatches`). Reported, never overwritten in either direction. `/api/stats/totals`
   sums the app's own computed `alt_gain_m`, never the stored `Altgain` column, so this fix is baked into
   `total_alt_gain_m` automatically: confirmed live where the sheet's reference `Total Altgain (m)` of
   61191 and the app's own 60841 differ by exactly 350 — this one row's correction, with the remaining gap
   fully explained (no unexplained residual).
4. `Übersicht`'s own `Buddys` tally (`Tom` 141, `Ueli` 61, `Simon` 16, `Päsci` 36) uses a different name
   set and different counts than the v0.2 import's comment-scan buddy proposals (`Tom` 134, `Ueli` 61,
   `Simon` 16, plus `Susi`/`Tigi`/`Jürg`/`Beni`, none of which appear in `Übersicht`'s block at all) —
   discovered while planning v0.7 (`specs/005-statistics/research.md`). Neither is a formula bug like the
   two above: the workbook's tally is a manually-kept count, the comment-scan is a derived regex signal
   over free text — two genuinely different data sources for the same real-world fact. `/api/stats/matrix/
   buddy` deliberately reconciles neither: it computes only over `flight_buddies` rows that actually exist
   (as of this writing, likely zero — nothing has ever auto-created one, per v0.2's FR-017), confirmed live
   where the buddy matrix returns an empty `rows: []` against the real dev database.

**Coaching-oriented additions (v0.7.3), from a direct pilot-review pass, not a new spec cycle**: `/stats`
gained five small features aimed at motivation-with-safety-margins rather than raw volume — `xc_progression()`
(per-year % of flights ≥`_DISTANCE_BOUNDS[0]`km, a deliberately category-name-independent proxy for "real"
XC flying, since `flight_categories.name` is free text a pilot could rename or never use consistently), a
`progression.days_since_last_flight`/`last_flight_date` currency pair (frontend colour-bands it green/
amber/red), a client-side-only site-diversity note ("N% of flights at your top 5 sites") computed from the
already-fetched `matrix/site` response, a client-side-only IGC track-coverage nudge combining `totals.
total_flights` with `igc-rollup.tracks_uploaded`, and a `personal_bests.flight_date` field powering a
"set N days/years ago" column. A safety-incident-category tile (surfacing `Bruchflug`/`Schwarzflug` counts)
was proposed in the same pass and explicitly declined by the pilot — do not re-add it speculatively. The
framing reason behind all of this (why currency is a safety nudge, not a volume push) is a personal-context
decision, not a technical one — see `RESUME.md` and this session's memory record before changing the tone
of any of this copy.

**Chart.js gotcha, hit and fixed in v0.7.2: never store a callback function as a leaf value inside
`chart.options`.** `static/stats.js`'s `barChart()` helper draws each bar's own value on the chart (per
pilot feedback against the deployed instance) via a small inline `afterDatasetsDraw` plugin. The first
version stashed the per-chart formatter function at `chart.options.plugins.barValueLabel.formatter` —
Chart.js treats *any* function found while resolving its `options` tree as a "scriptable option" and
auto-invokes it with its own internal context object, not the bar's value, which crashed every downstream
`Math.round()`/`toFixed()` call the moment the plugin read it back. The fix: stash the formatter directly
on the chart instance (`chart.$barValueLabelFormatter`), entirely outside `options`, where Chart.js's
resolver never looks.

**`database/db.py`'s `_seed_regions()` list and `core/aliases.py`'s `SITE_REGION` values must use
identical spelling for every region name.** `_get_or_create_region` matches by exact string, not fuzzy —
a spelling drift between the two doesn't error, it silently creates a second, orphaned region row on the
next real write. This happened once already: `_seed_regions()` had `"Dürstetten"` (ü) after `aliases.py`
was corrected to the byte-verified `"Därstetten"` (ä), and the live production write against the real
600-row workbook created a duplicate before anyone noticed. Pinned by
`test_real_workbook_import_creates_no_new_regions`, which asserts `regions_written == 0` against the
real workbook — every region name it can produce must already be seeded.

---

## Sharing & public readiness

**Shipped v0.9** (`specs/007-sharing-public-readiness/`). Two new columns
(`flights.visibility`, `users.public_profile_enabled`), one new unauthenticated router
(`api/routers/public.py`), and the deferred v0.2 starter-category seed
(`core/user_seed.py`). This is the first genuinely public, unauthenticated, rate-limited
data-serving surface in the app — `health.py` was already public but serves no pilot data
at all; `/api/public/*` is its second and third consumer of the "absence of a dependency
is what makes a route public" convention (`02-backend-conventions.md`), now extended into
real data exposure for the first time.

**`flights.visibility` is a plain string (`private`\|`unlisted`\|`public`, default
`private`)** — matches every other enum-shaped column in this schema (`buddies.link_state`,
`sites.coord_source`, ...), never a DB-level enum or lookup table. `PUT /api/flights/{id}`
accepts it as one more field on the existing owner-scoped, JWT-gated update — no new route.

**`users.public_profile_enabled` is a plain boolean, opt-in, default `False`.** No new
"profile" table — a public profile is the user row plus a live query over that owner's
`visibility = 'public'` flights, computed at request time, nothing separately stored or
cached. The profile URL reuses the existing opaque `users.id` (a UUID) rather than a new
slug/username column — non-enumerable by construction, with zero schema addition
(`specs/007-.../research.md`). `PUT /api/auth/me` (existing route, v0.1) accepts it as one
more field, the same generic `exclude_unset` update loop as every other profile field.

**`GET /api/public/flights/{id}`** 404s unless `visibility` is `unlisted` or `public`; a
private flight and a genuinely nonexistent id return the byte-for-byte identical
`AppException(404, "ENTITY_NOT_FOUND", "Flight not found")` — one shared raise site
(`public.py`'s `_not_found()`), not two independently-written branches that could drift
apart over time. Same pattern for **`GET /api/public/profiles/{user_id}`**, which 404s
unless `public_profile_enabled` is true, and which only ever lists that owner's
`public`-visibility flights — an `unlisted` flight is reachable exclusively by its own
direct link, never surfaced on its own owner's profile.

**`PublicFlightOut`/`PublicProfileOut` (`models/public.py`) are an explicit field
allowlist**, not inherited from or built on `FlightOut`/`UserOut` — the private schemas
carry fields (email, `hashed_password`, `import_key`, ...) that must never reach this
surface just because a future edit to the private schema happened to add one.

**Rate limiting is `slowapi`** (0.1.10, verified current against PyPI at implementation
time), wired as **per-route `@limiter.limit(...)` decorators inside `public.py` only** —
deliberately not `app.add_middleware(SlowAPIMiddleware)`, which would also throttle every
JWT/API-key-authenticated request and violate FR-008's "authenticated surface unaffected"
requirement. The limit value is a **callable** (`_public_rate_limit()`, reading
`config.api.public_rate_limit` fresh on every request), not a bare string — a literal
string decorator argument freezes at module-import time, before `load_config()` has even
run in the app lifespan, which would make the limit un-testable and un-reconfigurable.
The limiter's `key_func` is `dependencies.client_ip` (X-Forwarded-For-aware, already
trusted elsewhere in this app behind this deployment's Traefik) — not slowapi's own
`get_remote_address` default, which would resolve every visitor to the proxy's own IP and
put them all in one shared bucket. A `RateLimitExceeded` is caught by a dedicated handler
in `main.py` and re-mapped to this app's own `{"error": {"code": "RATE_LIMITED", ...}}`
envelope — never `slowapi`'s own default response shape. `slowapi`'s in-memory limiter
storage does not survive a process restart or scale across multiple app instances; accepted
as-is, matching this project's actual single-container deployment shape
(`specs/007-.../plan.md`'s Risk section).

**`core/user_seed.py` closes a gap open since v0.2's own planning.** `auth.py`'s
`register()` handler had carried a comment since v0.1 saying per-user category defaults
would be seeded from there, guarded by `users.seeded_at IS NULL` — never implemented,
because a starter set only mattered once self-registration was actually live
(`specs/001-core-data-import/research.md`). A self-registered account before v0.9 landed
with zero flight categories and no way to log a flight (`flights.category_id` is `NOT
NULL`). Five generic English categories are seeded — `Thermal`, `Soaring`, `XC`,
`Hike&Fly`, `Sled run` — deliberately **not** the 12 legacy German categories
(`core/aliases.py`'s `CANONICAL_CATEGORIES`), which are this specific pilot's own personal
historical data and include jurisdiction-specific artifacts (`Schwarzflug`, `Prüfung`,
`Startleiter`) that make no sense as a universal default for an arbitrary new pilot.
Written through the exact same `FlightCategory` row shape a manual `POST /api/categories`
creates — every existing validation and editability applies unchanged (FR-011). Idempotent
on `user.seeded_at IS NULL`; never re-runs, and never runs for an admin-created or
already-existing account.

**Two research findings this milestone corrected against real code rather than the
roadmap's stale wording**: the buddy invite/accept/decline flow was already shipped in
v0.2 (`buddies.py`), and `auth.allow_self_registration` was already a working, flippable
flag — neither was rebuilt here. The genuinely open gap was the starter-category seeding
above.

**`bootstrapPage({ anonymous: true })`, not just `{ requireAuth: false }`, for any unauthenticated
page.** `static/public-flight.js`/`public-profile.js` are the first pages in this app that must stay
viewable with zero session at all. `requireAuth: false` alone only skips the "redirect if logged
out" check — it does not stop `bootstrap.js`'s nav rendering from calling `loadCurrentUser()` →
`fetchAuth('/api/auth/me')` whenever `localStorage` happens to hold a token, and a stale/expired
token's failed refresh inside `fetchAuth()` clears storage and redirects to `/login` — exactly wrong
on a page a total stranger must be able to load. Found by a post-implementation review, not by curl
(curl has no `localStorage`, so every curl-based check of a public page looks identical whether or
not this redirect exists) and confirmed with a Node harness importing the real `bootstrap.js` under a
stubbed DOM. `bootstrap.js`'s new `anonymous` option skips the token check and the authenticated
`NAV_LINKS` block entirely, regardless of what a visitor's browser happens to be holding — the only
way to satisfy FR-013's "no leak of whether the visitor is logged in as a different pilot entirely."

**Not done in this milestone, by design**: the git-history scrub of
`olddata/Flugbuch.xlsx` (600 flights of personal history, including free-text comments
naming friends) required before the repository itself can go public. A destructive,
hard-to-reverse repository operation — every existing clone/fork keeps the old blob
reachable unless independently re-synced — kept as an explicitly pilot-confirmed action to
perform at the moment the pilot actually decides to make the repo public, never bundled
into a routine feature-implementation step (`04-constraints.md`,
`specs/007-.../research.md`).

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
| `/api/auth` | `auth.py` | **shipped v0.1** — `POST /register` (flag-gated, 201), `POST /login`, `POST /refresh`, `GET /me`, `PUT /me`, `POST /me/password` (204), `GET /registration-status` |
| `/health` | `health.py` | **shipped v0.1** — unauthenticated, the only public router |
| — | `pages.py` | **shipped v0.2:** `/`, `/login`, `/register`. **shipped v0.3:** `/flights`, `/flights/{flight_id}`, `/sites`, `/equipment`. **shipped v0.5:** `/igc`. **shipped v0.6:** `/hikes`, `/groundhandling`, `/tandem-flights`, `/goals`. **shipped v0.7:** `/stats`. **v0.7.5:** `/contacts` added; `/import` removed (see `/api/import-report`'s row — the backend endpoint and its frozen data are untouched, only the page is gone). **v0.8:** `/api-keys` added (key management UI). **v0.8.1:** `/igc` removed along with bulk upload (see `igc.py`'s row) — IGC tracks are attached only from a flight's own edit page now, which already had this since v0.5. **v0.9:** `/public/flights/{flight_id}`, `/public/profiles/{user_id}` added — a distinct `/public/...` prefix from the existing authenticated `/flights/{id}`, no JWT, no redirect-to-login. **v0.9.4:** `/categories` (owner-scoped category CRUD/reorder/archive UI — `/api/categories` had been owner-scoped since v0.2 with no page ever built against it) and `/profile` (the real account-settings home: display name, password change, the public-profile toggle moved off `/api-keys`) added. All `include_in_schema=False` |
| `/api/regions` | `regions.py` | **shipped v0.2** — `GET` only, shared reference data |
| `/api/sites` | `sites.py` | **shipped v0.2**, **behavior changed v0.3** — CRUD + `PUT /{id}/prefs`; `POST`/`PUT` now set `coord_source = "manual"` server-side whenever the request includes a non-null `lat` and/or `lon` (no schema change — `coord_source` is never accepted from the client). `coord_source = "igc_median"` also now written, but only ever by `core/site_backfill.py` (v0.5), never through this HTTP surface |
| `/api/gliders` `/api/harnesses` | `gliders.py`, `harnesses.py` | **shipped v0.2** — CRUD + `POST /{id}/retire` |
| `/api/categories` | `categories.py` | **shipped v0.2** — CRUD + `PUT /reorder` + `POST /{id}/archive` |
| `/api/buddies` | `buddies.py` | **shipped v0.2** — CRUD + `POST /{id}/link` (always 202) + `/link/accept` + `/link/decline`. **`/contacts` (v0.7.5)** is the first UI ever built against this router's create/update/delete surface — Phase 9 of `specs/002-flight-log-ui` had spec'd it since v0.3 but it was never implemented until a pilot explicitly asked why they couldn't add buddies |
| `/api/flights` | `flights.py` | **shipped v0.2** — CRUD; `GET` responses include computed `alt_gain_m` / `site_drop_m` / `total_descent_m`. **v0.7.4**: `FlightOut.has_igc_track` — the list endpoint batches one `IgcTrack.flight_id IN (...)` query for the page rather than checking `flight.igc_track` per row (the N+1 `04-constraints.md` warns about); single-flight routes check directly, since that's one row. **v0.8**: `FlightOut.links` — one small per-flight `FlightLink` query in every response (list included), same precedent as `buddy_ids`; surfaces any VidFactory-pushed link on the pilot's own flight-detail page with no action needed (FR-009) |
| `/api/import-report` | `import_report.py` | **shipped v0.3, page removed v0.7.5** — `GET` only, not owner-scoped; always returns `core/import_history.py`'s frozen `HISTORICAL_IMPORT_SUMMARY`, never re-runs the importer. The `/import` HTML page and its nav link are gone (a pilot's own live feedback: "outdated and not needed") but this endpoint and `core/import_history.py` are deliberately untouched — kept in case the frozen snapshot is ever wanted again |
| — | `core/importer.py` | **shipped v0.2** — `python -m flightlog.core.importer [--write] [--path FILE]`, no HTTP route |
| `/api/flights/{id}/igc`, `/api/admin/reanalyze` | `igc.py` | **shipped v0.5** — see IGC analysis section below and `specs/003-igc-ingest-analysis/contracts/endpoints.md`. First use anywhere in the app of `require_admin` (`/api/admin/reanalyze`) and of a multipart/`UploadFile` route. **v0.8.1**: `POST /api/igc/bulk` and `/api/igc/pending/*` (list/resolve/dismiss) removed — see "Attaching an uploaded IGC to a flight" above |
| `/api/hikes`, `/api/groundhandling`, `/api/tandem-flights` | `hikes.py`, `groundhandling.py`, `tandem_flights.py` | **shipped v0.6 as import-and-view only ("no `POST`/`PUT`/`DELETE`" — that line is now stale, corrected below), full CRUD added v0.7.5** — a pilot could import historical rows but never add a new one going forward, which a live pilot-feedback pass flagged directly. `HikeCreate`/`HikeUpdate` add an optional `flight_id` a pilot can set/clear by hand (never ownership-validated, matching `flights.py`'s own cross-referenced-id convention for `launch_site_id`/`category_id`); `import_key` stays server-only across all three, exactly as it already was for `goals.py` |
| `/api/goals` | `goals.py` | **shipped v0.6** — full CRUD + `POST /{id}/mark-done`; the one imported type in this milestone that stays editable — `import_key` is never accepted from the request body |
| — | `core/secondary_import.py` | **shipped v0.6** — `python -m flightlog.core.secondary_import [--write] [--path FILE]`, no HTTP route; imports `Fitnessprogramm`/`Groundhandling`/`Tandemflüge`/`Ziele`. XContest "My Flights" score import (originally scoped alongside this milestone) has moved to `features.md`'s Backlog — no real export sample was available; see `specs/004-secondary-sheets-xcontest/research.md` |
| `/api/stats` | `stats.py` | **shipped v0.7, extended v0.7.2–v0.7.5** — 10 `GET`-only, owner-scoped endpoints (`totals`, `time-breakdown`, `distribution`, `monthly-extremes`, `xc-progression`, `personal-bests`, `matrix/{dimension}`, `launch-technique`, `igc-rollup`, `progression`); no new tables, every figure a read-time aggregate over `core/stats.py`. `matrix/{dimension}` takes a plain `str` + allowlist, not `Literal[...]`, so an unknown dimension is `404 ENTITY_NOT_FOUND` rather than FastAPI's own `422`. All of `monthly-extremes`, `xc-progression`, `personal-bests.flight_date`, and `progression.days_since_last_flight`/`last_flight_date` were added post-ship, per direct pilot feedback against the deployed `fl.sdh.lol` instance rather than a new spec cycle — see this section's "Coaching-oriented additions" note below. **v0.7.5**: `ProgressionOut.cumulative_series` (and the `ProgressionPoint` schema, `core/stats.py`'s `cumulative_progression()`) were removed entirely — a running total by date is monotonically increasing by construction and the pilot correctly flagged the chart it fed as useless (a straight line, no information). Replaced by a frontend-only "monthly flights per year, overlaid" line chart built from `TimeBreakdownOut.year_month_matrix` (already fetched for the year×month table) — no new backend endpoint or field needed |
| `/api/keys` | `api_keys.py` | **shipped v0.8** — JWT-authenticated (`get_current_user`), pilot's own browser session. CRUD-shaped: `GET`/`POST`, `POST /{id}/revoke`, `DELETE /{id}`. `POST` returns the full plaintext key exactly once, never again — no endpoint can retrieve it after creation. `DELETE` requires the key already revoked (`409 CONFLICT` otherwise) — a deliberate two-step precondition, unlike `gliders.py`'s independent retire/delete |
| `/api/integration/v1` | `integration.py` | **shipped v0.8** — API-key-authenticated (`get_api_principal` + `require_scope`, `X-API-Key` header), for an external tool (VidFactory). `GET /flights/{id}` (`flights:read`) returns `FlightMetadataOut` — resolved **names** (site/glider/harness/category), not bare ids like the JWT-gated `FlightOut`, since an external caller has no other way to resolve them; also merges in `igc_summary` (the same `thermal_count`/`best_climb_ms`/`peak_climb_ms`/`glide_ratio`/`alt_gain_igc_m` already on `igc_tracks`, not in the original spec's metadata list but a deliberate v0.8 addition since a highlight video wants those numbers as captions) and any `links`. `GET /flights/{id}/segments` (`flights:read`) returns `igc_segments` verbatim — `kind` ∈ thermal\|glide\|takeoff\|landing\|max_alt\|top_of_climb; a "sink" moment is a `glide` segment with `alt_change_m < 0`, not a separate stored kind. `PUT /flights/{id}/links/{kind}/{external_id}` (`flight_links:write`) is the idempotent create-or-replace push-back. Every route 404s on a flight that doesn't exist or isn't owned by the key's pilot, 403s on a right-key-wrong-scope request — never a 404-that-would-leak-existence or a hint about what a correctly-scoped key would see. Frozen contract, versioned separately from the UI's models |
| `/api/public` | `public.py` | **shipped v0.9** — **unauthenticated by design**, no auth dependency anywhere in the file, rate-limited via `slowapi` (independent of the authenticated surface). `GET /flights/{id}` 404s unless `visibility` is `unlisted`\|`public`; `GET /profiles/{user_id}` 404s unless `public_profile_enabled`. Both 404 byte-identically whether the row is missing or simply not public — never a distinguishing signal. `PublicFlightOut`/`PublicProfileOut` (`models/public.py`) are an explicit field allowlist, not derived from `FlightOut`/`UserOut`. See "Sharing & public readiness" above |
| `/api/flights/{id}` visibility | `flights.py` | **v0.9**: `PUT` accepts one more field, `visibility` (`private`\|`unlisted`\|`public`) — no new route, no schema change beyond the field itself |
| `/api/auth/me` public profile | `auth.py` | **v0.9**: `PUT` accepts one more field, `public_profile_enabled` — same generic update path every other profile field already uses |

Routes are not enumerated here beyond the prefix — **read the router file, which is the source of truth.**

---

## Deployment

### Hostnames

| Environment | Host | Port |
|---|---|---|
| dev | `fl-dev.sdh.lol` | 8002 → 8000 |
| prod | `fl.lenti.cloud`, `flightlog.lenti.cloud` | via Traefik |

**Prod moved off `sdh.lol` (2026-08-17)**: `fl.sdh.lol` is retired — prod now answers on two
`lenti.cloud` hostnames instead. The whole-host Traefik `traefik-oidc-auth` (Pocket-ID) SSO layer
that previously fronted `fl.sdh.lol` (see `flightlog_prod_oidc_layer` memory) was removed as part
of this move — the service is now genuinely reachable by anonymous strangers with no SSO
challenge, which is what makes v0.9's `/public/*` surface actually usable in production rather
than just shipped. This was a pilot-owned change to shared homelab infrastructure, performed
outside this repo (`04-constraints.md`: never touch prod directly).

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

### Runtime — Python 3.14 is proven, with one caveat

`python:3.14-slim` built and pushed **multi-arch (amd64 + arm64) in 5m29s** on the v0.1.0 tag, and CI
passes on both 3.13 and 3.14. The plan's fallback to 3.13 was not needed.

**Updated for v0.5, now proven, not just de-risked**: `libigc` is actually installed (CI's test job and
the Dockerfile both run `poetry install --extras igc`, not just declare the extra). The `v0.5.0` tag's
multi-arch (amd64 + arm64) build — the first to carry this extra — completed in 5m1s, confirming the
PyPI file-metadata check made before enabling it (`libigc` ships a universal `py3-none-any` wheel, its
transitive `simplekml` dependency is a pure-Python sdist): neither reintroduced the QEMU/arm64
compilation risk this section originally flagged.

`requires-python = ">=3.13,<4.0"`: 3.13 is what local development runs, 3.14 is what the image ships,
and the CI matrix covers both so a runtime upgrade is proven rather than assumed.

### The first tagged release does not dispatch its own publish workflow

A tag pushed in the **same push that first introduces the workflow file** does not trigger it — the tag
event is evaluated before the new workflow is registered for that ref. This happened on v0.1.0: `main`
and `v0.1.0` went up together, only "Backend tests" ran, and the tag had to be deleted and re-pushed:

```bash
git push origin :refs/tags/vX.Y.Z && git push origin vX.Y.Z
```

The publish workflow now also has a `workflow_dispatch` trigger, so this can be resolved without
touching tags — and an image can be rebuilt for a base-image security fix without minting a release.

### Versioning

`pyproject.toml`'s version is both the image tag source and the static-asset cache key. A static change
without a version bump leaves returning users on the old file for up to a year. See the version
resolution note above — the resolution path matters as much as the bump.

Images publish to `ghcr.io/think4dvantage/flightlog`, tagged `vX.Y.Z`, `X.Y.Z`, `X.Y`, `X` and `latest`
from a single 3-part semver tag. Tags must be 3-part or the `metadata-action` semver patterns silently
do not activate.
