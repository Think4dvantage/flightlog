# Feature: Self-Service Spreadsheet Import

## Overview
Today, importing flight history into Flightlog requires a developer to run a one-shot CLI script
against a specific, hand-mapped Excel file — only the maintaining pilot's own workbook has ever
been imported this way. New pilots have no way to bring their existing flight history (kept in
their own spreadsheet, in whatever column layout they happen to use) into the app themselves.
This feature lets any pilot upload their own spreadsheet, tell the app which of their columns
correspond to which Flightlog fields, preview the result, and import it into their own account —
no developer involvement.

## User Stories

### P1 — Upload and map
As a pilot with an existing spreadsheet logbook, I want to upload it and tell the app which
column is which, so that I don't have to manually re-enter every past flight by hand.

**Acceptance Criteria**:
- I can upload a spreadsheet file (Excel or CSV) from a page in the app.
- The app shows me the columns it found (using my sheet's header row) and lets me choose, for
  each Flightlog field I care about, which of my columns supplies it.
- I'm not required to map every possible field — only enough to create a valid flight (date,
  launch site).

### P1 — Preview before committing
As a pilot, I want to see what will actually be created before anything is saved, so that a
mistake in my mapping doesn't leave me with hundreds of wrong flights to clean up.

**Acceptance Criteria**:
- Before import, I see a preview of the parsed rows (or a representative sample) and a summary:
  how many flights will be created, how many new sites/gliders/harnesses/categories will be
  created as a side effect, and how many rows can't be parsed and why.
- Rows that can't be parsed (missing required data, unreadable date, etc.) are listed
  individually, not silently dropped.
- I can go back and change my column mapping before committing.

### P2 — Reuse my existing reference data
As a pilot who already has some sites/gliders/categories set up (or who ran an earlier import), I
want values that already match my existing data to reuse it, and only genuinely new values to
create new rows, so that I don't end up with duplicate sites named slightly differently for no
reason.

**Acceptance Criteria**:
- A mapped value that exactly matches (case-sensitive, exact string) an existing site/glider/
  harness/category of mine is reused, not duplicated.
- A mapped value with no exact match becomes a new row of that type, owned by me.

### P2 — Safe re-run
As a pilot who hit an error partway or wants to double-check, I want to re-upload the same file
without ending up with duplicate flights, so that retrying isn't scary.

**Acceptance Criteria**:
- Re-uploading and re-importing the exact same file with the exact same mapping does not create
  duplicate flights for rows already successfully imported.

### P3 — Undo a bad import
As a pilot who mapped something wrong and only noticed after committing, I want an easy way to
remove everything a specific import run created, so that fixing a mistake doesn't mean manually
deleting flights one at a time.

**Acceptance Criteria**:
- Each import run is identifiable, and I can request removal of everything it created (only if
  untouched since).

## Functional Requirements
- FR-001: A pilot can upload a spreadsheet file (Excel or CSV) from within the app, scoped to
  their own account.
- FR-002: The app reads the header row of the uploaded file and presents the discovered columns
  for mapping.
- FR-003: The pilot maps each column they want used to a Flightlog field; unmapped columns are
  ignored.
- FR-004: At minimum, flight date and launch site must be mapped before an import can proceed;
  every other field is optional.
- FR-005: The app parses every row against the current mapping and classifies each as importable
  or not, with a specific reason for any row that isn't.
- FR-006: The pilot sees a preview — counts of flights/new reference rows to be created, and the
  list of any unparseable rows — before anything is written.
- FR-007: Only on the pilot's explicit confirmation are rows actually written.
- FR-008: A mapped value for site/glider/harness/category that exactly matches one the pilot
  already owns is reused; otherwise a new one is created, owned by the pilot.
- FR-009: Every flight created by an import is attributable to the specific import run that
  created it.
- FR-010: Re-running an import of the same file with the same mapping does not create duplicate
  flights for rows already imported successfully.
- FR-011: A pilot can undo an import run, removing every flight/reference row it created, as long
  as none of them have been edited since.
- FR-012: Rows without a mapped value for a required field are reported as unparseable, never
  silently skipped or guessed.

## Non-Functional Requirements
- NFR-001: Upload is size-limited to prevent abuse, consistent with this app's existing per-file
  limits elsewhere.

## Success Criteria
- A pilot with no prior technical involvement from the app's maintainer can go from "spreadsheet
  on my computer" to "flights visible in my flight log" entirely through the UI.
- A mis-mapped import can be fully undone without contacting support or hand-editing the
  database.
- Re-uploading a file a pilot already successfully imported does not corrupt their flight log
  with duplicates.

## Key Entities
| Entity | Key Attributes | Notes |
|---|---|---|
| Import run | uploader, source filename, column mapping used, created-at, row outcome counts | Groups everything one upload produced, for preview and undo |
| Imported flight | (existing Flight entity) | Tagged with the import run that created it |
| Imported reference row (site/glider/harness/category) | (existing entities) | Tagged with the import run that created it, only if the import run itself created it |

## Out of Scope
- Parsing any specific third-party app's export format (XCTrack, FlySkyHy, SkyViz, etc.) — this
  feature is a generic spreadsheet-with-column-mapping tool, not a format-specific parser.
  Dedicated format support remains a separate, later backlog item if ever pursued.
- Cross-source duplicate detection — matching an imported row against a flight the pilot already
  entered by hand is not attempted; only literal re-import of the same file/row is protected
  against.
- Importing anything other than flights and the reference data a flight directly needs (no
  hikes, groundhandling, tandem flights, or goals via this flow).
- IGC track attachment as part of import — a spreadsheet import never attaches a track; tracks
  are attached per-flight afterward, same as today.

## Assumptions
- Available to any authenticated pilot at any time, not gated to new/empty accounts only — an
  existing pilot can also use it to bulk-add more historical flights.
- If category isn't mapped, all imported flights are placed in a single auto-created category
  the app clearly labels as import-created, so the required field is always satisfied without
  guessing which of the pilot's real categories was meant.
- Import is best-effort per row, not all-or-nothing: importable rows are written, unparseable
  ones are reported and skipped — matching how the existing developer-run importer already
  reports (never silently drops, never guesses) rather than blocking an entire 500-row file over
  a handful of bad rows.
- Both Excel (.xlsx) and CSV are accepted — confirmed with the pilot directly (2026-08-19).

## Dependencies
- None blocking — unlike the XContest score-import backlog item, this doesn't depend on
  obtaining a third-party export sample, since the format is whatever the pilot's own
  spreadsheet already is.

## Edge Cases
- A spreadsheet with no header row, or headers the app can't reasonably present as column
  choices.
- A date column in a format the app can't parse for some rows but can for others.
- A mapped "site" value that's blank for some rows (should that row be dropped, or is landing
  site legitimately optional while launch site is not).
- A pilot mapping the same column to two different fields.
- An import run undo requested after some of its flights were already edited or had a track
  attached.
- A file with thousands of rows — where the preview step needs to summarize rather than list
  every row.
- A CSV file with an ambiguous delimiter or encoding (e.g. semicolon-delimited, non-UTF-8).
