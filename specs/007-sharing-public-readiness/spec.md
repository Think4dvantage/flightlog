# Feature: Sharing & Public Readiness

## Overview

Lets a pilot choose to show individual flights, or their whole flying identity, to people who don't have
an account — a public flight page for a specific achievement worth sharing, and a public pilot profile
as a durable, linkable presence. Closes out the two remaining prerequisites for genuinely opening this
service to strangers: a real self-registration path (not just a flippable flag guarding a broken
account) and removing the one piece of committed data that must never become publicly reachable.

## Clarifications

### Session 2026-08-15
- Q: `features.md`'s original wording for this milestone listed "buddy invite/accept flow" and
  "`allow_self_registration` genuinely flippable" as deliverables — are either still needed? → A: The
  buddy invite/accept/decline flow has been shipped since `v0.2` (confirmed against the real
  `buddies.py` router) — not part of this feature. `allow_self_registration` is already a working
  config flag — also not part of this feature as stated. What genuinely remains, discovered while
  verifying this: self-registering today creates an account with **zero flight categories**, because
  the generic per-account starter-category seeding was explicitly deferred, in v0.2's own planning
  research, to "once self-registration is live" — this feature is where that deferred work actually
  lands.
- Q: Is the git-history scrub of `olddata/Flugbuch.xlsx` something this feature's implementation
  performs automatically as one of its tasks? → A: No — a git history rewrite is destructive and
  effectively irreversible (every existing clone, fork, or local checkout keeps the old history unless
  explicitly re-synced). This spec requires it to ship before the pilot makes the repository public, but
  the action itself must be explicitly confirmed with the pilot at the moment it's actually performed,
  never bundled into an "and also run this" implementation step.

## User Stories

### P1 — Must Have

**As a pilot, I want to mark an individual flight as unlisted or public so I can share a specific
achievement with someone via a link, without exposing my whole flight log.**

