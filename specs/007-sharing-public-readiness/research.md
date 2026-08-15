# Research: Sharing & Public Readiness

## Decision: two of `features.md`'s original three roadmap items for this milestone are already done — confirmed against the real code, not assumed

- **Buddy invite/accept/decline**: `architecture.md`'s API Contracts table already lists
  `POST /api/buddies/{id}/link` (+ `/link/accept` + `/link/decline`) as **shipped v0.2** — and the real
  `src/flightlog/api/routers/buddies.py` confirms it: the routes exist, `link_state` transitions
  correctly, the "always 202 regardless of whether the email is registered" enumeration-safety rule
  (`04-constraints.md`) is implemented. **Not part of this feature.**
- **`allow_self_registration` genuinely flippable**: already true today — `config.py`'s
  `AuthConfig.allow_self_registration` is a real boolean the real `POST /api/auth/register` checks
  (403 when `False`), and `GET /api/auth/registration-status` already exposes the current value.
  **Not part of this feature as originally worded.**
- **What genuinely remains**: `auth.py`'s own `register()` handler carries a comment — *"Per-user
  defaults (flight categories) are seeded from here in v0.2, guarded by `users.seeded_at IS NULL`"* —
  that was never actually implemented. `specs/001-core-data-import/research.md` explains why: "A generic
  starter set only matters once self-registration is live... building it now is designing for a
  hypothetical signup that cannot happen yet" — an entirely reasonable call at the time, deferred
  explicitly to this exact future point (that document's own numbering scheme called this milestone
  "v0.8," before this session's renumbering; the deferred *work* is the same regardless of which number
  it's attached to). This is a real, well-documented, still-open gap — a self-registered pilot today
  gets an account with zero flight categories and no way to log a flight until they hand-create at least
  one, since `category_id` is `NOT NULL` on `flights`. This feature closes that gap. `users.seeded_at`
  already exists as reserved plumbing (`database/models.py`), unused — this feature is its first
  consumer.

## Decision: seed a small, generic, English-language starter category set — not the 12 legacy German categories verbatim

- **Decision**: seed exactly five categories on first self-registration:
  `Thermal`, `Soaring`, `XC`, `Hike&Fly`, `Sled run` — with `is_hike_fly`/`is_training` flags set the
  same way `core/aliases.py`'s `CATEGORY_FLAGS` already sets them for the equivalent legacy concepts
  (`Hike&Fly` → `is_hike_fly=True`; none of these five are training categories).
- **Rationale**: the 12 legacy categories (`core/aliases.py`'s `CANONICAL_CATEGORIES`) are this specific
  pilot's own real historical data, imported verbatim in German — several of them are personal or
  jurisdiction-specific artifacts (`Schwarzflug` = unauthorized/illegal flying, `Prüfung` = a licensing
  exam, `Startleiter` = a launch-marshal duty at a flight school) that make no sense as a *generic*
  default for an arbitrary new self-registered pilot who could be anyone, anywhere. Seeding all 12
  verbatim would misrepresent this pilot's personal history as a universal template. English, not
  German, because a new self-registration path is the first point where this app might reasonably serve
  a pilot who isn't the original German-speaking one — `SUPPORTED = ['en']` is already the only UI
  locale, so this is consistent, not a new precedent.
- **Alternatives considered**: seed all 12 legacy names. Rejected for the reason above. Seed zero
  categories and just relax the `NOT NULL` constraint on `flights.category_id` instead. Rejected — that
  changes an existing, working data-integrity rule for every pilot to work around a gap that only
  affects the *first flight* of a *newly self-registered* account; seeding five sensible defaults is
  less invasive and gives the new pilot something immediately useful rather than a forced null-handling
  path everywhere category is read.
- FR-011 already guarantees this isn't a lock-in — the pilot can rename, reorder, or archive any seeded
  category immediately, exactly as if they'd typed it in themselves.

## Decision: `flights.visibility` is a plain string column, matching this app's existing enum-as-string convention

- **Decision**: `flights.visibility` — `String, not null, default "private"`, values
  `private`\|`unlisted`\|`public`. Not a new lookup table, not a database-level `CHECK` enum.
- **Rationale**: matches how every other enum-shaped value in this schema already works —
  `buddies.link_state`, `sites.coord_source`, `igc_tracks.alt_source`, `igc_pending_uploads.status` are
  all plain, application-validated strings, never a DB-level enum type or a lookup table. Consistency
  with the established pattern, not a new one.

## Decision: reuse the existing opaque `users.id` as the public-profile identifier — no new "slug" column

- **Decision**: a public profile lives at a URL keyed on the pilot's existing `users.id` (a UUID) —
  no new human-friendly slug/username column.
- **Rationale**: `spec.md`'s Assumptions require the identifier to not be enumerable — a UUID already
  satisfies this with zero new schema, consistent with how every other public-facing identifier in this
  app (a flight id, a site id) is already an opaque UUID, never a sequential integer. A prettier,
  human-chosen slug (a public "username") is a real, reasonable future enhancement, but it's also a much
  bigger decision (uniqueness, allowed characters, change-after-the-fact implications, squatting) that
  `spec.md` never asked for — this feature's job is "opt in to a public profile," not "design a
  username system."
- **Alternatives considered**: a dedicated `profile_slug` column, pilot-chosen. Rejected as unrequested
  scope beyond what `spec.md`'s stories actually ask for (a durable, shareable link — a UUID-based one
  is already durable and shareable, just not memorable) — worth a backlog note, not this feature's job.

## Decision: rate limiting via `slowapi` — reverified current, not copied from a sibling project

- **Decision**: `slowapi` 0.1.10 (verified against PyPI's JSON API this session, per
  `02-backend-conventions.md`'s dependency-freshness rule — not assumed, not copied from Lenticularis or
  VidFactory). It's a small, actively-published Starlette/FastAPI rate-limiting library requiring no
  external dependency (in-memory limiter is sufficient for this single-instance deployment,
  `architecture.md`'s deployment section: one named Docker volume, no multi-instance/Redis
  infrastructure exists or is implied elsewhere in this project).
- **Rationale**: this is the first time this app needs rate limiting at all — every existing route is
  either JWT-authenticated (a logged-in pilot, trusted) or the one already-public `/health` route (not a
  target for abuse in a way that matters). `04-constraints.md`'s "No InfluxDB, no scheduler" rule doesn't
  block this — `slowapi` needs neither.
- **Alternatives considered**: hand-rolled in-memory rate limiting (a dict of IP → timestamp windows).
  Rejected as reinventing a small, well-tested wheel for no real benefit — `slowapi` is exactly this,
  already written and maintained.

## Decision: public routes live in their own router(s), unauthenticated by design — following `health.py`'s existing precedent exactly

- **Decision**: `api/routers/public.py` holds every unauthenticated route this feature introduces
  (public flight view, public profile view) — no `Depends(get_current_user)` anywhere in this file, and
  the file's own docstring says so explicitly at the top, matching `health.py`'s existing "this router is
  unauthenticated by design" convention (`02-backend-conventions.md`: "the absence of a dependency is
  what makes a route public — so any public route must live in its own router and say so").
- **Rationale**: this is already the established pattern for the one prior public route in this app;
  this feature is simply its second and third consumer, not a new convention.

## Decision: the git-history scrub is an explicitly out-of-band, user-confirmed operational step — not an implementation task this plan schedules

- **Decision**: `spec.md`'s Success Criteria requires it to have happened before the repo goes public,
  but no task in this feature's `tasks.md` performs it. It is a destructive, hard-to-reverse repository
  operation (rewriting history, not deleting a file — every existing clone/fork keeps the old blob
  reachable unless independently re-synced) and must be a separate, explicitly-confirmed action with the
  pilot at the moment it's actually done, consistent with this project's own general safety posture
  around destructive operations.
- **Rationale**: bundling a repo-history rewrite into a routine feature-implementation task list risks
  it being executed as "just another checklist item" rather than the deliberate, confirmed action it
  needs to be. Keeping it named in the spec (so it isn't forgotten) but out of the task list (so it isn't
  automated) is the safer shape.
