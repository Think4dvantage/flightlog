# Frontend Conventions

## No Build Step

Changes to `static/` are live immediately in dev (volume-mounted). **Never introduce npm, webpack, vite,
rollup, parcel or any bundler. No `package.json`.** The frontend is intentionally dependency-free.

---

## No CDN — this is enforced by the browser, not by preference

Leaflet and Chart.js are **self-hosted** under `static/vendor/`. The app sends
`Content-Security-Policy: script-src 'self'`, so a CDN `<script src="https://...">` is **blocked by the
browser**, not merely discouraged. A page that references one silently renders without its map or chart.

To add a library: download the release into `static/vendor/<lib>/`, reference it by absolute
`/static/vendor/...` path, and mark the directory `-text` in `.gitattributes` so the bytes stay exact.

Verify the vendored version is the current stable release before committing it — see the dependency
freshness rule in `02-backend-conventions.md`. Vendored libraries are dependencies too.

---

## Static Asset Caching & Cache-Busting

Cache-busting is server-side: `pages.py` rewrites asset references to `?v=<app-version>` where the
version comes from `pyproject.toml`.

| Request | Cache-Control |
|---|---|
| `/static/x.css?v=0.3.1` | `public, max-age=31536000, immutable` |
| `/static/x.css` | `public, max-age=600` |
| `*.html` | `no-cache` + ETag → 304 |

**A deploy therefore requires a version bump in `pyproject.toml` — the version *is* the cache key.**
Ship a static change without bumping it and returning users keep the old file for up to a year.

---

## Internationalisation (i18n)

`SUPPORTED = ['en']`. The machinery is fully wired so adding a locale is one line plus a JSON file;
retrofitting hardcoded strings later is the expensive half.

Every user-visible string must have a key in **every configured locale** simultaneously. `en.json` is
the source of truth.

### German source data is data, not UI — never translate it

Site names (`Höhenmatte`, `Amisbühl`), flight categories (`Abgleiter`, `Thermikflug`, `Hike&Fly`),
glider and harness names, hike routes and flight comments are **user data**. They are stored and
displayed verbatim in every locale. Only chrome — labels, buttons, nav, headings, validation messages —
is translated.

This distinction is easy to get wrong when adding a locale. A "Launch site" label is a key; `Schiltgrat`
is not.

### HTML

```html
<span data-i18n="nav.flights">Flights</span>
<input data-i18n-placeholder="auth.email_placeholder">
<div id="navLangPicker"></div>   <!-- required mount point on every page -->
```

### JavaScript

```javascript
// In module scripts, after await bootstrapPage()/initI18n():
el.textContent = window.t('flights.count', { count: 5 });

// In non-module scripts that may run before initI18n() resolves:
const t = typeof window.t === 'function' ? window.t : k => k;

// Config objects must be built lazily, post-init — not at module load time:
function getColumnLabels() {
  return { date: window.t('flights.col.date'), duration: window.t('flights.col.duration') };
}
```

---

## Module Scripts & Bootstrap

Each page has exactly **one** `<script type="module">` block. Large pages (`flights`,
`flight-detail`) put their logic in a companion `.js` file that the module block imports.

```javascript
import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth } from '/static/auth.js';
await bootstrapPage({ page: 'flights' });
```

`bootstrapPage()` renders the nav, runs `initI18n()`, renders auth state and the language picker.
`shared.css` owns **all** nav CSS — never duplicate nav styling in a page `<style>` block.

**An unauthenticated-by-design page (v0.9: `public-flight.js`, `public-profile.js`) must pass
`anonymous: true`, not just `requireAuth: false`:**

```javascript
await bootstrapPage({ page: 'public-flight', anonymous: true });
```

`requireAuth: false` alone still lets the nav-rendering path call `loadCurrentUser()` →
`fetchAuth('/api/auth/me')` whenever `localStorage` holds a token, and a stale token's failed refresh
redirects to `/login` — wrong on a page a stranger with zero session must be able to load. `anonymous:
true` skips the token check and the authenticated nav links entirely, regardless of what a visitor's
browser happens to hold. See `04-constraints.md`'s Security section for the full rationale.

---

## Dark Theme

| Token | Value |
|---|---|
| Body background | `#0f1117` |
| Cards / nav | `#1a1f2e` |
| Borders | `#2d3748` |
| Primary text | `#e2e8f0` |
| Accent | `#90cdf4` |

---

## Authentication

Use `fetchAuth()` from `auth.js` for every authenticated call. It attaches the bearer token,
auto-refreshes on expiry and redirects to `/login` when the refresh fails.

---

## XSS — Rules That Must Not Be Broken

**Never assign untrusted data to `innerHTML`, `outerHTML` or `document.write()`.** Flight comments are
free text up to ~3300 characters, written by the user and — once sharing ships — readable by others.
They are the highest-risk strings in the app.

```javascript
// WRONG
cell.innerHTML = flight.comment;

// RIGHT
cell.textContent = flight.comment;
```

Where markup genuinely is required, pipe it through a per-page `sanitizeHTML()` allowlist.

URLs are equally untrusted: any user-supplied URL (e.g. `flight_links.url`, v0.8) must have its `http(s)`
scheme validated **server-side in the Pydantic model** (see `04-constraints.md`) before it's ever
interpolated into an `href` — `javascript:` and `data:` URLs are the attack.

---

## Browser Console Logging Policy

**Log verbosely.** It must be possible to diagnose any frontend behaviour from the console alone.

### Mandatory rule: add logging whenever you touch code

**Any time you modify a frontend function or block — even for an unrelated fix — check whether it has
console logging. If it does not, add it before moving on.** Logging is not scope creep.

| Event type | Level | What to include |
|---|---|---|
| Data fetches | `console.log` | URL, `performance.now()` start, result size, elapsed ms |
| Cache hits / misses | `console.log` | Key, cache age in seconds |
| State transitions | `console.log` | Old → new, payload summary |
| User interactions | `console.log` | Action name, resolved parameters |
| Warnings / empty results | `console.warn` | Expected vs received |
| Errors | `console.error` | Full error object + context |

### Prefix convention

Every `console.*` starts with a bracketed prefix derived from the HTML filename:

```
[FL:flights]        flights.html
[FL:flight-detail]  flight-detail.html
[FL:sites]          sites.html
[FL:auth]           login.html / register.html
[FL:<page>]         derive from the filename
```

### Throttling

Guard verbose output inside timers and animation loops:

```javascript
if (idx % 25 === 0) console.log(`[FL:flights] rendered ${idx}/${total} rows`);
```

---

## Page Layout Pattern

One `.html` per page, plus a companion `.js` when the page is large. One HTML + script per domain.