Acceptance Criteria:
- Every flight defaults to private (today's implicit behavior, made explicit).
- A flight can be set to unlisted (reachable only by its exact URL, never listed or searchable) or
  public (reachable by URL and discoverable from the pilot's own public profile, if they have one).
- A private or unlisted flight's URL, if guessed or shared without permission, never leaks anything
  about a *different* flight, site, or pilot — only exactly what that one flight's own visibility
  setting allows.
- Changing a flight back to private immediately stops it from being viewable by anyone without an
  account, with no propagation delay.

**As a pilot, I want a public profile page so I have one durable link that represents my flying, rather
than sharing individual flight links one at a time.**

Acceptance Criteria:
- A pilot can opt in to having a public profile at all — profiles are opt-in, not on by default.
- An opted-in profile shows the pilot's display name and their public flights only — never a private or
  unlisted flight, and never any other pilot's data.
- A pilot can opt back out at any time, immediately removing the public profile from view.

**As the operator, I want the public-facing surface rate-limited so a single abusive client can't
overwhelm the service the way an authenticated, trusted surface doesn't need to worry about.**

Acceptance Criteria:
- Every public (unauthenticated) route enforces a request-rate ceiling per client.
- A client that exceeds the ceiling receives a clear, typed rejection, not a silent drop or an
  unrelated-looking error.
- The authenticated surface (everything requiring a JWT or API key) is unaffected — this limiting
  applies specifically to the newly-public routes this feature introduces, not the entire application.

### P2 — Should Have

**As a new pilot, I want self-registration to give me a working, usable account immediately, not an
empty shell missing basic categories I'd otherwise have to create by hand.**

Acceptance Criteria:
- A self-registered account is seeded with a generic starter set of flight categories on creation,
  guarded so it only happens once per account (reusing the already-reserved `users.seeded_at` column and
  guard pattern named in this project's own prior planning).
- The pilot can still edit, rename, reorder, or archive any seeded category exactly as if they'd created
  it themselves — the seed is a starting point, not a locked default.
- This applies only to a genuinely new self-registered account — it never runs again for, or retroactively
  touches, the existing pilot account.

### P3 — Nice to Have

**As a pilot with a public profile, I want basic visit/view counts so I know whether anyone's actually
looking.**

Acceptance Criteria: out of scope for this feature — no analytics beyond what operational request logs
already capture; a dedicated view-counting feature is a fast-follow, not blocking.

## Functional Requirements

- FR-001: The system MUST support a per-flight visibility state of private, unlisted, or public,
  defaulting every flight to private.
- FR-002: An unlisted flight MUST be viewable only by its exact URL — never listed, indexed, or
  discoverable from any other public surface.
- FR-003: A public flight MUST be viewable by URL and discoverable from its owner's public profile, if
  the owner has one.
- FR-004: Changing a flight's visibility MUST take effect immediately, with no caching or propagation
  delay that could expose a now-private flight.
- FR-005: The system MUST let a pilot opt in to a public profile, off by default.
- FR-006: A public profile MUST show only its owner's public flights and display name — never a
  private or unlisted flight, and never another pilot's data under any circumstance.
- FR-007: A pilot MUST be able to opt out of a public profile at any time, taking effect immediately.
- FR-008: The system MUST rate-limit every unauthenticated (public) route introduced by this feature,
  independently of the authenticated surface.
- FR-009: A rate-limited request MUST receive a clear, typed rejection response, never a silent failure.
- FR-010: A newly self-registered account MUST be seeded with a generic starter set of flight
  categories, exactly once, using the existing `users.seeded_at`-guard pattern already reserved for this
  purpose.
- FR-011: The seeded starter categories MUST be fully editable afterward — the same as if the pilot had
  created them directly.
- FR-012: All user-visible chrome for this feature's new views MUST go through the existing translation
  mechanism; a pilot's own flight/profile content (notes, display name) MUST never be translated.
- FR-013: Every new view MUST use the existing dark theme and navigation shell, adapted appropriately
  for an unauthenticated visitor (no nav items requiring login, no leak of whether the *visitor* is
  logged in as a different pilot entirely).

## Non-Functional Requirements

- NFR-001: A public flight or profile page must load reasonably fast for an anonymous visitor — the
  same performance bar as every authenticated page, not a lesser one, since this is the one surface a
  stranger's first impression of the whole project rests on.
- NFR-002: Every new view must be usable by keyboard alone.
- NFR-003: Changing a flight's visibility to more open (private → unlisted → public), and opting in to a
  public profile, are both consequential, hard-to-fully-undo-the-consequences-of actions (once a URL is
  shared, this app cannot un-share it from wherever it ended up) — the UI must make the resulting
  exposure level unambiguous before the pilot confirms the change, though a single confirmed action is
  sufficient; this is a "be clear," not a "require a second click," requirement.

## Success Criteria

- A pilot can share a single flight's achievement with someone outside the app without exposing anything
  else.
- A pilot can maintain one durable public-profile link that stays current as they fly more, without
  manual upkeep.
- The public surface survives a burst of unauthenticated traffic without degrading the authenticated
  experience for the pilot's own logged-in session.
- A newly self-registered pilot can start logging flights immediately, with a usable set of categories,
  without first needing to understand and manually recreate what the historical import gave the original
  pilot for free.
- `olddata/Flugbuch.xlsx` is confirmed absent from git history (not merely from the working tree) before
  the repository's visibility is ever changed to public — verified, not assumed.

## Key Entities

| Entity | Key Attributes | Notes |
|--------|---------------|-------|
| Flight (existing) | + visibility (private\|unlisted\|public) | The only new data this feature adds to an existing entity |
| Public profile setting | opted-in (bool), owner | Could be a flag on `users` rather than a new table — a planning-phase decision, not a product one |

## Out of Scope

- View-count analytics on public content (P3, deferred).
- Any change to the buddy invite/accept/decline flow — already shipped in v0.2, not touched here (see
  Clarifications).
- Any change to whether `allow_self_registration` can be toggled — already true today (see
  Clarifications); this feature only makes the *result* of toggling it on actually usable.
- A generic, official shared site catalogue (`sites.owner_id IS NULL`, mentioned in `architecture.md`'s
  Sites section as reserved for a future layer with "nothing uses it yet") — a conceptually related but
  distinct kind of "sharing" (site data, not flight/profile visibility) that this feature does not
  implement.
- Actually performing the git-history rewrite as part of this feature's own implementation tasks — the
  spec requires it to have happened before the repo goes public, but the act itself is a separately
  confirmed, high-risk operational step (see Clarifications).

## Assumptions

- There is exactly one pilot account in the system today (matches every prior feature's assumption) —
  this feature's visibility model is designed to be correct once multiple pilots exist, even though only
  one does right now to test it against.
- A public profile's URL is based on something stable and non-guessable-as-an-enumeration-vector (a
  planning-phase decision — not, e.g., a sequential integer that would let a visitor enumerate every
  pilot).
- "Rate limiting on the public surface" means the *new* unauthenticated routes this feature introduces —
  it does not retroactively add limiting to `/health` or any other already-public route unless a
  planning-phase review finds a specific reason to.

## Dependencies

- Requires the existing `flights` table and its ownership model.
- Requires `users` (for the public-profile opt-in and the self-registration seeding gap).
- Requires `allow_self_registration` and `POST /api/auth/register` (v0.1/v0.2, already shipped) as the
  entry point the seeding gap (FR-010) attaches to.

## Edge Cases

- A pilot deletes or un-publics a flight that a public profile was linking to: the profile's flight list
  must reflect the change immediately, never show a broken or stale link.
- A rate-limited anonymous visitor who is *also*, in a different browser tab, a logged-in pilot: the
  limiting must apply to the anonymous request path only — the pilot's own authenticated session must
  never be affected by rate-limit state accumulated against their IP on the public surface.
- Two different pilots' public profiles: one pilot's profile must never, under any request pattern,
  surface even a hint of another pilot's existence beyond what's already inherent in a public,
  discoverable URL scheme (e.g. a not-found response for an unknown profile must look identical whether
  the profile never existed or exists but isn't public).
- A newly self-registered account immediately importing their own Excel workbook via the existing
  importer: the seeded starter categories must not conflict with or duplicate categories the importer
  itself would create — the importer's own existing `_get_or_create_category` idempotency (matching by
  `owner_id` + slug) already handles this correctly by construction, but this feature's seeding must use
  the same category names/slugs, not a differently-spelled parallel set that would produce two "XC"-like
  categories for the same pilot.
