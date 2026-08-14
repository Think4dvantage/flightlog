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

**T001–T032 done (32/35).** Every backend route in `contracts/endpoints.md`, all four new tables,
`core/igc.py`/`igc_storage.py`/`site_backfill.py`, and every frontend piece — flight-detail's upload/
replace/detach control and eight computed figures, the Leaflet track map, the Chart.js barogram with
per-segment thermal/glide line coloring, and the `/igc` bulk-upload + pending-review page. 17 new
backend tests, 143/143 passing project-wide, `ruff check`/`ruff format --check` clean.

Verified against real, generated IGC fixtures, not fabricated assertions — a genuine climbing thermal
correctly detected and filtered, GNSS altitude-source fallback confirmed for a no-baro file — and
against a live local dev boot via `curl` for every endpoint including the full bulk-upload → ambiguous
→ resolve/dismiss cycle. Two real bugs were caught and fixed only because of that live-boot pass, not
by unit tests alone: `auth.js`'s `fetchAuth()` forced `Content-Type: application/json` onto every
request with a body, silently breaking `FormData` multipart uploads; and dismissing a pending upload
left its `UniqueConstraint("owner_id", "sha256")` slot occupied, silently blocking any later re-upload
of that same file. Both fixed, the second covered by a new regression test.

**Remaining: T033–T035 (Final Phase)** — a real browser has still not rendered any of this (see
[[env-no-browser-extension]]; unavailable all session), the version bump, and the `sync.md` documentation
pass.

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
- [x] T002 [P] Create `tests/backend/fixtures/` IGC files: a valid multi-thermal flight, a flight with no
      barometric fixes, a corrupt/truncated file, and a same-day two-flights pair (for bulk-match
      ambiguity testing) — needed by nearly every test task below. Generated (not hand-written) and
      verified against real `libigc` output — a launch, one genuine climbing thermal, and a glide, with
      realistic ground speeds so libigc's own takeoff/landing detection behaves correctly

## Phase 2 — Foundation

- [x] T003 Add `IgcParsingConfig` / `IgcConfig` to `src/flightlog/config.py` and an `igc.parsing:` block
      to `config.yml.example`, logged at INFO on startup like every other config section
- [x] T004 [P] Add `IgcTrack`, `IgcSegment`, `SiteObservation`, `IgcPendingUpload` ORM models to
      `src/flightlog/database/models.py` per `data-model.md`
- [x] T005 Install the `igc` extra locally and resolve `research.md`'s two open items against the real
      package (per-fix `press_alt`/`gnss_alt` field shape; `FlightParsingConfig`'s actual parameter names
      and defaults) — finalizes T003's config keys and the altitude-source logic in T007. Both resolved:
      `flight.alt_source` is read directly rather than reimplemented; the real parameter names are
      `min_bearing_change_circling` / `min_time_for_bearing_change` / `min_time_for_thermal`, not the
      four originally guessed — see `research.md`
- [x] T006 Create `src/flightlog/core/igc_storage.py` — sha256 + content-addressed write/read under
      `storage.igc_dir` (`<owner_id>/<upload_year>/<sha256>.igc`), `storage.max_igc_bytes` enforcement
- [x] T007 Create `src/flightlog/core/igc.py` — `libigc.Flight.create_from_file` wrapper: reject
      `not flight.valid`; altitude-source selection; thermal filter (climbing circles only, per
      `architecture.md` rule 3); glide ratio; `best_climb_ms` / `peak_climb_ms`; segment extraction;
      `track_simplified_json` generation; `ANALYZER_VERSION` constant. Verified against real, generated
      IGC fixtures, not just unit-level assertions
- [x] T008 [P] Create `src/flightlog/models/igc.py` — Pydantic response schemas
      (`IgcTrackOut`, `IgcSegmentOut`, `IgcTrackGeoJsonOut`, `BulkUploadOutcomeOut`,
      `IgcPendingUploadOut`, `ReanalyzeResultOut`) per `contracts/endpoints.md`

---

## Phase 3 — Upload a flight's track and see it analyzed [US1]

**Goal**: a pilot can upload a flight's IGC file from that flight's own record and see real duration,
distance, altitude gain, thermal count, best climb, and glide ratio instead of hand-typed estimates.
**Independent test criteria**: upload a valid fixture to a flight, see every FR-005 figure populated
correctly; re-upload the same file (no-op, no duplicate); upload a different file (replaces cleanly);
upload a corrupt file (rejected with a specific reason, nothing written).

