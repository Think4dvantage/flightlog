# Resume Notes — 2026-08-16

## In Progress

**`v0.9.0` (sharing & public readiness) is implemented, tested, committed, tagged and pushed.**
The `olddata/Flugbuch.xlsx` git-history scrub the pilot explicitly requested immediately
afterward has been **performed and pushed — fully complete, independently verified against a
fresh clone from GitHub itself.** This picks up straight from the prior session's `v0.8.1` ship.

### What shipped in `v0.9.0`

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
   Still unverified — see "Open Questions".

`pyproject.toml` bumped `0.8.1` → `0.9.0`. Docs fully synced (`architecture.md`, `features.md`,
`01-project-overview.md`, `02`/`03`/`04-...md`, `07-api-conventions.md`, `README.md`,
`specs/007-.../tasks.md`).

### `olddata/Flugbuch.xlsx` git-history scrub — done, pushed, verified

The pilot's follow-up message ("scrub the flugbuch - this is just a copy") was the explicit,
in-the-moment confirmation `specs/007-.../research.md` required before ever performing this.

**Safety steps taken before the rewrite:**
- Confirmed the working tree was clean (`git status` — required by `git-filter-repo`).
- Confirmed `tests/fixtures/flugbuch_sample.xlsx` is a separate, synthetic 6 KB test fixture
  (fabricated dates, generic comments) — **not** touched, out of scope; only
  `olddata/Flugbuch.xlsx` (171 KB, the real 600-flight workbook) was in scope.
- Copied the file itself, and a full-repo bundle backup (`git bundle create --all`, all branches
  + all 15 tags, verified with `git bundle verify`), to **`C:\git\flightlog-pre-scrub-backup\`**
  before running anything destructive. **Still there — safe to delete once you no longer want a
  recovery path**, e.g. after a few weeks of the repo being public with no issues.

**The rewrite**: `python -m git_filter_repo --path olddata/Flugbuch.xlsx --invert-paths --force`.
Removed the file from every commit, including HEAD. Every commit SHA changed, and all 15 tags
(`v0.1.0`–`v0.9.0`) were rewritten to new SHAs — expected and unavoidable for a real scrub.

**Follow-up**:
- The file was restored to `olddata/Flugbuch.xlsx` on disk as an **untracked** file — the importer
  and the real-workbook regression tests (already `skipif`-gated on its presence) keep working
  locally without ever re-committing it. `.gitignore` gained `/olddata/`.
- Full test suite re-run after restoring the file: 225/225 still passing, confirming the
  real-workbook tests genuinely ran (not silently skipped).
- Committed as `0c848a0` on top of the rewritten `v0.9.0` commit.

**Push, and the permission snag along the way**: `git-filter-repo` removes the `origin` remote by
design; re-adding it via Bash was blocked by the Claude Code auto-mode permission classifier
(git remote/config changes are gated). The pilot ran `git remote add origin ...` themselves. A
first `git push` (no `--force`) was correctly rejected — local and remote history share no common
ancestor after a rewrite, so a fast-forward push can never work; this is not a sign anything went
wrong. **After explicit confirmation, force-pushed `main` (`27f79cd` → `0c848a0`) and all 15 tags.**

**Independently verified against GitHub itself, not just local state**: fresh `git clone` of
`https://github.com/Think4dvantage/flightlog.git` into a scratch directory, then
`git log --all -- olddata/Flugbuch.xlsx` (empty) and
`git rev-list --objects --all | grep -i flugbuch.xlsx` (empty, ignoring the unrelated sample
fixture) — the file is gone from GitHub's own copy, not just believed gone from the push output.
15 tags present, `HEAD` matches. Scratch clone deleted afterward.

**What this does *not* retroactively fix**: any existing clone or fork of this repo (if one
exists) keeps the old history, including the real workbook, until it's explicitly re-synced
against the rewritten remote. This push only changes what `origin` itself now serves.

## Next Step

1. **Making `fl.sdh.lol` itself reachable by strangers needs one more thing v0.9 doesn't touch**:
   a Traefik `traefik-oidc-auth` (Pocket-ID) middleware protects the *entire* host (see
   `features.md`'s v0.7 "Also investigated" note and the `flightlog_prod_oidc_layer` memory) —
   every `/api/public/*` and `/public/*` route is unreachable by an anonymous visitor in
   production until that middleware is reconfigured to exclude those paths. Shared
   infrastructure the pilot must change themselves.
2. **Confirm whether Traefik replaces or appends to `X-Forwarded-For`** before treating the
   public rate limiter as abuse-resistant rather than just accidental-burst-resistant.
3. **The repository's visibility itself hasn't been changed to public yet** — the scrub was a
   prerequisite (per `04-constraints.md`), not the act of flipping the switch. That's still a
   separate step for the pilot whenever they're ready.
4. **`C:\git\flightlog-pre-scrub-backup\`** can be deleted once the pilot is confident the scrub
   is stable (see Context below) — not urgent, no action needed now.
5. **XContest score import** and **`specs/002-flight-log-ui`'s Phases 10-11** (CSV export,
   remember-last-filters) remain open backlog items, not tied to any particular tag.

## Open Questions

- Has the Traefik OIDC middleware in front of `fl.sdh.lol` been scoped to exclude `/public/*` and
  `/api/public/*`?
- Does this deployment's Traefik replace `X-Forwarded-For` or append to it?
- Is the pilot ready to actually flip the repository's visibility to public now that the scrub is
  done, or is that a separate future decision?

## Context

- **`C:\git\flightlog-pre-scrub-backup\`** holds the pre-scrub full-repo bundle
  (`flightlog-full-backup.bundle`, all branches + all 15 pre-scrub tags) and a copy of the real
  `Flugbuch.xlsx`. To fully restore the pre-scrub state if something is ever discovered wrong:
  `git clone flightlog-full-backup.bundle flightlog-restored`.
- **The dev server needs a restart after every backend edit** (no `--reload`). See
  [[flightlog-dev-server-workflow]].
- **slowapi's `Limiter` is a module-level singleton** — see [[flightlog_slowapi_rate_limit_trap]]
  if a future public-route test starts failing with an unexplained 429.
- **Any new unauthenticated page must use `bootstrapPage({ anonymous: true })`**, not just
  `{ requireAuth: false }` — see [[flightlog_public_page_pattern]].
- **`git remote add`/other git-config-adjacent commands are blocked for Claude Code by the
  auto-mode permission classifier in this environment** — when that happens again, the pilot
  needs to run the command themselves rather than Claude finding a workaround.

This file is a pointer, not a duplicate — `.ai/context/features.md`, `architecture.md`, and each
feature's own `specs/` folder have the detail.
