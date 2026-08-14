# Resume Notes — 2026-08-14

## In Progress

**v0.3.0 (`4a536ff`) is live at `fl.sdh.lol`** — confirmed by the pilot browsing it directly. This
session started from two live bug reports plus a "the import findings don't make sense" complaint,
and ends with a `/sites` redesign and explanatory copy on `/import`, both **implemented on `main` but
not committed, tagged, or deployed yet.**

**Bug 1 — map pin icon not rendering on click-to-place.** Root cause **not confirmed**: no browser
tool was connected this session either (see [[env-no-browser-extension]]), and `fl.sdh.lol` sits
behind Traefik OIDC — every unauthenticated `curl` against it, including static assets, came back
`401 application/json+problem`, so it couldn't be reproduced directly. Best evidence-backed hypothesis,
not verified: the OIDC session cookie not covering a freshly-requested image the same way it covers the
already-loaded page. The old `/sites` code itself (icon paths, CSP, static mount, vendored PNGs) checked
out clean locally — a marker-icon PUT/GET round-trip and a raw static-file fetch both worked against a
local dev boot. **First thing to do with real browser access: DevTools → Network → filter
`marker-icon` → read the actual status code.**

**Bug 2 — no way to re-edit a site once pinned.** Confirmed real and fixed by redesign, independent of
bug 1. The old page only let a row's click arm map-placement for a site with *no* coordinates yet;
a site that already had a pin could only be moved by finding and dragging its (possibly not-rendering)
marker — spec.md's own FR-009/FR-010 line ("editing a site's name or elevation does not require
re-placing its pin") implies a proper edit path that was never built.

**Fix: `/sites` now has an Edit button per row opening a drawer** (name, launch/landing flags, region,
elevation, coordinates — all editable together, same drawer pattern as `/flights` and `/equipment`).
Coordinates have two independent paths, so bug 1 (whatever it turns out to be) can't block editing
entirely: a "click the map to set the pin" picker, and manual lat/lon text fields (deliberately
`type="text"`, not `type="number"` — a browser set to a comma-decimal locale silently reports `""` for
`"46,4"` typed into a number input, which would have quietly unpinned the site on save; the text fields
accept either separator and parse it themselves). One drawer bug caught and fixed before commit: the
drawer's own overlay is a fixed, full-viewport layer above the map — left as-is, the first map click
while picking would have hit the overlay and closed the drawer instead of placing the pin. `armPicker()`
now hides the overlay for the duration of the pick.

**The "import findings don't make sense" complaint needed no code fix, only explanation.** Every
mismatch on `/import` was already correctly root-caused in a *previous* session
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
  the new `/sites` drawer's region field if the pilot wants it under "Fiesch".
- **Row 387's altitude-gain mismatch** is the sheet's own recorded gain (350m) disagreeing with its own
  `max_alt − launch_elev` columns (1930 − 1930 = 0) for that one row — a pre-existing data quirk,
  reported and left alone.

The only change made: short explanatory `<p>`s were added under each `/import` findings section
(`import.*_note` i18n keys) so the pilot sees this reasoning in-app instead of only in dev docs.

**Version bumped 0.3.0 → 0.3.1.** `pages.py` rewrites every `/static/...` reference to `?v=<version>`
at render time, and `main.py` serves anything with a `v=` query as cache-`immutable`
(`max-age=31536000`) — since 0.3.0 is already live and the pilot has already loaded it once, shipping
these fixes under the same version string would leave a returning browser pinned to the old, buggy
`sites.js` forever.

**Known, local-only test failure — not caused by this session's changes, does not affect prod:**
`test_app_version_matches_pyproject` fails in *this* dev venv because
`flightlog-0.2.1.dist-info` (leftover from an earlier plain `poetry install`, before `--no-root` was
adopted) sits in the venv's `site-packages` and shadows the `pyproject.toml` fallback via
`importlib.metadata`. Confirmed absent from the repo tree; the container's `poetry install --no-root`
never creates it, so a fresh deploy resolves `APP_VERSION` correctly. 126/127 otherwise passing,
`ruff` clean.

**Nothing from this session is committed yet** — same as last time, but true this time; `git status`
will show the diff (`sites.html`, `sites.js`, `import.html`, `i18n/en.json`, `pyproject.toml`).

## Next Step

1. **Review and commit this session's work.**
2. **Real browser pass on `/sites`** the moment a browser tool is available — the overlay/picker
   interaction and the narrow-screen case (the drawer is full-width below 640px, so the map sits
   entirely behind it there and the manual lat/lon fields are the only usable path) were only verified
   by reading `shared.css`'s z-index rules, never rendered. This is still T047's job, now with more
   surface area to check than before.
3. **Get the actual marker-icon DevTools status code** from the pilot next time bug 1 reproduces, to
   turn the OIDC hypothesis above into a confirmed root cause (or rule it out).
4. **Redeploy `fl.sdh.lol`** with `0.3.1` once the above is done.
5. **Two small live-data fixes, now possible through the new drawer, still pilot's call:** assign
   `Fiescheralp` to the `Fiesch` region (or leave it — the sheet itself never did either), and decide
   whether to add "Advance Success 2" under `/equipment` and reattach it to its 3 flights.
6. **Decide on Phases 9–11** (`/contacts`, CSV export, remember-last-filters) before or after tagging
   `v0.3.0`/`0.3.1` proper — unchanged from before, still open.

## Open Questions

- Whether Phases 9–11 ship with `v0.3.0` or as a fast-follow — see step 6 above.
- The three items already in `features.md`'s backlog from v0.2 (unchanged this session): grant the
  deploy `gh` token `read:packages`, re-run the `python:3.14-slim` build gate once `libigc` lands in
  v0.4, and the `bootstrap_admin_email`/`bootstrap_admin_password` `set=%s`-style logging gap.

## Context

- **v0.3's spec/plan/research/data-model/contracts/tasks live in `specs/002-flight-log-ui/`.**
- **The dev server needs a restart after every backend edit** (no `--reload`); irrelevant this session
  since only static files and `pyproject.toml` changed, but still true for the next backend change.
  See [[flightlog-dev-server-workflow]].
- **One real XSS bug was caught and fixed last session** (Leaflet `bindTooltip(string)` on free-text
  `site.name` → `innerHTML`); the fix (`textContent` DOM node) is preserved unchanged in this session's
  `sites.js` rewrite.
- **`database/db.py`'s `_seed_regions()` and `core/aliases.py`'s `SITE_REGION` must use identical region
  spelling** — a mismatch silently creates an orphaned duplicate region row on the next write, not an
  error. This bit the project once already (`Därstetten`/`Dürstetten`, `7345d28`/`e4ae0b8`). Not touched
  this session, but worth remembering before editing either file.

This file is a pointer, not a duplicate — `.ai/context/features.md`, `architecture.md` and
`specs/002-flight-log-ui/` have the detail.
