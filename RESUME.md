# Resume Notes — 2026-08-16

## In Progress

**`v0.9.0` (sharing & public readiness) is implemented, tested, live-verified and docs-synced
this session — not yet committed, tagged or deployed.** This picks up straight from the prior
session's `v0.8.1` ship (see git log / the section below this one for that history).

### What shipped in `v0.9.0`

Implemented per the full spec/plan/tasks already written in `specs/007-sharing-public-readiness/`
(all 20 tasks now ticked `[x]`). See `.ai/context/architecture.md`'s "Sharing & public readiness"
section for the complete technical detail — summary here:

1. **`flights.visibility`** (`private`\|`unlisted`\|`public`, default `private`) and
   **`users.public_profile_enabled`** (boolean, default `False`) — two new columns via
   `_run_column_migrations()`'s idempotent guard.
2. **`/api/public`** (`api/routers/public.py`) — unauthenticated by design, `GET /flights/{id}` and
   `GET /profiles/{user_id}`, both byte-identical 404s for "missing" vs. "exists but not public".
   `models/public.py`'s `PublicFlightOut`/`PublicProfileOut` are an explicit field allowlist.
3. **`slowapi` 0.1.10** — new dependency, per-route decorators only (never a global middleware),
   keyed on the X-Forwarded-For-aware `client_ip`, mapped to this app's own `RATE_LIMITED` error
   envelope on a 429.
4. **`core/user_seed.py`** — five starter categories seeded on self-registration, guarded by
   `users.seeded_at IS NULL` (the first real consumer of that column, reserved since v0.2).
