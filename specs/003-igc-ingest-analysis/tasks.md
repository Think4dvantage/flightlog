# Tasks: IGC Ingest & Analysis

Spec: [`spec.md`](./spec.md) · Plan: [`plan.md`](./plan.md) · Data model: [`data-model.md`](./data-model.md)
· Contracts: [`contracts/endpoints.md`](./contracts/endpoints.md) · Research: [`research.md`](./research.md)

## Summary

- Total tasks: 35
- Parallel opportunities: 10 (marked `[P]`)
- MVP scope: Phase 3 (US1 — single-flight upload with computed figures) is the smallest
  independently-shippable slice, matching `spec.md`'s P1 priority.

Test tasks are included throughout (`06-testing-conventions.md`: backend logic is test-gated; matches
both prior features' precedent). No frontend test tasks, consistent with `specs/002-flight-log-ui`.

## Dependencies

```
Phase 1 (Setup) ─> Phase 2 (Foundation: config, tables, storage, core/igc.py, schemas) ─┬─> Phase 3  US1 single upload + figures
                                                                                          │        │
                                                                                          │        v
                                                                                          │   Phase 4  US2 map + barogram + segments
                                                                                          │        (extends US1's flight-detail work)
                                                                                          │
                                                                                          ├─> Phase 5  US4 site coordinate backfill
                                                                                          │        (wires into US1's upload/detach — after Phase 3)
                                                                                          │
                                                                                          ├─> Phase 6  US3 bulk upload + resolution
                                                                                          │        (reuses core/igc.py from Foundation; independent
                                                                                          │         page, no dependency on Phase 3/4/5's files)
                                                                                          │
                                                                                          └─> Phase 7  US5 admin re-analysis
                                                                                                   (reuses core/igc.py; independent of 3-6)

Final Phase — Polish: after everything above.
```

Phase 5 needs Phase 3's upload/detach endpoints to exist (it hooks into them), so it follows Phase 3
even though it's a different user story. Phases 4, 6, 7 each depend only on Phase 2 and can proceed in
any order relative to each other.

---

## Phase 1 — Setup

- [x] T001 [P] Re-verify `libigc`, Chart.js, and Leaflet are still the latest stable releases (PyPI JSON
      API, `gh api repos/chartjs/Chart.js/releases/latest`, `gh api repos/Leaflet/Leaflet/releases/latest`)
      — confirmed `libigc` 1.2.0 / `v4.5.1` / `v1.9.4` at planning time (`research.md`)
- [ ] T002 [P] Create `tests/backend/fixtures/` IGC files: a valid multi-thermal flight, a flight with no
      barometric fixes, a corrupt/truncated file, and a same-day two-flights pair (for bulk-match
      ambiguity testing) — needed by nearly every test task below

## Phase 2 — Foundation

- [ ] T003 Add `IgcParsingConfig` / `IgcConfig` to `src/flightlog/config.py` and an `igc.parsing:` block
      to `config.yml.example`, logged at INFO on startup like every other config section
- [ ] T004 [P] Add `IgcTrack`, `IgcSegment`, `SiteObservation`, `IgcPendingUpload` ORM models to
      `src/flightlog/database/models.py` per `data-model.md`
- [ ] T005 Install the `igc` extra locally and resolve `research.md`'s two open items against the real
      package (per-fix `press_alt`/`gnss_alt` field shape; `FlightParsingConfig`'s actual parameter names
      and defaults) — finalizes T003's config keys and the altitude-source logic in T007
- [ ] T006 Create `src/flightlog/core/igc_storage.py` — sha256 + content-addressed write/read under
      `storage.igc_dir` (`<owner_id>/<YYYY>/<sha256>.igc`), `storage.max_igc_bytes` enforcement
- [ ] T007 Create `src/flightlog/core/igc.py` — `libigc.Flight.create_from_file` wrapper: reject
      `not flight.valid`; altitude-source selection; thermal filter (climbing circles only, per
      `architecture.md` rule 3); glide ratio; `best_climb_ms` / `peak_climb_ms`; segment extraction;
      `track_simplified_json` generation; `ANALYZER_VERSION` constant
- [ ] T008 [P] Create `src/flightlog/models/igc.py` — Pydantic response schemas
      (`IgcTrackOut`, `IgcSegmentOut`, `IgcTrackGeoJsonOut`, `BulkUploadOutcomeOut`,
      `IgcPendingUploadOut`, `ReanalyzeResultOut`) per `contracts/endpoints.md`

---

## Phase 3 — Upload a flight's track and see it analyzed [US1]

**Goal**: a pilot can upload a flight's IGC file from that flight's own record and see real duration,
distance, altitude gain, thermal count, best climb, and glide ratio instead of hand-typed estimates.
**Independent test criteria**: upload a valid fixture to a flight, see every FR-005 figure populated
correctly; re-upload the same file (no-op, no duplicate); upload a different file (replaces cleanly);
upload a corrupt file (rejected with a specific reason, nothing written).

- [ ] T009 [US1] Create `src/flightlog/api/routers/igc.py` with `POST /api/flights/{id}/igc` — multipart
      upload, `asyncio.to_thread`-offloaded analysis, create-or-replace semantics (FR-004), same-sha256
      no-op (FR-003), size/validity rejection with a specific reason (FR-002)
- [ ] T010 [US1] Add `GET /api/flights/{id}/igc` (summary, 404 if none) and
      `DELETE /api/flights/{id}/igc` (detach, FR-012) to `igc.py`
- [ ] T011 [US1] Register the `igc` router in `src/flightlog/api/main.py`
- [ ] T012 [US1] [P] `tests/backend/test_igc_upload.py` — upload, replace, dedup no-op, rejection, detach,
      all against the T002 fixtures
- [ ] T013 [US1] Add an upload/replace/detach control and the six computed figures to
      `static/flight-detail.html` / `static/flight-detail.js`
- [ ] T014 [US1] [P] Add `igc.*` i18n keys for the upload control and figure labels to
      `static/i18n/en.json`

## Phase 4 — Track map and altitude chart with thermal/glide segments [US2]

**Goal**: a pilot can see the track on a map and an altitude-over-time chart with climbing and gliding
parts visually distinguished.
**Independent test criteria**: after a Phase 3 upload, `/flights/{id}` shows a map line matching the
fixture's route and a barogram whose thermal/glide bands match the fixture's known segments.

- [ ] T015 [US2] Add `GET /api/flights/{id}/igc/segments` to `igc.py`
- [ ] T016 [US2] Add `GET /api/flights/{id}/igc/track.geojson` to `igc.py`
      (`LineString` with `[lon, lat, alt_m]` coordinates + `properties.offsets_s`)
- [ ] T017 [US2] [P] Extend `tests/backend/test_igc_upload.py` (or a new `test_igc_view.py`) for
      segments/geojson response shape
- [ ] T018 [US2] Add a Leaflet track map to `flight-detail.html` / `.js`, reusing the vendored copy
      `/sites` already uses
- [ ] T019 [US2] Add a Chart.js barogram with thermal/glide band highlighting to `flight-detail.html` /
      `.js` — first real use of the vendored `static/vendor/chartjs/chart.umd.js`
- [ ] T020 [US2] [P] Add map/chart i18n keys to `en.json`

## Phase 5 — Site coordinates fill in automatically from tracks [US4]

**Goal**: once a site has ≥3 tracked flights, its map location is set automatically without a manual pin
— and never overwrites a pin the pilot placed by hand.
**Independent test criteria**: upload 3 fixtures sharing a launch site with no coordinates yet; the site
gets a real `lat`/`lon` and `coord_source="igc_median"`; a manually-pinned site never changes regardless
of how many tracks accumulate; detaching a track that was one of the 3 drops the site back below
threshold and clears the auto-set coordinates.

- [ ] T021 [US4] Create `src/flightlog/core/site_backfill.py` — insert `site_observations` on a
      successful upload, recompute the median at the ≥3 threshold, skip entirely when
      `coord_source == "manual"`
- [ ] T022 [US4] Wire `site_backfill` into T009's upload path and T010's detach path — a replace or
      detach must remove the track's old observations before any recompute (FR-004/FR-012)
- [ ] T023 [US4] [P] `tests/backend/test_site_backfill.py`

## Phase 6 — Bulk upload with automatic matching and manual resolution [US3]

**Goal**: a pilot can upload many IGC files at once; unambiguous matches attach automatically, everything
else is queued for manual resolution, never guessed.
**Independent test criteria**: bulk-upload the T002 same-day-two-flights pair plus one clearly
unambiguous fixture; the unambiguous one auto-attaches, the ambiguous pair both land in
`igc_pending_uploads`; resolving one attaches it and removes it from the pending list.

- [ ] T024 [US3] Implement the bulk-match algorithm in `core/igc.py` (date + duration scoring,
      auto-attach only when `|Δ| ≤ 3 min` **and** runner-up `> 10 min` away, per `architecture.md`)
- [ ] T025 [US3] Add `POST /api/igc/bulk` to `igc.py` — per-file outcome (`auto_attached` /
      `needs_resolution` / `rejected`), writing unresolved files to `igc_pending_uploads`
- [ ] T026 [US3] Add `GET /api/igc/pending`, `POST /api/igc/pending/{id}/resolve`,
      `DELETE /api/igc/pending/{id}` to `igc.py`
- [ ] T027 [US3] [P] `tests/backend/test_igc_bulk.py`
- [ ] T028 [US3] Create `static/igc.html` / `static/igc.js` — multi-file upload, per-file outcome list,
      resolve/dismiss actions for pending rows
- [ ] T029 [US3] Add `GET /igc` route to `src/flightlog/api/routers/pages.py`; nav entry ("Tracks") in
      `static/bootstrap.js`
- [ ] T030 [US3] [P] Add bulk-page and nav i18n keys to `en.json`

## Phase 7 — Administrator re-analysis [US5]

**Goal**: an administrator can re-run analysis on already-uploaded tracks without re-upload.
**Independent test criteria**: bump the code's `ANALYZER_VERSION` constant in a test, call the endpoint
as an admin account, confirm stale tracks are reprocessed and their `analyzer_version` updated; confirm
403 for a non-admin pilot account.

- [ ] T031 [US5] Add `POST /api/admin/reanalyze` to `igc.py`, gated by the existing `require_admin`
      dependency (its first use anywhere in the app)
- [ ] T032 [US5] [P] `tests/backend/test_igc_reanalyze.py`

## Final Phase — Polish

- [ ] T033 Live-boot verification pass per `plan.md`'s Phase 8 checklist: real single-file upload
      cross-checked by hand, replace, bulk ambiguous pair, site backfill threshold and manual-pin
      protection, admin-only re-analysis
- [ ] T034 `ruff check` / `ruff format --check` / full `pytest` clean; bump `pyproject.toml`'s version
      (static assets and backend both changed — the version is the cache key)
- [ ] T035 `sync.md` — update `architecture.md` (IGC analysis section, SQLite Tables list, API Contracts
      table), `features.md` (mark v0.5 shipped), and `RESUME.md` with what actually shipped, including
      resolving `research.md`'s two open items with what T005 actually found
