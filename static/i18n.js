/**
 * Minimal i18n. Loads a locale JSON, exposes window.t(), applies data-i18n attributes.
 *
 * SUPPORTED holds one locale today. The machinery is wired anyway because retrofitting
 * hardcoded strings later is the expensive half — adding a locale is one entry here plus
 * a JSON file.
 *
 * User data is NOT translated. Site names, flight categories, glider names and comments
 * are German source data and are rendered verbatim in every locale. Only chrome has keys.
 */

export const SUPPORTED = ['en'];
export const DEFAULT_LOCALE = 'en';

const STORAGE_KEY = 'fl.locale';

let translations = {};
let currentLocale = DEFAULT_LOCALE;

function resolveLocale() {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored && SUPPORTED.includes(stored)) return stored;

  const browser = (navigator.language || DEFAULT_LOCALE).slice(0, 2);
  return SUPPORTED.includes(browser) ? browser : DEFAULT_LOCALE;
}

/** Resolve a dotted key path against the loaded translations. */
function lookup(key) {
  return key.split('.').reduce((acc, part) => (acc == null ? undefined : acc[part]), translations);
}

/**
 * Translate a key. Falls back to the key itself so a missing string is visible in the UI
 * rather than rendering as empty.
 */
export function t(key, vars) {
  let value = lookup(key);
  if (typeof value !== 'string') {
    console.warn(`[FL:i18n] missing key: ${key}`);
    return key;
  }
  if (vars) {
    for (const [name, val] of Object.entries(vars)) {
      value = value.replaceAll(`{${name}}`, String(val));
    }
  }
  return value;
}

export function applyDataI18n(root = document) {
  let count = 0;

  root.querySelectorAll('[data-i18n]').forEach((el) => {
    el.textContent = t(el.getAttribute('data-i18n'));
    count += 1;
  });

  root.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
    el.setAttribute('placeholder', t(el.getAttribute('data-i18n-placeholder')));
    count += 1;
  });

  root.querySelectorAll('[data-i18n-title]').forEach((el) => {
    el.setAttribute('title', t(el.getAttribute('data-i18n-title')));
    count += 1;
  });

  console.log(`[FL:i18n] applied ${count} translations (${currentLocale})`);
}

export async function initI18n() {
  currentLocale = resolveLocale();
  const started = performance.now();

  try {
    const res = await fetch(`/static/i18n/${currentLocale}.json`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    translations = await res.json();
    console.log(
      `[FL:i18n] loaded ${currentLocale} in ${(performance.now() - started).toFixed(0)}ms`,
    );
  } catch (err) {
    console.error(`[FL:i18n] failed to load locale ${currentLocale}`, err);
    translations = {};
  }

  window.t = t;
  document.documentElement.lang = currentLocale;
  applyDataI18n();
  return currentLocale;
}

export function renderLangPicker(mount) {
  if (!mount) return;

  // With a single supported locale a picker is noise. The mount point stays in the
  // markup so adding a locale needs no HTML change.
  if (SUPPORTED.length < 2) {
    mount.style.display = 'none';
    return;
  }

  const select = document.createElement('select');
  select.setAttribute('aria-label', 'Language');
  for (const loc of SUPPORTED) {
    const opt = document.createElement('option');
    opt.value = loc;
    opt.textContent = loc.toUpperCase();
    opt.selected = loc === currentLocale;
    select.appendChild(opt);
  }
  select.addEventListener('change', () => {
    console.log(`[FL:i18n] locale changed to ${select.value}`);
    localStorage.setItem(STORAGE_KEY, select.value);
    window.location.reload();
  });

  mount.replaceChildren(select);
}
