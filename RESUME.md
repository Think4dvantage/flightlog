# Resume Notes — 2026-08-16

## In Progress

**Nothing in progress — `v0.8.0` is implemented, tested, live-verified, doc-drift-cleaned,
committed, tagged, and pushed this session.** All 21 tasks in
`specs/006-public-api-vidfactory/tasks.md` are done. This picks up straight from the prior
session's `v0.7.5` ship (see git log / the section below this one for that history).

### What shipped in `v0.8.0`

Triggered by the pilot asking whether the v0.5 IGC analysis (climb/sink timestamps,
launch/landing) could be exposed via API for a highlight-video tool. Investigation found
`architecture.md` had already committed to exactly this shape for `igc_segments` since v0.5
("the VidFactory contract") — it just wasn't exposed under a scoped, machine-authenticated
surface yet, which is what v0.8 already existed to build.

1. **`api_keys` / `flight_links` tables**, `services/apikeys.py` (mint/hash/verify,
   SHA-256 not bcrypt — 256 bits of CSPRNG doesn't need a slow hash), `ApiPrincipal` /
   `get_api_principal` / `require_scope(...)` in `dependencies.py` — genuinely new code,
   confirmed via `research.md` that the docs describing this shape predated any real
   implementation.
2. **`/api/keys`** (JWT-auth) — create/list/revoke/delete, plaintext shown exactly once at
   creation. `/api-keys` page with a deliberately non-accidentally-dismissible one-time
   reveal state.
3. **`/api/integration/v1`** (API-key-auth via `X-API-Key`) — `GET /flights/{id}` (resolved
   names + `igc_summary`, a deliberate addition beyond the original spec's metadata list),
   `GET /flights/{id}/segments` (verbatim `igc_segments`), `PUT .../links/{kind}/{external_id}`
   (idempotent push-back).
4. **`FlightOut.links`** — the pilot's own flight views now show any VidFactory-pushed link
   automatically (FR-009), no separate endpoint needed.
5. **21 new tests**, 211/211 passing project-wide, `ruff` clean.
6. **Live-boot verified via `curl`** against the local dev server exactly as an external
   tool would: minted a key, read real flight metadata (names resolved correctly against a
   real glider/site), pushed a link then re-pushed it (confirmed idempotent replace),
   confirmed the pilot's own flight view picked it up with zero action, revoked the key and
   confirmed the very next call was rejected, deleted the revoked key. Test data cleaned up
   after.
7. **Docs synced**: `architecture.md` (SQLite Tables + API Contracts), `01-project-
   overview.md`'s Repository Layout / Data Flow (added `api_keys.py` to the router list,
   fixed the flight-link push-back path to the real `/api/integration/v1/...` prefix),
   `features.md` (full v0.8 write-up), `specs/006-public-api-vidfactory/tasks.md` (all 21
   boxes checked), `pyproject.toml` bumped `0.7.5` → `0.8.0` (`poetry install` re-run so
   `APP_VERSION` isn't stale).
8. **A genuine, pre-existing doc-drift bug found and fixed, not just flagged**: the pilot
   asked for the drift to be fixed before shipping, no matter whose session introduced it.
   `media_links`/`tracker_links`/site `webcam_url`/`rules_url` had been cited as existing
   tables/columns and as URL-validation precedent in `architecture.md`, `04-constraints.md`,
   and `03-frontend-conventions.md` since this project's first revision — none of them ever
   existed in `database/models.py`, and no code validated a URL before this session's real
   `flight_links.url`. See this file's Context section below for exactly what changed.

**Not touched**: `02-backend-conventions.md` needed no edit — the `ApiPrincipal`/
`get_api_principal`/`require_scope` shape it already documented (aspirationally, per
`research.md`) turned out to match exactly what got built, so it's simply accurate now.

### The Chrome extension was not connected this session

See `env-no-browser-extension` memory — tried `tabs_context_mcp` first per that memory's own
guidance, got the "not connected" error. Fell back to: `curl` against the live dev server for
every backend behavior (see above), plus for the two new/changed frontend files
(`api-keys.html`/`.js`, `flight-detail.html`/`.js`) — cross-checked every DOM id referenced in
JS against the HTML, every `data-i18n` key against `en.json`, and ran `node --check` on the
JS. **This is not the same as an actual rendered screenshot** — the `/api-keys` page and the
flight-detail "Linked resources" row have not been visually confirmed in a real browser.

## Next Step

1. **If a browser is available next session, actually look at `/api-keys` and the
   flight-detail "Linked resources" row** — the create-drawer, scope checkboxes, one-time
   reveal panel, and revoke/delete confirm drawer have only been checked structurally (ids
   match, JS parses, i18n keys resolve), never visually.
2. **Confirm with the pilot whether re-logging into the SSO fixed "Add goal"** on
   `fl.sdh.lol` (carried over from last session — still open, see Open Questions).
3. **v0.9 (sharing & public readiness)** is fully planned (`specs/007-sharing-public-
   readiness/`) and ready next.
4. **XContest score import** remains a backlog item.
5. **Decide on `specs/002-flight-log-ui`'s Phases 10-11** (CSV export, remember-last-filters)
   — still open, not tied to any particular tag.
6. **`v0.8.0` itself is not yet deployed** — tagging/pushing to `main` triggers
   `docker-publish.yml` the same as every prior tag, but confirming it's actually live at
   `fl.sdh.lol` (and that the pilot can mint a real key against production) is still worth a
   follow-up check, same pattern as every prior tagged release in this file's history.

## Open Questions

- Whether the OIDC/Traefik layer in front of `fl.sdh.lol` needs an actual config change, or
  whether re-authenticating to the SSO resolves the "Add goal" write-failure symptom on its
  own — pilot was self-testing as of last session, no update yet.
- Whether VidFactory's own team is ready to consume `/api/integration/v1` yet, or whether
  this ships and sits unused for a while — doesn't block shipping either way
  (`spec.md`'s Assumptions: this service is authoritative, not blocked on VidFactory).

## Context

- **`FlightOut.links` (pilot-facing) and `FlightMetadataOut`/`SegmentOut` (`/api/integration/v1`,
  frozen) deliberately use separate Pydantic types**, even though `flight_links` is one table.
  A first pass had `models/flights.py` importing `FlightLinkOut` straight from
  `models/integration.py` — caught before commit (advisor review): that would mean a change
  made for an integration-contract reason silently changes the pilot-facing `/api/flights`
  shape, the exact thing "frozen, versioned separately from the UI's models" is supposed to
  prevent. Now `models/flights.py` defines its own minimal `FlightLinkOut` (`kind`,
  `external_id`, `url`, `label` — no `created_at`/`updated_at`, which nothing in the UI reads).
- **`media_links`/`tracker_links`/site `webcam_url`/`rules_url` doc drift is now fixed**, not just
  flagged. These were cited by `architecture.md`, `04-constraints.md`, and
  `03-frontend-conventions.md` as existing tables/columns and as URL-validation precedent since this
  project's first revision — none of them ever existed in `database/models.py`, and no code validated
  a URL before this session's real `flight_links.url`. `architecture.md`'s `media_links` row now reads
  "not built — backlog" and points at `features.md`'s real backlog entry; `tracker_links` and the two
  site columns moved to "Tables that do NOT exist," explicitly marked as forgotten blueprint leftovers
  (not a deliberate design rejection like `igc_fixes`/`outings`/`lookups`/`stats_cache`); both
  instruction files now point to `flight_links.url`'s `field_validator` as the one real example to
  follow. `specs/004-secondary-sheets-xcontest/`'s two mentions were left as-is — that folder is a
  frozen planning-session record, same convention this project already applies elsewhere (see e.g.
  `features.md`'s v0.7 entry, "left as a visible historical trace rather than silently rewritten").
- **`specs/006-public-api-vidfactory/`** now has all 21 tasks checked — the full spec/plan/
  data-model/contracts/research/tasks set matches what's actually implemented.
- **The DELETE-requires-revoke-first precondition on `/api/keys/{id}`** (`409` if not yet
  revoked) was a judgment call, not explicit in `spec.md` — `contracts/endpoints.md`'s
  wording ("Hard delete... once already revoked") read as a precondition, unlike `gliders.py`'s
  independent retire/delete split it's compared against. Worth confirming with the pilot if
  it ever feels like unnecessary friction.
- **`igc_summary` on `FlightMetadataOut`** (the `igc_tracks` aggregate — thermal count, best/
  peak climb, glide ratio, alt gain) was not in `contracts/endpoints.md`'s original field
  list for that endpoint — added after confirming with the pilot (asked via `AskUserQuestion`
  before building) that a highlight video wants those numbers as captions, not just the raw
  segment timeline.
- **The dev server needs a restart after every backend edit** (no `--reload`). See
  [[flightlog-dev-server-workflow]].
- **The Windows-only WAL gotcha**: `data/flightlog.db`'s main file is often stale on its own
  — real, current data lives in the accompanying `.db-wal`/`.db-shm` sidecar files until
  SQLite checkpoints them. Copy all three together, or better, just point directly at the
  real path.

This file is a pointer, not a duplicate — `.ai/context/features.md`, `architecture.md`, and
each feature's own `specs/` folder have the detail.
