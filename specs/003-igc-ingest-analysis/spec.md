# Feature: IGC Ingest & Analysis

## Overview

Lets a pilot upload a flight's GPS track (an IGC file) and see it turned into real figures — thermal
count, best sustained climb, glide ratio, altitude gain, duration, distance — instead of the hand-typed
estimates the Excel-derived flight log has today. Covers a single flight's own upload, a bulk path for
backfilling years of old track files against the already-imported flight log, a map + altitude chart per
tracked flight, and using enough tracks at a site to fill in that site's map location automatically.

## Clarifications

### Session 2026-08-15
- Q: If a flight already has a track attached and the pilot uploads a different file for that same
  flight, what happens? → A: The new file's analysis replaces the old track and its segments
  automatically — no explicit detach step required first.

## User Stories

### P1 — Must Have

**As a pilot, I want to upload a flight's IGC file from that flight's own record so it shows real
analysis instead of just what I typed in by hand.**

Acceptance Criteria:
- Uploading from a flight's own edit/detail view attaches the track to exactly that flight — no matching
  or ambiguity, since the pilot picked the flight.
- After upload, the flight shows: duration, distance over ground, altitude gain, thermal count, best
  sustained climb rate, and glide ratio.
- Uploading the exact same file again for the same flight changes nothing and does not create a
  duplicate.
- Uploading a different file for a flight that already has a track replaces the existing track and its
  segments (per Clarifications).
- An invalid or unreadable file is rejected with a clear, specific reason, not silently ignored or
  accepted with blank figures.

**As a pilot, I want to see my track on a map and my altitude over time on a chart, with thermal and
glide parts visually distinguished, so I can understand how a flight actually went.**

Acceptance Criteria:
- The track is drawn on a map, reachable from the flight's own detail page.
- An altitude-over-time chart spans the whole flight.
- Thermal segments and glide segments are visually distinguishable from each other and from the rest of
  the track on the chart.

### P2 — Should Have

**As a pilot, I want to upload many IGC files at once so I can back-fill years of old tracks without
attaching 600 files one at a time.**

Acceptance Criteria:
- Multiple files can be uploaded in one action.
- A file that unambiguously matches exactly one existing flight (by date, with a closely matching
  duration) is attached automatically.
- Anything ambiguous — most commonly a day with more than one logged flight — is never guessed; it is
  listed for the pilot to resolve by hand.
- For every uploaded file, the pilot can see its outcome (auto-attached / needs manual resolution /
  rejected) and, for a rejection, why.
- The pilot can resolve a listed ambiguous file by picking the correct flight themselves.

**As a pilot, I want a site's map location to fill itself in automatically once I've flown there enough
times with a GPS track, so I don't have to manually place every pin.**

Acceptance Criteria:
- Once enough tracks exist for a site, its coordinates are set automatically from that GPS data.
- A site the pilot has manually pinned (via the existing `/sites` map) is never overwritten by this
  automatic process.
- Whether a site's current location came from a manual pin or from track data is visible to the pilot
  (the app already distinguishes coordinate sources today).

### P3 — Nice to Have

**As the administrator, I want to re-run analysis on already-uploaded tracks without re-uploading them,
so that improving the analysis doesn't mean redoing the pilot's manual work.**

Acceptance Criteria:
- A re-analysis action re-processes existing tracks from their already-stored files.
- Re-analysis updates the computed figures and segments without the pilot re-attaching anything.
- Only an administrator can trigger this — not every pilot account.

## Functional Requirements

- FR-001: The system MUST let the pilot upload a single IGC file from a flight's own edit/detail view
  and attach it to exactly that flight.
- FR-002: The system MUST reject an invalid or unparseable IGC file with a clear, specific reason.
- FR-003: The system MUST NOT create a duplicate track when the identical file is uploaded again for a
  flight that already has that exact track attached.
- FR-004: Uploading a different file for a flight that already has a track MUST replace the existing
  track and its segments.
- FR-005: For every track, the system MUST compute and display duration, distance over ground, altitude
  gain, thermal count, best sustained climb rate, and glide ratio.
- FR-006: The system MUST render the track on a map, reachable from the flight's detail view.
- FR-007: The system MUST render an altitude-over-time chart for the track, visually distinguishing
  thermal and glide segments from each other and from the rest of the track.
- FR-008: The system MUST let the pilot upload multiple IGC files in a single action.
- FR-009: For a bulk upload, the system MUST automatically attach a file to a flight only when the match
  is unambiguous; every other file MUST be presented for manual resolution, never guessed onto a flight.
- FR-010: The system MUST show, for every bulk-uploaded file, its outcome (auto-attached / needs manual
  resolution / rejected) and the reason for that outcome.
- FR-011: The system MUST let the pilot manually resolve an ambiguous bulk-upload file by selecting the
  correct flight themselves.
- FR-012: The system MUST let the pilot detach a track from a flight (to correct a wrong manual
  resolution, without needing to delete the flight itself).
- FR-013: Once a site has enough associated tracks, the system MUST automatically set that site's
  coordinates from that track data.