- [x] T009 [US1] Create `src/flightlog/api/routers/igc.py` with `POST /api/flights/{id}/igc` — multipart
      upload, create-or-replace semantics (FR-004), same-sha256 no-op (FR-003), size/validity rejection
      with a specific reason (FR-002). **Deviation from this task's original wording**: no
      `asyncio.to_thread` wrapper — every route in this file is a plain sync `def` like every other
      router in the app, so FastAPI's own threadpool dispatch already keeps `analyze()` off the event
      loop; see `research.md`'s revised decision
- [x] T010 [US1] Add `GET /api/flights/{id}/igc` (summary, 404 if none) and
      `DELETE /api/flights/{id}/igc` (detach, FR-012) to `igc.py`
- [x] T011 [US1] Register the `igc` router in `src/flightlog/api/main.py`
- [x] T012 [US1] [P] `tests/backend/test_igc_upload.py` — upload, replace, dedup no-op, rejection, detach,
      cross-owner 404, all against the T002 fixtures. 7/7 passing
- [x] T013 [US1] Add an upload/replace/detach control and the eight computed figures to
      `static/flight-detail.html` / `static/flight-detail.js` — verified against a live dev boot via
      `curl` (multipart upload, figures in the response); found and fixed a real bug in the process:
      `auth.js`'s `fetchAuth()` was forcing `Content-Type: application/json` onto every request with a
      body, including `FormData` uploads, which silently breaks multipart encoding
- [x] T014 [US1] [P] Add `flight_detail.track_*` i18n keys for the upload control and figure labels to
      `static/i18n/en.json`

## Phase 4 — Track map and altitude chart with thermal/glide segments [US2]

**Goal**: a pilot can see the track on a map and an altitude-over-time chart with climbing and gliding
parts visually distinguished.
**Independent test criteria**: after a Phase 3 upload, `/flights/{id}` shows a map line matching the
fixture's route and a barogram whose thermal/glide bands match the fixture's known segments.

- [x] T015 [US2] Add `GET /api/flights/{id}/igc/segments` to `igc.py`
- [x] T016 [US2] Add `GET /api/flights/{id}/igc/track.geojson` to `igc.py` — a proper GeoJSON `Feature`
      (`LineString` geometry with `[lon, lat, alt_m]` coordinates + `properties.offsets_s`), not a bare
      geometry object, since only a `Feature` can carry `properties` per the GeoJSON spec
- [x] T017 [US2] [P] Segments/geojson response shape covered in `test_igc_upload.py`'s main upload test
      rather than a separate file — small enough not to warrant one
- [x] T018 [US2] Add a Leaflet track map to `flight-detail.html` / `.js`, reusing the vendored copy
      `/sites` already uses — a plain polyline, deliberately no takeoff/landing markers, sidestepping
      `/sites`' marker-icon-path bug class entirely rather than risking reintroducing it here
- [x] T019 [US2] Add a Chart.js barogram with thermal/glide band highlighting to `flight-detail.html` /
      `.js` — first real use of the vendored `static/vendor/chartjs/chart.umd.js`. No annotation plugin
      (none is vendored); thermal/glide phases are shown by coloring the line itself per-segment via
      Chart.js 4's built-in `segment.borderColor` callback, using new `--warm` / existing
      `--accent-strong` CSS custom properties (a colorblind-safe pairing) read via `getComputedStyle`
- [x] T020 [US2] [P] Map/chart i18n keys folded into T014's `flight_detail.track_*` additions

## Phase 5 — Site coordinates fill in automatically from tracks [US4]

**Goal**: once a site has ≥3 tracked flights, its map location is set automatically without a manual pin
— and never overwrites a pin the pilot placed by hand.
**Independent test criteria**: upload 3 fixtures sharing a launch site with no coordinates yet; the site
gets a real `lat`/`lon` and `coord_source="igc_median"`; a manually-pinned site never changes regardless
of how many tracks accumulate; detaching a track that was one of the 3 drops the site back below
threshold and clears the auto-set coordinates.

- [x] T021 [US4] Create `src/flightlog/core/site_backfill.py` — insert `site_observations` on a
      successful upload, recompute the median at the ≥3 threshold, skip entirely when
      `coord_source == "manual"`
- [x] T022 [US4] Wire `site_backfill` into T009's upload path and T010's detach path — a replace or
      detach must remove the track's old observations before any recompute (FR-004/FR-012)
- [x] T023 [US4] [P] `tests/backend/test_site_backfill.py` — median from 3 tracks, manual pin never
      overwritten, detach-below-threshold clears the auto-set coordinate. 3/3 passing