5. **Frontend**: `public-flight.html`/`.js`, `public-profile.html`/`.js` (new), a visibility control
   on `flight-detail.html`/`.js`, a public-profile toggle card on `api-keys.html`/`.js`.
   `bootstrap.js` gained a new `anonymous: true` option to `bootstrapPage()` — a second-pass fix
   (an advisor review caught it, curl couldn't): the two public pages originally used
   `requireAuth: false` only, which still ran `renderNavAuth()` → `loadCurrentUser()` →
   `fetchAuth('/api/auth/me')` whenever *any* token happened to be in `localStorage`, and a stale
   token's failed refresh silently redirected an anonymous visitor to `/login` — exactly the FR-013
   violation this feature was supposed to prevent, invisible to every curl-based check because curl
   has no localStorage. `anonymous: true` skips the token check and the authenticated nav links
   entirely, regardless of what's in `localStorage`. Mechanically proven (not just reasoned about)
   with a Node harness importing the real `bootstrap.js` under a stubbed DOM/localStorage/fetch: a
   garbage token present → no redirect, no `/api/auth/me` call; the same scenario with the old
   `anonymous: false` behavior reproduces the exact redirect-to-`/login` bug, confirming the harness
   is actually sensitive to it.
6. **14 new tests** (`test_public_routes.py`, `test_user_seed.py`) — 225/225 passing project-wide,
   `ruff check`/`ruff format --check src/ tests/` clean. The private-vs-nonexistent and
   disabled-vs-nonexistent 404 tests compare `.content` (raw bytes), not `.json()` (structural
   equality) — `plan.md`'s Risk section specifically asks for byte-for-byte, not "both happen to
   parse the same."
7. **NFR-003 copy fix**: the visibility hint shown before a pilot saves `unlisted`/`public` now says
   "…including your notes" — the live curl pass returned a real flight comment naming a friend
   (`04-constraints.md` singles this out as the dataset's sensitive content), and the original hint
   text didn't make clear that notes are part of what becomes visible.
8. **Known, documented, unverified risk**: the rate limiter's key function
   (`dependencies.client_ip`) trusts `X-Forwarded-For` as-is, which is fine for its original use
   (audit-log lines) but means the limiter is only abuse-resistant if this deployment's Traefik
   *replaces* that header rather than appending to a client-supplied one. Not verified this
   session (would require touching prod config, off-limits per `04-constraints.md`) — flagged in a
   code comment in `public.py` and here rather than silently assumed safe.

**Live-boot verified via `curl` against the local dev server** (`CONFIG_PATH=config.yml
PYTHONPATH=src python -m poetry run uvicorn flightlog.api.main:app --host 127.0.0.1 --port 8002`):
set a real flight to `public`, confirmed unauthenticated access and a byte-identical 404 for a
private flight vs. a made-up id; opted the real dev account into a public profile and confirmed it
listed exactly the one public flight; fired a 33-request burst against the default `30/minute` limit
and confirmed 429s with the correct envelope while the authenticated `/api/flights` call kept
succeeding throughout; registered a fresh account and confirmed exactly 5 editable categories.
**All test-only state was reverted/deleted from the real dev DB afterward** — the flight's
visibility and the account's `public_profile_enabled` were set back, and the throwaway registered
user + its seeded categories were removed via direct SQL (no user-delete endpoint exists yet). The
pilot's own real account and 600-flight data were untouched by the end of the session.

`pyproject.toml` bumped `0.8.1` → `0.9.0`, `poetry install` re-run so `APP_VERSION` isn't stale.
Docs synced: `architecture.md` (new "Sharing & public readiness" section, SQLite Tables and API
Contracts rows updated), `01-project-overview.md` (Repository Layout, self-registration note),
`features.md` (v0.9 rewritten from "planned" to "shipped", Current Version bumped), `README.md`
(new v0.9 paragraph, Status line, config table row — also fixed a pre-existing broken sentence
split across the v0.8/v0.8.1 paragraphs from a prior session), `specs/007-.../tasks.md` (all 20
tasks ticked).

## Next Step

1. **Not yet committed, tagged or pushed.** Review the diff, commit, bump the tag to `v0.9.0`, push
   — same flow as every prior release.
2. **The git-history scrub of `olddata/Flugbuch.xlsx` is still outstanding and deliberately not
   part of this session's work.** It's a destructive, hard-to-reverse repository operation (a
   history rewrite, not a plain `git rm`) that `specs/007-.../research.md` scoped as a separate,
   explicitly pilot-confirmed action — required before the repository's own visibility can ever
   change to public, not before this feature ships. Raise it with the pilot when they're actually
   ready to make the repo public, not as a routine follow-up task.
3. **Making the deployed instance itself reachable by strangers needs one more thing this feature
   doesn't touch**: `fl.sdh.lol` sits behind a Traefik `traefik-oidc-auth` (Pocket-ID) middleware
   protecting the *entire* host (see `features.md`'s v0.7 "Also investigated" note and the
   `flightlog_prod_oidc_layer` memory) — every `/api/public/*` and `/public/*` route this feature
   built will be unreachable by an anonymous visitor in production until that middleware is
   reconfigured to exclude those paths. That's shared infrastructure the pilot must change
   themselves (`04-constraints.md`); flag it before or during the next deploy, don't assume it's
   already scoped correctly.
4. **Confirm whether Traefik replaces or appends to `X-Forwarded-For`** before treating the public
   rate limiter as abuse-resistant rather than just accidental-burst-resistant — see item 8 above.
   Cannot be checked from this repo; needs the pilot or prod-side confirmation.
5. **XContest score import** remains a backlog item.
6. **`specs/002-flight-log-ui`'s Phases 10-11** (CSV export, remember-last-filters) — still open,
   not tied to any particular tag.

## Open Questions

- Has the Traefik OIDC middleware in front of `fl.sdh.lol` been scoped to exclude `/public/*` and
  `/api/public/*`? Without that, the public surface this session built is real in the app but
  unreachable by an actual anonymous stranger on the live instance.
- Does this deployment's Traefik replace `X-Forwarded-For` or append to it? Determines whether the
  public-route rate limiter is a real abuse control or just an accidental-burst guard.

## Context

- **The dev server needs a restart after every backend edit** (no `--reload`). See
  [[flightlog-dev-server-workflow]]. Hit this directly this session: the first live-boot attempt
  bound against a stale ~6.7-hour-old server still holding port 8002 from an earlier session and
  had to be killed via `Get-NetTCPConnection -LocalPort 8002 | Stop-Process -Force` before the new
  code would actually be exercised — a stale-server false negative, not a real bug, exactly as the
  memory note warns.
- **slowapi's `Limiter` is a module-level singleton** (`api/routers/public.py`'s `limiter`), shared
  across every `create_app()` call within one process — including every test. Its in-memory rate
  counters persist across tests unless explicitly reset, which is why `test_public_routes.py` has
  an autouse fixture calling `limiter.reset()` before and after every test in that file. Worth
  remembering if a future public-route test starts failing with an unexplained 429.
- **`slowapi`'s `@limiter.limit(...)` decorator accepts a callable, not just a literal string** —
  used deliberately here (`_public_rate_limit()` reads `get_config()` fresh per request) rather
  than a bare string, since a literal freezes at module-import time, before `load_config()` has run
  in the app lifespan, and would make the limit impossible to override in tests or via a live
  config reload.

This file is a pointer, not a duplicate — `.ai/context/features.md`, `architecture.md`, and each
feature's own `specs/` folder have the detail.