- FR-014: Automatic coordinate placement MUST NEVER overwrite a site's manually-set coordinates.
- FR-015: The system MUST let an administrator trigger re-analysis of already-uploaded tracks without
  requiring re-upload.
- FR-016: Re-analysis MUST be restricted to administrator accounts.
- FR-017: All user-visible chrome (labels, buttons, navigation, validation and rejection messages) MUST
  go through the existing translation mechanism.
- FR-018: Every view introduced by this feature MUST use the existing dark theme and navigation shell
  consistently with the rest of the application.

## Non-Functional Requirements

- NFR-001: A single-file upload's analysis must complete quickly enough that the pilot does not need to
  leave the upload flow to wait for it (single-digit seconds for a typical multi-hour flight track).
- NFR-002: Every view introduced by this feature must be usable by keyboard alone, consistent with the
  rest of the application's existing keyboard-navigation standard.
- NFR-003: Detaching a track, and any bulk action affecting more than one flight, must require an
  explicit confirmation step — none may be a single accidental click.

## Success Criteria

- A pilot can upload a single IGC file and see full thermal/glide/duration/altitude-gain analysis within
  seconds of upload.
- A pilot can bulk-upload a folder of historical track files and have the clear majority correctly and
  automatically attached, with the rest flagged for a few minutes of manual review rather than hours.
- Re-uploading the same file twice never produces a duplicate or an unexpected change.
- After enough flights are tracked at a site, that site shows a real map location without any manual
  pin-drop from the pilot.
- Looking at any tracked flight's chart, a pilot can immediately tell which parts were climbing and
  which were gliding, without cross-referencing raw data.

## Key Entities

| Entity | Key Attributes | Notes |
|--------|---------------|-------|
| IGC Track | flight it belongs to, original filename, duration, distance, altitude gain, thermal count, best/peak climb rate, glide ratio, altitude source (barometric or GPS) | One per flight; the uploaded file is stored, not just the derived figures — replaced wholesale on re-upload (FR-004) |
| Track Segment | track it belongs to, kind (thermal / glide / takeoff / landing / marker), when it happened relative to takeoff | Multiple per track; drives the chart's thermal/glide highlighting (FR-007) |
| Site Observation | site it belongs to, a GPS fix location, which track it came from | Feeds automatic site-coordinate refinement (FR-013); not directly pilot-visible as its own view |

## Out of Scope

- XC/competition scoring — already decided against project-wide (official scores are imported
  separately; see `features.md`'s Backlog).
- Terrain-relative (AGL) altitude and any 3D visualization.
- VidFactory video-highlight integration and anything about pushing data to external services — this
  feature only stores and displays per-flight track data; the public API milestone consumes it later.
- Statistics or rollups drawn from IGC data (cumulative climb totals, personal bests, etc.) — this
  feature only computes and shows per-flight figures.
- Any in-app UI for tuning how analysis is computed (thermal/glide detection sensitivity) — that remains
  a configuration-file setting for the operator, not something a pilot edits.
- Live tracking (never in scope for this project).

## Assumptions

- There is exactly one pilot account in the system today (matches prior specs' stated assumption); the
  administrator-only re-analysis action still needs role gating even though only one account exists,
  since the app's existing role model already distinguishes pilot from admin accounts.
- The pilot holds years of historical IGC files never previously matched against the Excel-derived
  flight log — the bulk-upload path exists specifically to back-fill those, not only to handle new
  flights going forward.
- IGC files come from a mix of GPS devices and phone apps of varying quality, some without barometric
  altitude readings — analysis must degrade gracefully (falling back to GPS altitude) rather than fail
  outright when a reading type is missing.
- A single calendar day can have more than one logged flight (already true of the historical data), so
  date alone is never a sufficient signal for automatic bulk-match attachment.

## Dependencies

- Requires the flight, site, and region data already in place from v0.2/v0.3 — this feature attaches to
  those existing records; it does not restructure them.
- Requires a capability to parse and analyze IGC flight-track files; which specific library provides
  that is a planning-phase decision, not a product decision.
- Requires the existing authentication/role system to gate the administrator-only re-analysis action.

## Edge Cases

- A day with two or more logged flights: bulk match must never guess between them — both go to manual
  resolution rather than picking the closer-duration candidate silently.
- A GPS device with no barometric sensor: the track must still analyze using GPS altitude, with that
  fallback recorded rather than hidden.
- A corrupt or truncated IGC file: rejected with a specific reason (e.g. "unreadable" vs "too short to
  be a flight"), not a generic failure message.
- Circling flight that is actually a descending spiral or a wingover, not a genuine thermal: must not be
  counted as a thermal or inflate the climb-rate figures.
- A flight that already has a track attached receives another upload: replaces the existing track and
  segments in full (FR-004) — no partial merge of old and new segments.
- Re-analysis changes a track's computed figures (e.g. after a tuning change): the pilot-facing figures
  simply reflect the latest analysis; no history of previous figures is kept or shown.