## Phase 6 — Bulk upload with automatic matching and manual resolution [US3]

**Goal**: a pilot can upload many IGC files at once; unambiguous matches attach automatically, everything
else is queued for manual resolution, never guessed.
**Independent test criteria**: bulk-upload the T002 same-day-two-flights pair plus one clearly
unambiguous fixture; the unambiguous one auto-attaches, the ambiguous pair both land in
`igc_pending_uploads`; resolving one attaches it and removes it from the pending list.

- [x] T024 [US3] Implement the bulk-match algorithm — in `api/routers/igc.py` (`_find_bulk_match`)
      rather than `core/igc.py`: date + duration scoring, auto-attach only when `|Δ| ≤ 3 min` **and**
      runner-up `> 10 min` away, per `architecture.md`. Reads the date from the already-fully-parsed
      `AnalysisResult` rather than architecture.md's original lightweight header-only pre-scan — see
      `research.md`
- [x] T025 [US3] Add `POST /api/igc/bulk` to `igc.py` — per-file outcome (`auto_attached` /
      `needs_resolution` / `rejected`), writing unresolved files to `igc_pending_uploads`
- [x] T026 [US3] Add `GET /api/igc/pending`, `POST /api/igc/pending/{id}/resolve`,
      `DELETE /api/igc/pending/{id}` to `igc.py`
- [x] T027 [US3] [P] `tests/backend/test_igc_bulk.py` — auto-match, ambiguous same-day pair -> pending,
      resolve, dismiss, repeat-upload-of-a-still-pending-file recognized not duplicated. 3/3 passing
- [x] T028 [US3] Create `static/igc.html` / `static/igc.js` — multi-file upload, per-file outcome list,
      resolve/dismiss actions for pending rows. Resolve dropdown is restricted to the bulk-match
      algorithm's own candidate list rather than the full flights list — verified end-to-end against a
      live dev boot: auto-match, needs-resolution with a real candidate, resolve, dismiss. Caught and
      fixed a real bug this way — dismissing a pending row didn't clear its dedup slot, so re-uploading
      that exact file was silently swallowed (`UniqueConstraint("owner_id", "sha256")` blocked a second
      row; the lookup didn't check `resolved_at`); fixed in `igc.py`, covered by a new regression test
- [x] T029 [US3] Add `GET /igc` route to `src/flightlog/api/routers/pages.py`; nav entry ("Tracks") in
      `static/bootstrap.js`
- [x] T030 [US3] [P] Add `igc.*` and `nav.tracks` i18n keys to `en.json`

## Phase 7 — Administrator re-analysis [US5]

**Goal**: an administrator can re-run analysis on already-uploaded tracks without re-upload.
**Independent test criteria**: bump the code's `ANALYZER_VERSION` constant in a test, call the endpoint
as an admin account, confirm stale tracks are reprocessed and their `analyzer_version` updated; confirm
403 for a non-admin pilot account.

- [x] T031 [US5] Add `POST /api/admin/reanalyze` to `igc.py`, gated by the existing `require_admin`
      dependency (its first use anywhere in the app)
- [x] T032 [US5] [P] `tests/backend/test_igc_reanalyze.py` — 403 for a pilot account, stale-track
      reprocessing bumps `analyzer_version`. 2/2 passing

## Final Phase — Polish

- [~] T033 Live-boot verification pass per `plan.md`'s Phase 8 checklist — **done via `curl` against
      every endpoint** (single upload with figures cross-checked by hand against the fixture, replace,
      detach, bulk auto-match, bulk ambiguous → pending → resolve, dismiss → re-upload). **Not done:
      actual browser rendering** — no browser tool was connected this session either (still
      [[env-no-browser-extension]]); the map, the barogram's per-segment line coloring, the drawer/file-
      input interactions, and keyboard navigation are all unconfirmed. This is the same gap
      `specs/002-flight-log-ui`'s T047 was left open for, for the same reason — first thing to do the
      moment a browser is available
- [x] T034 `ruff check` / `ruff format --check` / full `pytest` clean (143/143); `pyproject.toml` bumped
      0.4.0 → 0.5.0 (static assets and backend both changed — the version is the cache key)
- [ ] T035 `sync.md` — update `architecture.md` (IGC analysis section, SQLite Tables list, API Contracts
      table), `features.md` (mark v0.5 shipped), and `RESUME.md` with what actually shipped, including
      resolving `research.md`'s two open items with what T005 actually found
