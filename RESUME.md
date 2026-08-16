# Resume Notes — 2026-08-16

## In Progress

**`v0.8.1` is implemented, tested, live-verified, docs-synced, version-bumped, committed,
tagged, and pushed this session.** This picks up straight from the prior session's `v0.8.0`
ship (see git log / the section below this one for that history).

### What shipped in `v0.8.1`

Triggered directly by the pilot: a real bulk IGC import against `fl.sdh.lol` mismatched
flights ("I have bulk imported and it got horribly wrong"), and the ask was to remove bulk
import outright, confirm direct per-flight linking already exists, and reset the bad data —
as one release.

1. **Bulk upload + its pending-review queue removed entirely**, not just hidden (unlike the
   `/import` page's v0.7.5 precedent): `POST /api/igc/bulk`, `GET /api/igc/pending`,
   `POST /api/igc/pending/{id}/resolve`, `DELETE /api/igc/pending/{id}`, the `/igc` page
   (`static/igc.html`/`igc.js` deleted), its nav entry (`bootstrap.js`), its i18n block
   (`nav.tracks` + the whole `igc.*` key tree in `en.json`), the `IgcPendingUpload` model, and
   `_find_bulk_match`/the two `AUTO_MATCH_*` constants in `api/routers/igc.py`.
2. **No new work was needed for "link an IGC file from the flight edit page"** — confirmed
   before touching anything that `/flights/{id}`'s edit form already has full unambiguous
   upload/replace/detach (`POST`/`DELETE /api/flights/{id}/igc`, `flight-detail.html`/`.js`)
   since v0.5. That was always the primary attach path; bulk was always the secondary one.
3. **`core/reset_igc.py`** — new one-shot script, `python -m flightlog.core.reset_igc
   [--write]` (dry-run default, mirrors `core/importer.py`'s shape). Deletes every
   `igc_tracks`/`igc_segments`/`site_observations` row, drops the now-modelless
   `igc_pending_uploads` table outright (raw SQL — no ORM model left to delete through), and
   undoes the two side effects those tracks wrote elsewhere: nulls `flights.takeoff_time`/
   `landing_time` (the legacy workbook has no time-of-day anywhere, so every value there came
   from a track) and clears any site's `coord_source == "igc_median"` coordinate (a median of
   the observations being deleted). Not owner-scoped — one pilot account, same assumption the
   importer makes.
4. **Run against local dev**: `data/flightlog.db` had 3 `igc_tracks` / 21 `igc_segments` / 3
   `site_observations` / 2 `igc_pending_uploads` / 1 `igc_median` site — all cleared, 5 `.igc`
   files deleted from `data/igc/`. 0 flights had `takeoff_time`/`landing_time` set, so that
   side effect was a no-op locally; the pilot's real damage is on `fl.sdh.lol`, not this dev
   DB.
5. **3 new tests** (`tests/backend/test_reset_igc.py`), `test_igc_bulk.py` deleted with the
   feature it tested — 211/211 passing project-wide, `ruff check`/`ruff format --check` clean.
6. **Live-boot verified via `curl`**: `/igc` and every bulk/pending route now 404,
   `/api/flights/{id}/igc` + `segments`/`track.geojson` still resolve, `/health` reports
   `0.8.1`, the rendered `/flights` HTML has no leftover `nav.tracks`/`/igc` reference.
7. **Docs synced**: `architecture.md` ("Attaching an uploaded IGC to a flight" section
   rewritten — bulk path removed; `igc_pending_uploads` moved into "Tables that do NOT exist"
   with the removal story; API Contracts table's `igc.py`/`pages.py` rows updated),
   `01-project-overview.md` (Repository Layout: fixed `igc_store.py` → `igc_storage.py`,
   removed the never-real `igc_match.py`, added `reset_igc.py`), `features.md` (this v0.8.1
   write-up), `README.md` (new v0.8.1 paragraph). `pyproject.toml` bumped `0.8.0` → `0.8.1`
   (`poetry install` re-run so `APP_VERSION` isn't stale).

## Next Step

1. **Run the reset against prod once the new `v0.8.1` image is live**: `docker exec
   <container> python -m flightlog.core.reset_igc --write` against the real `fl.sdh.lol`
   container — this was deliberately not done from here; `04-constraints.md` forbids direct
   SSH/`docker-compose` on the prod host, so the pilot runs it themselves once
   `docker-publish.yml` has finished and the new image is deployed. Dry-run (no `--write`)
   first to sanity-check the counts before committing to `--write`.
2. **v0.9 (sharing & public readiness)** is fully planned (`specs/007-sharing-public-
   readiness/`) and ready whenever picked back up.
3. **XContest score import** remains a backlog item.
4. **`specs/002-flight-log-ui`'s Phases 10-11** (CSV export, remember-last-filters) — still
   open, not tied to any particular tag.

## Open Questions

- None blocking. Confirm after the prod reset runs: did it find and clear real mismatched
  track data (non-zero counts), matching the pilot's report of a bad bulk import — a
  zero-everywhere result there would be worth a second look before assuming the reset ran
  against the right database.

## Context

- **The whole release is a removal + a cleanup script, not new product surface** — no new
  spec cycle was written for this; scoped directly from the pilot's message via
  `AskUserQuestion` (full removal vs. UI-only, prod-script vs. local-only, reset depth) before
  touching any code.
- **`igc_pending_uploads` is dropped via raw SQL (`DROP TABLE`), not left as an orphaned empty
  table.** `04-constraints.md`'s "no `.sql` migration files, no `_migrations` table" rule
  governs schema *creation*; there's no established convention for dropping a table in this
  codebase, since nothing has ever removed one before. `core/reset_igc.py` is a one-shot
  script the pilot runs by hand, not something `_run_column_migrations()` or app startup ever
  calls — same category as `core/importer.py`, not a new migration mechanism.
- **The dev server needs a restart after every backend edit** (no `--reload`). See
  [[flightlog-dev-server-workflow]].
- **The Windows-only WAL gotcha**: `data/flightlog.db`'s main file is often stale on its own
  — real, current data lives in the accompanying `.db-wal`/`.db-shm` sidecar files until
  SQLite checkpoints them. Copy all three together, or better, just point directly at the
  real path.

This file is a pointer, not a duplicate — `.ai/context/features.md`, `architecture.md`, and
each feature's own `specs/` folder have the detail.
