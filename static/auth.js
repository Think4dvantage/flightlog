/**
 * Token storage and authenticated fetch.
 *
 * fetchAuth() attaches the bearer token, transparently refreshes once on a 401, and
 * redirects to /login when the refresh also fails. Every authenticated call in the app
 * goes through it — never call fetch() directly with an Authorization header.
 */

const ACCESS_KEY = 'fl.access_token';
const REFRESH_KEY = 'fl.refresh_token';

export function getAccessToken() {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY);
}

export function storeTokens({ access_token, refresh_token }) {
  localStorage.setItem(ACCESS_KEY, access_token);
  localStorage.setItem(REFRESH_KEY, refresh_token);
  console.log('[FL:auth] tokens stored');
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  console.log('[FL:auth] tokens cleared');
}

export function isLoggedIn() {
  return Boolean(getAccessToken());
}

/** Extract the envelope's message, falling back to something readable. */
export async function errorMessage(response) {
  try {
    const body = await response.json();
    return body?.error?.message || `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

async function refreshTokens() {
  const refresh_token = getRefreshToken();
  if (!refresh_token) return false;

  console.log('[FL:auth] access token rejected, attempting refresh');
  const res = await fetch('/api/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token }),
  });

  if (!res.ok) {
    console.warn(`[FL:auth] refresh failed (${res.status})`);
    return false;
  }

  storeTokens(await res.json());
  return true;
}

export async function fetchAuth(url, options = {}, _retried = false) {
  const started = performance.now();
  const headers = new Headers(options.headers || {});

  const token = getAccessToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  // FormData (multipart file uploads) must never get an explicit Content-Type — the browser
  // sets one itself with the boundary it actually used to encode the body. Setting our own
  // (or defaulting to JSON) breaks every multipart request silently.
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(url, { ...options, headers });
  const elapsed = (performance.now() - started).toFixed(0);
  console.log(`[FL:auth] ${options.method || 'GET'} ${url} → ${response.status} (${elapsed}ms)`);

  if (response.status === 401 && !_retried) {
    if (await refreshTokens()) {
      return fetchAuth(url, options, true);
    }
    clearTokens();
    console.warn('[FL:auth] session expired, redirecting to /login');
    window.location.href = '/login';
  }

  return response;
}

export async function loadCurrentUser() {
  if (!isLoggedIn()) return null;
  const res = await fetchAuth('/api/auth/me');
  if (!res.ok) return null;
  return res.json();
}

export function logout() {
  clearTokens();
  window.location.href = '/login';
}
