# Resume Notes — 2026-08-14

## In Progress

**v0.3's MVP (flight log UI, `specs/002-flight-log-ui/`) is implemented on `main` but not committed,
tagged, or deployed.** Phases 1–8 (T001–T036 of 49) are done: `/flights` (search/filter/sort/paginate +
inline add/edit/delete drawer), `/flights/{id}` detail, `/sites` (Leaflet map, click-to-drop /
drag-to-move pins), `/equipment` (glider/harness CRUD + retire), `/import` (read-only historical import
findings from a frozen, freshly-regenerated dry-run — not hand-transcribed from this file), and
`static/refdata.js` as the shared join cache every page uses. 127 backend tests passing (up from 121:
4 new for `sites.py`'s `coord_source = "manual"` behavior, 2 new for `GET /api/import-report`), `ruff
check` and `ruff format --check` clean. `pyproject.toml` bumped to `0.3.0` (static assets changed — the
version is the cache key).

**Verified live via `curl` against a local dev boot** (`config.yml` already present in the working tree,
pointed at `data/flightlog.db`), with the real 600-flight workbook re-imported into that dev DB
(`--write`, confirmed `Regions written: 0` — further live confirmation the `Därstetten` seed fix from
the last session is correct): every new page route, every new/changed API endpoint, and the full flight
create/edit/delete lifecycle were exercised end-to-end, including a 422 validation response shape-check
against the drawer's field-error rendering.

**Not verified: actual browser rendering.** No browser automation tool was connected this session (the
Claude in Chrome extension wasn't available), so nobody has looked at these pages, clicked the map,
dragged a pin, or tabbed through the drawer. `specs/002-flight-log-ui/tasks.md`'s T047 (manual live-boot
verification pass — golden path, empty states, validation errors, keyboard nav, i18n completeness) is
still open specifically for that reason and should be the first thing done with real browser access.

**Nothing from this session is committed yet.** `git status` will show all the new/changed files.

## Next Step

In order:
1. **Review and commit this session's work.** New: `static/refdata.js`, `flights.html/js`,
   `flight-detail.html/js`, `sites.html/js`, `equipment.html/js`, `import.html/js`,
   `core/import_history.py`, `models/import_report.py`, `api/routers/import_report.py`,
   `test_import_report.py`, 5 vendored Leaflet marker/layer images. Changed: `shared.css`,
   `bootstrap.js`, `index.html`, `i18n/en.json`, `pages.py`, `main.py`, `sites.py` (+its tests),
   `pyproject.toml` (version bump).
2. **Do the T047 visual pass** once a browser is available — this is the one thing `curl` genuinely
   can't confirm (rendering, the map's click/drag, keyboard-only nav, i18n completeness).
3. **Finish the still-open v0.2 prod loose ends** (independent of v0.3, can happen in parallel): the
   orphan `"Dürstetten"` region row still needs checking (0 sites attached) and deleting on the live
   prod DB, and the region-seed fix (`7345d28`/`e4ae0b8`) still needs a redeploy. Both were re-confirmed
   still pending as of this session — nobody has run the `docker exec` commands yet. Consider folding
   this redeploy into whatever ships v0.3, rather than shipping it separately.
4. **Decide on Phases 9–11** (`/contacts`, CSV export, remember-last-filters — all P2/P3) before tagging
   `v0.3.0`: ship the MVP boundary now and treat these as a fast-follow, or include them first. The spec
   treats Phases 3–8 as the complete MVP boundary ("the Excel is never opened again"), so shipping
   without 9–11 is consistent with the plan of record.
5. Tag and deploy once the above is settled.

## Open Questions

- Whether Phases 9–11 ship with v0.3.0 or as a fast-follow v0.3.1 — see step 4 above.
- The three items already in `features.md`'s backlog from v0.2 (unchanged this session): grant the
  deploy `gh` token `read:packages`, re-run the `python:3.14-slim` build gate once `libigc` lands in
  v0.4, and the `bootstrap_admin_email`/`bootstrap_admin_password` `set=%s`-style logging gap.

## Context

- **v0.3's spec/plan/research/data-model/contracts/tasks live in `specs/002-flight-log-ui/`** — this
  directory existed only in the working tree at the start of this session (never committed); it was
  committed early on, before any implementation, so the plan of record is durable regardless of what
  happens to the implementation.
- **The `HISTORICAL_IMPORT_SUMMARY` frozen constant in `core/import_history.py` was generated from a
  fresh dry-run**, not copied from this file or from chat — `data-model.md` and `tasks.md`'s T027 are
  explicit that hand-transcription is exactly how the `Därstetten`/`Dürstetten` bug happened last
  session, so the values were pulled via a throwaway pytest test that ran `run_import(..., write=False)`
  and printed the real `ImportReport` fields, then deleted. A pure dry-run never increments
  `ImportReport.flights_written` (the importer's own `if not write: continue` skips that line), so the
  frozen `flights_written=600` is `rows_read - len(flights_skipped_unresolved)` from that dry-run, not
  the field name it looks like.
- **One real XSS bug caught and fixed before it shipped**: `sites.js`'s Leaflet marker tooltips were
  initially bound with `marker.bindTooltip(site.name)` — a bare string. Leaflet's `bindTooltip(string)`
  sets `innerHTML` internally, and `site.name` is free-text user data (sites can be user-created,
  `sites.allow_user_sites` in `config.yml`). Fixed to build a DOM node with `textContent` first and bind
  that instead, per `03-frontend-conventions.md`'s XSS rule. A second near-miss of the same class was
  caught earlier in `flights.js`'s buddy multi-select, which briefly used an `innerHTML`-based option
  builder for buddy display names before being rewritten to use `document.createElement` +
  `textContent` like every other dropdown on the page.
- **The dev server needs a restart after every backend edit** — it was started once with `uvicorn
  --host 127.0.0.1 --port 8002` (no `--reload`) against the working tree's existing `config.yml` /
  `data/flightlog.db`, and every `pages.py`/`sites.py` change required killing and restarting it before
  the change was live. Two 404s and one silently-stale `coord_source` behavior during this session's own
  smoke testing were both this, not real bugs — worth remembering before assuming a live-boot check that
  fails is a code problem.

This file is a pointer, not a duplicate — `.ai/context/features.md`, `architecture.md` and
`specs/002-flight-log-ui/` have the detail.
