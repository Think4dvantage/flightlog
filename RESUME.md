# Resume Notes — 2026-08-17

## In Progress

Nothing in flight. **`v0.9.4`, `v0.9.5` and `v0.9.6` are all implemented, tested, committed,
tagged and pushed — CI green** (`Backend tests` and `Publish container image` both succeeded on
GitHub Actions for each tag). This picks up straight from the prior session's `v0.9.3` ship.

### What shipped in `v0.9.4`–`v0.9.6`

Three separate pilot-requested features, each its own plan-mode cycle (explore → plan file →
explicit approval → implement), each its own commit + tag — not bundled together like
`v0.9.1`–`v0.9.3` were, since each landed as its own distinct ask across the session rather than
several small tweaks requested at once. Full detail in `.ai/context/features.md`'s own entries;
summary here:

1. **`v0.9.4`** — `/categories` (full create/rename/reorder/archive/delete UI for flight
   categories — the API had been owner-scoped since v0.2, only the page was missing) and
   `/profile` (the account-settings home that never existed: display name, password change, the
   "Public profile" toggle moved off `/api-keys`, which had only ever hosted it as a stand-in).
2. **`v0.9.5`** — two parts. **Part 1**: `/public/flights/{id}` now shows the same track map,
   barogram and IGC-derived figures the pilot's own flight-detail page shows, when a track is
   attached. **Part 2**: public statistics sharing — a new, independent `users.public_stats_enabled`
   flag (separate from `public_profile_enabled`) publishes `/public/stats/{id}`, mirroring the
   pilot's own `/stats` dashboard over their **entire** flight history including buddy names (both
   confirmed explicitly with the pilot via `AskUserQuestion` before building, since the naive
   version would have leaked more than a per-flight `visibility` choice implies). `stats.js`'s
   chart/table logic was extracted into a shared `stats-render.js` so the two pages can't drift —
   see [[flightlog_v0_9_sharing]] and `03-frontend-conventions.md`'s new note on this
   pattern.
3. **`v0.9.6`** — flight links: multiple YouTube videos + one XContest link per flight, pasted by
   hand (no API integration, per the pilot's own "for now" framing). Reuses the existing
   `flight_links` table (shipped v0.8, previously only written by VidFactory) for the pilot's own
   first manual write path onto it; manually-pasted video links reuse VidFactory's own
   `kind="video"` rather than a new kind, so both sources render in one list. Also shows on a
   flight's public page when shared (confirmed with the pilot).

245/245 backend tests passing (up from 229 at the start of this run), `ruff check`/`ruff format
--check` clean throughout. Docs (`architecture.md`, `features.md`, `README.md`) synced
incrementally after each release, not batched at the end. `pyproject.toml`: `0.9.3` → `0.9.4` →
`0.9.5` → `0.9.6`, `poetry install` re-run after each bump.

**Not yet done**: the Chrome extension never connected in any session that shipped `v0.9.4`
through `v0.9.6` — every UI change (categories page, profile page, public-stats page, the links
card on flight-detail/public-flight) is functionally verified (curl against a throwaway account,
DOM-id/`data-i18n` cross-checks) but **never visually confirmed in a real browser**. First thing
to check next time the extension is available — start with `/public/stats/{id}` (the largest,
most chart-heavy new page) and the flight-links UI (the newest, least-exercised interaction
pattern: inline add/remove, no drawer).

## Next Step

Carried forward, still open:

1. **Confirm whether Traefik replaces or appends to `X-Forwarded-For`** before treating the public
   rate limiter's `client_ip` key as abuse-resistant rather than just accidental-burst-resistant.
   Now higher-stakes than when first noted — `/api/public/*` has grown from 2 to 4 route families
   since (`flights`, `profiles`, `stats`, and `flights/{id}`'s new `links`), all sharing the same
   limiter.
2. **The repository's visibility itself is still private** — the `Flugbuch.xlsx` scrub (done
   2026-08-16) was the prerequisite, not the act of flipping the switch. Separate step, pilot's
   call.
3. **`C:\git\flightlog-pre-scrub-backup\`** (pre-scrub full-repo bundle + a copy of the real
   workbook) can be deleted once the pilot is confident the scrub is stable — not urgent.
4. **XContest score import** (the auto-matched, independently-verified `xc_official_score` — not
   to be confused with `v0.9.6`'s manual link) and **`specs/002-flight-log-ui`'s Phases 10–11**
   (CSV export, remember-last-filters) remain open backlog items, untouched.
5. **No visual/browser confirmation of `v0.9.4`–`v0.9.6`'s UI** — see above.

## Context

- The dev server needs a restart after every backend edit (no `--reload` in this workflow) — see
  [[flightlog_dev_server_workflow]].
- **Any new unauthenticated page must use `bootstrapPage({ anonymous: true })`**, not just
  `{ requireAuth: false }` — see [[flightlog_public_page_pattern]].
- **`slowapi`'s `Limiter` is a module-level singleton** — see
  [[flightlog_slowapi_rate_limit_trap]] if a future public-route test starts failing with an
  unexplained 429.
- **Prod moved off `fl.sdh.lol`** (retired) to `fl.lenti.cloud` / `flightlog.lenti.cloud`, and the
  whole-host Traefik OIDC (Pocket-ID) gate that used to front it is gone — see
  [[flightlog_prod_oidc_layer]] and `architecture.md`'s Deployment section. `/api/public/*` is now
  genuinely reachable by an anonymous stranger in production, not just in the app's own code.
- **Every new public disclosure surface gets its own independent opt-in flag** (never reuse or
  imply from an existing one) and **bundles what would otherwise be several endpoints into one
  response** (the public surface shares one rate-limit budget per visitor) — both now-established
  conventions, written up in `04-constraints.md`.
- **Live-verification pattern used throughout this run**: register a throwaway account via the
  running dev server, exercise the real feature end-to-end via `curl` (never fabricate output),
  then delete the throwaway account/flights/sites/categories/on-disk IGC files from the real dev
  DB afterward. The pilot's own real account and data are never touched.

This file is a pointer, not a duplicate — `.ai/context/features.md`, `architecture.md`, and each
feature's own `specs/` folder have the detail.
