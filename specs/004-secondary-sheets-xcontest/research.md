# Research: Secondary Sheets & XContest Import

Findings from inspecting the real `olddata/Flugbuch.xlsx` directly (via `openpyxl`, `data_only=True`),
the same method `specs/001-core-data-import/research.md` used for `Flugbuch` itself. The four sheets
this feature imports were named but never actually read in that prior research — confirmed here for the
first time.

## Decision: real sheet structures, confirmed by direct read

- **`Fitnessprogramm`** (85 data rows): `Datum, Start, Ziel, steigung, gefälle, Distanz km, Zeit, Route,
  Airtime, Landeplatz`. `Airtime`/`Landeplatz` are populated on some rows and `None` on others — this is
  the real, observed signal for "this hike became a flight" vs. "this was a pure hike," confirming
  `architecture.md`'s `hikes.flight_id` nullable design without needing to guess at it.
- **`Groundhandling`** (9 data rows): `Datum, Ort, Dauer (min), Kommentar` — matches
  `architecture.md`'s already-named columns (`date`, `place`, `duration_min`, `comment`) exactly.
- **`Tandemflüge`** (17 data rows): `Datum, Start, Landung, Pilot, Kommentar, kosten`. `Pilot` holds
  either a person's name or a company name (e.g. `"AlpineAir"`) — confirms this must stay a free-text
  field, never a FK into `buddies` (a tandem operator is not necessarily a personal contact). `kosten`
  is `0` on several real rows (flight-school tandems flown for free) — a real, meaningful value, not an
  absence.
- **`Ziele`** (11 data rows): `Titel, Wetterlage, Level, Kategorie, Beschreibung, Links, Saison, Status`
  — only 8 real columns, though `openpyxl` reports ~505 columns wide per row; every column past the 8th
  is `None` on every row, a leftover Excel formatting artifact (likely from conditional formatting or a
  copy-paste that extended past used cells), not real data. **Decision**: the importer must read only
  the first 8 columns by name/position, not iterate the full reported width. Observed `Status` values:
  `open`, `done`. Observed `Kategorie` values include `H&F`, `Abgleiter`, `Teacher`. Observed `Level`
  values: `leicht`, `mittel`, `schwer`. `Wetterlage` is free text (`"N"`, `"W, SW"`, `"any"`).

## Decision: idempotency follows the existing `import_key` pattern exactly

- **Decision**: Each of the three read-only-import types (hikes, ground-handling, tandem flights) gets
  its own `import_key` column, `UniqueConstraint("owner_id", "import_key")`, formatted
  `"<sheet>:<row>"` (e.g. `"fitnessprogramm:5"`) — identical in shape to `flights.import_key`
  (`specs/001-core-data-import/data-model.md`). Goals get the same treatment for their one-time import,
  even though they become editable afterward — the `import_key` only identifies *which spreadsheet row
  produced this goal originally*; it plays no role once the pilot starts editing it.
- **Rationale**: This is the exact mechanism that already makes the primary flight import safely
  re-runnable, and there is no reason for a smaller, later import to invent a different one. Consistency
  here means one shared mental model (and possibly one shared helper) instead of three subtly different
  idempotency schemes.
- **Alternatives considered**: A single shared "historical import log" table keyed by sheet+row across
  all four types. Rejected as premature abstraction for four small, structurally different imports (8
  rows each on average) — `import_key` living directly on each type's own table, exactly like `flights`
  already does, is simpler and has direct precedent.

## Decision: hike-to-flight linking uses the same ambiguity rule as IGC bulk-match, not a new algorithm

