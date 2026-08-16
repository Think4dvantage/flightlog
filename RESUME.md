# Resume Notes — 2026-08-16

## In Progress

**`v0.9.0` (sharing & public readiness) is implemented, tested, committed, tagged and pushed.**
The `olddata/Flugbuch.xlsx` git-history scrub the pilot explicitly requested immediately
afterward has been **performed locally** (`git filter-repo`) but **not yet pushed** — blocked on
one permission step, see "Next Step" below. This picks up straight from the prior session's
`v0.8.1` ship.

### What shipped in `v0.9.0` (pushed, `v0.9.0` tag live, CI triggered and confirmed running)

Implemented per the full spec/plan/tasks already written in `specs/007-sharing-public-readiness/`
(all 20 tasks ticked `[x]`). See `.ai/context/architecture.md`'s "Sharing & public readiness"
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
   `requireAuth: false` only, which still redirected an anonymous visitor to `/login` if their
   browser held a stale token. Mechanically proven fixed with a Node harness importing the real
   `bootstrap.js` under a stubbed DOM/localStorage.
6. **14 new tests** (`test_public_routes.py`, `test_user_seed.py`) — 225/225 passing project-wide.
   The private-vs-nonexistent and disabled-vs-nonexistent 404 tests compare `.content` (raw bytes),
   not `.json()`.
7. **NFR-003 copy fix**: the visibility hint now says "…including your notes" — a live curl pass
   returned a real flight comment naming a friend.
8. **Known, documented, unverified risk**: the rate limiter's key function
   (`dependencies.client_ip`) trusts `X-Forwarded-For` as-is — only abuse-resistant if this
   deployment's Traefik *replaces* that header rather than appending to a client-supplied one.

Committed `27f79cd` (pre-scrub SHA), tagged and pushed as `v0.9.0`, both "Backend tests" and
"Publish container image" CI workflows confirmed triggered. `pyproject.toml` bumped `0.8.1` →
`0.9.0`. Docs fully synced (`architecture.md`, `features.md`, `01-project-overview.md`,
`02`/`03`/`04-...md`, `07-api-conventions.md`, `README.md`, `specs/007-.../tasks.md`).

### `olddata/Flugbuch.xlsx` git-history scrub — performed locally, 2026-08-16, same session

The pilot's follow-up message ("scrub the flugbuch - this is just a copy") was the explicit,
in-the-moment confirmation `specs/007-.../research.md` required before ever performing this.

**Safety steps taken before the rewrite:**
- Confirmed the working tree was clean (`git status` — required by `git-filter-repo`).
- Confirmed `tests/fixtures/flugbuch_sample.xlsx` is a separate, synthetic 6 KB test fixture
  (fabricated dates, generic comments) — **not** touched, out of scope; only
  `olddata/Flugbuch.xlsx` (171 KB, the real 600-flight workbook) was in scope.
- Copied the file itself, and a full-repo bundle backup (`git bundle create --all`, all branches
  + all 15 tags, verified with `git bundle verify`), to **`C:\git\flightlog-pre-scrub-backup\`**
  (outside the repo, so the rewrite can't touch it) before running anything destructive.

**The rewrite**: `python -m git_filter_repo --path olddata/Flugbuch.xlsx --invert-paths --force`
(installed via `pip install --user git-filter-repo`, not on PATH — invoke as
`python -m git_filter_repo`). Removed the file from **every commit**, including the current HEAD
— confirmed via `git log --all -- olddata/Flugbuch.xlsx` (empty) and
`git rev-list --objects --all | grep -i flugbuch.xlsx` (empty). **Every commit SHA changed, and
all 15 tags (`v0.1.0`–`v0.9.0`) were rewritten to new SHAs** — this is expected and unavoidable
for a real history scrub, not a mistake.

**Follow-up (also done locally)**:
- The file was restored to `olddata/Flugbuch.xlsx` on disk as an **untracked** file (copied back
  from the pre-scrub backup) — `core/importer.py`/`core/secondary_import.py`'s default `--path`
  and the real-workbook regression tests (already `skipif`-gated on the file's presence, e.g.
  `test_importer.py`, `test_secondary_import.py`, `test_goals.py`) keep working locally without
  ever re-committing it.
- `.gitignore` gained `/olddata/` — uncommitted as of this note, needs a commit before push.
- Full test suite re-run after restoring the file: **225/225 still passing**, confirming the
  real-workbook tests genuinely ran (not silently skipped) against the untracked copy.
- `git-filter-repo` removes the `origin` remote by design as a safety measure. Re-adding it
  (`git remote add origin ...`) was **blocked by the Claude Code auto-mode permission
  classifier** — git remote/config changes are gated and this needs either the pilot running it
  themselves or explicitly granting the permission.

## Next Step

1. **Blocked on one permission step before the scrub can be pushed.** Either:
   - Run this yourself: `git remote add origin https://github.com/Think4dvantage/flightlog.git`
     (verify with `git remote -v`), then hand back to Claude to continue, **or**
   - Grant the Bash permission for `git remote add` so it can be run directly.
