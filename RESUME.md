# Resume Notes — 2026-08-14

## In Progress

**v0.3.2 is committed, tagged, and pushed; redeploy to `fl.sdh.lol` is the only thing left.**
`0.3.0` (`4a536ff`) went live first. `0.3.1` (`f9f06d2`) shipped a `/sites` redesign and `/import`
explanatory copy — confirmed auto-deployed and live within the same session (the pilot's own browser
console showed `sites.js?v=0.3.1`). While verifying it, the pilot's browser console turned up the real
bug 1 below, root-caused and fixed as part of `0.3.2`, not yet deployed.

**Bug 1 — map pin icon 404s on the map, even though the exact same URL loads fine when opened
directly.** Root cause **confirmed** from the pilot's browser console
(`GET https://fl.sdh.lol/static/vendor/leaflet/images//static/vendor/leaflet/images/marker-icon-2x.png
404` — note the doubled path) and traced to source in the vendored, minified `leaflet.js`:
`L.Icon.Default.prototype._getIconUrl` unconditionally returns
`(this.options.imagePath || <CSS-sniffed path>) + <name>Url` — it has no "this value is already
absolute" mode. The old `sites.js` set `iconUrl`/`iconRetinaUrl`/`shadowUrl` to full absolute paths via
`mergeOptions`, which doesn't disable that prefixing; it just means the auto/explicit `imagePath` prefix
lands in front of an already-absolute path, doubling it. On a non-retina display this silently degrades
(iconUrl's `marker-icon.png` truthy-shortcircuits before the retina branch ever runs); on a retina
display, `_getIconUrl('icon')` prefers `iconRetinaUrl`, and `_getIconUrl('shadow')` always uses
`shadowUrl` — both doubled, both 404. That's exactly why only `*-2x.png` and `marker-shadow.png` ever
appeared broken in the console, never the base `marker-icon.png`: on a retina display the base filename
is simply never requested. **Fixed** by setting `imagePath` explicitly and leaving `iconUrl` /
`iconRetinaUrl` / `shadowUrl` as bare filenames (Leaflet's own default shape) so `imagePath + name`
composes correctly instead of doubling. Verified locally: all three files 200 at their real,
non-doubled paths against a local dev boot; the earlier OIDC-session hypothesis in this file's prior
draft is **retracted** — the failures were plain 404s, not 401s, so auth was never the cause.

**Bug 2 — no way to re-edit a site once pinned.** Confirmed real and fixed by redesign, independent of
bug 1. The old page only let a row's click arm map-placement for a site with *no* coordinates yet;
a site that already had a pin could only be moved by finding and dragging its (possibly not-rendering,
per bug 1) marker — spec.md's own FR-009/FR-010 line ("editing a site's name or elevation does not
require re-placing its pin") implies a proper edit path that was never built.

**Fix (shipped in 0.3.1, live): `/sites` now has an Edit button per row opening a drawer** (name,
launch/landing flags, region, elevation, coordinates — all editable together, same drawer pattern as
`/flights` and `/equipment`). Coordinates have two independent paths: a "click the map to set the pin"
picker, and manual lat/lon text fields (deliberately `type="text"`, not `type="number"` — a browser set
to a comma-decimal locale silently reports `""` for `"46,4"` typed into a number input, which would
have quietly unpinned the site on save). One drawer bug caught and fixed before the 0.3.1 commit: the
drawer's own overlay is a fixed, full-viewport layer above the map — left as-is, the first map click
while picking would have hit the overlay and closed the drawer instead of placing the pin.
`armPicker()` now hides the overlay for the duration of the pick.

**The "import findings don't make sense" complaint (shipped in 0.3.1, live) needed no code fix, only
explanation.** Every mismatch on `/import` was already correctly root-caused in a *previous* session
(`.ai/context/architecture.md`'s Statistics section, `core/aliases.py`'s comments) — independently
re-derived and confirmed this session by re-running the exact resolution logic against
`olddata/Flugbuch.xlsx`:
- **"Advance Success 2" harness** (3 flights) is deliberately excluded from `CANONICAL_HARNESSES` —
  retired gear, not a misspelling; the importer never guesses. To bring it back: add it under
  `/equipment`, then edit those 3 flights to attach it (already-imported flights aren't touched by
  re-running the importer).
- **Region mismatches** (Interlaken +3, Grindelwald +1, Fiesch −1 vs. the legacy sheet's own Total
  column) are the legacy sheet's own internal inconsistency, not an import bug: three launch sites
  (`Ober Burgfeldstand` 1 flight, `Alp Unterburgfeld` 2 flights, `Lauberhorn` 1 flight) were added to
  the workbook's yearly formulas after the Total column formula was last updated, so the Total column
  still misses exactly those 4 flights. `Fiescheralp` (1 flight) was never assigned to any region
  anywhere in the sheet at all — genuinely unmapped, not a bug; can now be fixed on the live data via
  the `/sites` drawer's region field if the pilot wants it under "Fiesch".
- **Row 387's altitude-gain mismatch** is the sheet's own recorded gain (350m) disagreeing with its own
  `max_alt − launch_elev` columns (1930 − 1930 = 0) for that one row — a pre-existing data quirk,
  reported and left alone.

**Version chain: 0.3.0 → 0.3.1 → 0.3.2**, each bump because static assets changed again after the
previous one was already live with `pages.py`'s `?v=<version>` cache-busting → `main.py`'s
`Cache-Control: immutable` for versioned assets. Note this mechanism only covers `src=`/`href=`
attributes in server-rendered HTML — the Leaflet marker-icon paths (bug 1) are plain strings *inside*
`sites.js`, never touched by that rewriting; `sites.js` itself is what's versioned, and that's enough,
since the fix lives in `sites.js`'s own content.

**Known, local-only test failure — not caused by this session's changes, does not affect prod:**
`test_app_version_matches_pyproject` fails in *this* dev venv because
`flightlog-0.2.1.dist-info` (leftover from an earlier plain `poetry install`, before `--no-root` was
adopted) sits in the venv's `site-packages` and shadows the `pyproject.toml` fallback via
`importlib.metadata`. Confirmed absent from the repo tree; the container's `poetry install --no-root`
never creates it, so a fresh deploy resolves `APP_VERSION` correctly. 126/127 otherwise passing,
`ruff` clean.

## Next Step

1. **Redeploy `fl.sdh.lol` with `0.3.2`** — the only remaining step for bug 1.
2. **Real browser pass on `/sites`** the moment the Claude in Chrome extension connects (it didn't
   connect this session — see [[env-no-browser-extension]]; still worth a retry each session, since the
   pilot has been actively troubleshooting their own login for it). Specifically check the drawer/picker
   interaction and the narrow-screen case (the drawer is full-width below 640px, so the map sits
   entirely behind it there and the manual lat/lon fields are the only usable path) — still nobody has
   actually seen this render, only reasoned about it from CSS and from the pilot's own console logs.
3. **Two small live-data fixes, now possible through the drawer, still pilot's call:** assign
   `Fiescheralp` to the `Fiesch` region (or leave it — the sheet itself never did either), and decide
   whether to add "Advance Success 2" under `/equipment` and reattach it to its 3 flights.
4. **Decide on Phases 9–11** (`/contacts`, CSV export, remember-last-filters) before or after tagging
   a `v0.4.0` — unchanged from before, still open.

## Open Questions

- Whether Phases 9–11 ship before or after `v0.4.0` — see step 4 above.
- The three items already in `features.md`'s backlog from v0.2 (unchanged this session): grant the
  deploy `gh` token `read:packages`, re-run the `python:3.14-slim` build gate once `libigc` lands in
  v0.4, and the `bootstrap_admin_email`/`bootstrap_admin_password` `set=%s`-style logging gap.

## Context

- **v0.3's spec/plan/research/data-model/contracts/tasks live in `specs/002-flight-log-ui/`.**
- **The dev server needs a restart after every backend edit** (no `--reload`); irrelevant this session
  since only static files and `pyproject.toml` changed, but still true for the next backend change.
  See [[flightlog-dev-server-workflow]].
- **One real XSS bug was caught and fixed two sessions ago** (Leaflet `bindTooltip(string)` on free-text
  `site.name` → `innerHTML`); the fix (`textContent` DOM node) is preserved unchanged through the
  `sites.js` rewrite.
- **`database/db.py`'s `_seed_regions()` and `core/aliases.py`'s `SITE_REGION` must use identical region
  spelling** — a mismatch silently creates an orphaned duplicate region row on the next write, not an
  error. This bit the project once already (`Därstetten`/`Dürstetten`, `7345d28`/`e4ae0b8`). Not touched
  this session, but worth remembering before editing either file.

This file is a pointer, not a duplicate — `.ai/context/features.md`, `architecture.md` and
`specs/002-flight-log-ui/` have the detail.