- **Decision**: A hike's `Datum` is compared against `flights.flight_date` for flights whose category
  has `is_hike_fly = True`. Exactly one same-date candidate → link `hikes.flight_id`. Zero or multiple
  candidates → import the hike with `flight_id = NULL` and report it in an import-findings-style summary
  (following `/import`'s existing precedent from `specs/002-flight-log-ui`), never guessed.
- **Rationale**: This is architecturally identical to `specs/003-igc-ingest-analysis`'s bulk IGC match
  (date-based, ambiguity reported not resolved) — reusing the *pattern*, not the code, since the
  matching signal here (date only, no duration to disambiguate) is simpler and the volume (85 rows) is
  small enough that a same-day ambiguity is rare and cheap to leave for manual review rather than build
  a second disambiguation signal for.
- **Alternatives considered**: Also scoring by launch-site name similarity (`Fitnessprogramm.Ziel` vs.
  the flight's landing site, since a hike's destination often *is* the flight's landing point).
  Rejected as unnecessary complexity for 85 rows where date alone already resolves the overwhelming
  majority unambiguously — worth revisiting only if the real import run shows many same-day
  `Hike&Fly` collisions, which is a Phase 1 implementation-time check, not a planning-time guess.

## Open: XContest "My Flights" export's exact JSON schema is unverified — resolve against a real sample before implementing the parser

- **What's confirmed**: `architecture.md` already commits to exactly three resulting columns on
  `flights` — `xc_official_score`, `xc_official_type`, `xc_official_url` — and this feature's job is to
  populate them from an import, alongside the hand-entered FAI distance that already exists. XContest
  does offer a "My Flights" JSON export reachable from a logged-in user's own flights page (confirmed by
  general web search this session), so the mechanism exists.
- **A real, working XContest integration was found and inspected** — the open-source paragliding
  logbook `Iv/FlyHigh` (`src/upload/XContestUploader.cpp`/`.h`, plus
  `doc/xcontest.org/API_gate_flight_documentation.pdf` and `xcontest_api_implementation_howto.pdf`) —
  but it implements the **opposite direction from what this feature needs**: XContest's "Gate flight"
  API, which *submits* a local IGC file to XContest to be scored (a `ticket` → key/hash-signed `gate`
  request → `authTicket` session flow, posting `flight[tracklog]` / `flight[comment]` /
  `flight[glider_name]` as multipart form fields, keyed against a fixed public API key). This confirms
  XContest runs a real, documented, key-authenticated API generally — useful context — but it is a
  **flight-upload/scoring-request API, not a flight-list/export-retrieval API**. It does not show what a
  "My Flights" JSON export (reading back flights *already* scored on the pilot's own account) looks
  like, because `FlyHigh` never does that — it only ever pushes flights outward.
- **Still not confirmed**: the literal JSON key names, nesting, date format, and exactly which flight-
  type/score fields appear in a "My Flights" export (XContest scores under several rule sets — its own
  ranking vs. FAI triangle vs. free distance — and it's not yet known which of those the export
  surfaces, or under what key). XContest.org's own pages require a logged-in session to browse (a plain
  fetch returned 401), and neither `FlyHigh` nor SkyViz's integration guide (checked this session)
  documents this specific schema.
- **Resolve by**: obtaining one real sample "My Flights" export (the pilot's own XContest account, once
  this feature starts implementation) and reading its actual structure directly — the same resolution
  method `specs/003-igc-ingest-analysis/research.md` used for `libigc`'s two unknowns (inspect the real
  artifact, don't guess from docs or from a same-vendor API that turned out to solve a different
  problem). This is a Phase 1 (foundation) implementation task, not a blocker for this plan: the spec and
  data model are already written at the field-*meaning* level (score, type, URL), not the JSON's literal
  shape, so whichever way the schema resolves is a contained change to one parser module, not a
  redesign.

## Decision: goals are the one editable entity this feature introduces — reuse the existing CRUD-router pattern, not the frozen-snapshot `/import` pattern

- **Decision**: `goals` gets a normal owner-scoped CRUD router (`GET`/`POST`/`GET/{id}`/`PUT`/`DELETE`),
  following `buddies.py`'s or `sites.py`'s existing shape exactly — not `import_report.py`'s frozen-
  constant, read-only shape.
- **Rationale**: `spec.md`'s FR-006 explicitly wants ongoing create/edit/delete/mark-done after import,
  unlike the `/import` page's historical-snapshot findings (which are deliberately frozen,
  `specs/002-flight-log-ui/research.md`) or this feature's own hike/ground-handling/tandem-flight import
  (deliberately import-and-view-only per this spec's Out of Scope). Goals are the one type here that
  behaves like every other domain entity already in the app, so it should look like one.
- **Alternatives considered**: None seriously — this follows the codebase's own dominant, well-
  established pattern; `import_report.py`'s frozen shape exists specifically *because* that data must
  never look live, which is the opposite of what FR-006 asks for here.