2. **Then the actual push — this is the truly irreversible, externally-visible step, confirm
   before doing it, not just before starting**: `git push origin main --force` and
   `git push origin --tags --force` (all 15 tags changed SHA, every one needs re-pushing).
   After this: anyone with an existing clone or fork keeps the *old* history (containing the
   real workbook) until they explicitly re-sync against the rewritten remote — this push cannot
   retroactively reach those copies. Worth being explicit with the pilot about that limit one
   more time, even though they already said "this is just a copy."
3. **Commit the `.gitignore` change** (`/olddata/`) before or as part of that push — currently
   uncommitted in the working tree.
4. **Update `.ai/` files to say the scrub is done, not pending** — `architecture.md`,
   `features.md`, `04-constraints.md`'s Personal Data section, and this file were updated to
   reflect the scrub *this session*, but re-check them once the push actually lands in case
   anything reads as still-hypothetical.
5. **Making `fl.sdh.lol` itself reachable by strangers needs one more thing v0.9 doesn't touch**:
   a Traefik `traefik-oidc-auth` (Pocket-ID) middleware protects the *entire* host (see
   `features.md`'s v0.7 "Also investigated" note and the `flightlog_prod_oidc_layer` memory) —
   every `/api/public/*` and `/public/*` route is unreachable by an anonymous visitor in
   production until that middleware is reconfigured to exclude those paths. Shared
   infrastructure the pilot must change themselves.
6. **Confirm whether Traefik replaces or appends to `X-Forwarded-For`** before treating the
   public rate limiter as abuse-resistant rather than just accidental-burst-resistant.
7. **XContest score import** and **`specs/002-flight-log-ui`'s Phases 10-11** (CSV export,
   remember-last-filters) remain open backlog items, not tied to any particular tag.

## Open Questions

- Has the pilot re-added the `origin` remote / granted the permission, and are they ready for the
  force-push specifically (not just the scrub in the abstract)?
- Has the Traefik OIDC middleware in front of `fl.sdh.lol` been scoped to exclude `/public/*` and
  `/api/public/*`?
- Does this deployment's Traefik replace `X-Forwarded-For` or append to it?

## Context

- **`C:\git\flightlog-pre-scrub-backup\`** holds the pre-scrub full-repo bundle
  (`flightlog-full-backup.bundle`) and a copy of the real `Flugbuch.xlsx` — keep this until the
  force-push has landed and been sanity-checked (`git clone`, `git log --all -- olddata/`, confirm
  empty), then it's safe to delete. To fully restore the pre-scrub state from the bundle if
  something goes wrong: `git clone flightlog-full-backup.bundle flightlog-restored`.
- **The dev server needs a restart after every backend edit** (no `--reload`). See
  [[flightlog-dev-server-workflow]].
- **slowapi's `Limiter` is a module-level singleton** — see [[flightlog_slowapi_rate_limit_trap]]
  if a future public-route test starts failing with an unexplained 429.
- **Any new unauthenticated page must use `bootstrapPage({ anonymous: true })`**, not just
  `{ requireAuth: false }` — see [[flightlog_public_page_pattern]].

This file is a pointer, not a duplicate — `.ai/context/features.md`, `architecture.md`, and each
feature's own `specs/` folder have the detail.
