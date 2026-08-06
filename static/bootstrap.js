/**
 * Per-page bootstrap: nav, i18n, auth state, language picker.
 *
 * Every page calls bootstrapPage({ page: '<name>' }) from its single module script.
 * The nav markup lives here so shared.css can own all nav styling — see
 * .ai/instructions/03-frontend-conventions.md.
 */

import { initI18n, renderLangPicker } from '/static/i18n.js';
import { isLoggedIn, loadCurrentUser, logout } from '/static/auth.js';

const NAV_LINKS = [
  { page: 'flights', href: '/flights', key: 'nav.flights' },
  { page: 'sites', href: '/sites', key: 'nav.sites' },
  { page: 'equipment', href: '/equipment', key: 'nav.equipment' },
  { page: 'stats', href: '/stats', key: 'nav.stats' },
];

export function renderNav(mount, activePage) {
  if (!mount) return;

  const nav = document.createElement('nav');
  nav.className = 'nav';

  const brand = document.createElement('a');
  brand.className = 'nav-brand';
  brand.href = '/';
  brand.textContent = 'Flightlog';
  nav.appendChild(brand);

  const links = document.createElement('div');
  links.className = 'nav-links';
  if (isLoggedIn()) {
    for (const link of NAV_LINKS) {
      const a = document.createElement('a');
      a.href = link.href;
      a.setAttribute('data-i18n', link.key);
      a.textContent = link.key;
      if (link.page === activePage) a.classList.add('active');
      links.appendChild(a);
    }
  }
  nav.appendChild(links);

  const right = document.createElement('div');
  right.className = 'nav-right';
  right.id = 'navAuth';

  const picker = document.createElement('div');
  picker.id = 'navLangPicker';
  right.appendChild(picker);

  nav.appendChild(right);
  mount.replaceChildren(nav);
}

async function renderNavAuth() {
  const mount = document.getElementById('navAuth');
  if (!mount) return;

  // Keep the language picker; replace only the auth controls around it.
  const existing = mount.querySelector('#navLangPicker');
  const controls = document.createElement('span');
  controls.className = 'nav-auth-controls';

  if (isLoggedIn()) {
    const user = await loadCurrentUser();
    if (user) {
      const name = document.createElement('span');
      name.className = 'muted';
      // Display name is user data — never translated.
      name.textContent = user.display_name;
      controls.appendChild(name);

      const out = document.createElement('button');
      out.className = 'btn-ghost';
      out.setAttribute('data-i18n', 'nav.logout');
      out.textContent = 'Log out';
      out.addEventListener('click', () => {
        console.log('[FL:nav] logout clicked');
        logout();
      });
      controls.appendChild(out);
    }
  } else {
    const login = document.createElement('a');
    login.href = '/login';
    login.setAttribute('data-i18n', 'nav.login');
    login.textContent = 'Log in';
    controls.appendChild(login);
  }

  mount.replaceChildren(controls, existing || document.createElement('div'));
}

export async function bootstrapPage({ page, requireAuth = false } = {}) {
  console.log(`[FL:${page}] bootstrap start`);

  if (requireAuth && !isLoggedIn()) {
    console.warn(`[FL:${page}] not authenticated, redirecting to /login`);
    window.location.href = '/login';
    return;
  }

  renderNav(document.getElementById('appNav'), page);
  await initI18n();
  await renderNavAuth();
  renderLangPicker(document.getElementById('navLangPicker'));

  console.log(`[FL:${page}] bootstrap complete`);
}
