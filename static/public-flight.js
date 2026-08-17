/**
 * /public/flights/{id} — anonymous-visitor view of a single unlisted-or-public flight
 * (v0.9). Deliberately built without any assumption of a logged-in session: bootstrapPage
 * is called with `anonymous: true`, which skips the token check entirely — a visitor's own
 * (possibly stale) localStorage token must never trigger a redirect-to-/login on this page,
 * and a visitor who is logged in as some other pilot in this browser must never see that
 * identity surfaced here (FR-013). A private or nonexistent flight both 404 identically —
 * see api/routers/public.py.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { errorMessage } from '/static/auth.js';

const el = (id) => document.getElementById(id);

function flightIdFromUrl() {
  const parts = window.location.pathname.split('/').filter(Boolean);
  return parts[parts.length - 1];
}

function notRecorded() {
  return window.t('public_flight.not_recorded');
}

function fmtDate(iso) {
  const d = new Date(`${iso}T00:00:00Z`);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
}

function fmtDuration(min) {
  if (min == null) return notRecorded();
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h > 0 ? `${h}h ${String(m).padStart(2, '0')}min` : `${m} min`;
}

function fmtNumber(value, unit) {
  return value == null ? notRecorded() : `${value} ${unit}`;
}

async function loadFlight(id) {
  const started = performance.now();
  const res = await fetch(`/api/public/flights/${id}`);
  console.log(`[FL:public-flight] GET /api/public/flights/${id} → ${res.status} (${(performance.now() - started).toFixed(0)}ms)`);
  if (!res.ok) {
    el('alert').textContent = await errorMessage(res);
    el('alert').classList.add('visible');
    return null;
  }
  return res.json();
}

function render(flight) {
  // nickname / owner_display_name / site / category names are user data — textContent only,
  // never innerHTML.
  el('d_date').textContent = flight.nickname
    ? `${flight.nickname} — ${fmtDate(flight.flight_date)}`
    : fmtDate(flight.flight_date);
  el('d_owner').textContent = window.t('public_flight.shared_by', { name: flight.owner_display_name });

  el('d_launch').textContent = flight.launch_site_name || notRecorded();
  el('d_landing').textContent = flight.landing_site_name || notRecorded();
  el('d_category').textContent = flight.category_name || notRecorded();

  el('d_duration').textContent = fmtDuration(flight.duration_min);
  el('d_distance').textContent = fmtNumber(flight.distance_km, 'km');
  el('d_maxalt').textContent = fmtNumber(flight.max_alt_m, 'm');
  el('d_altgain').textContent = fmtNumber(flight.alt_gain_m, 'm');
  el('d_totaldescent').textContent = fmtNumber(flight.total_descent_m, 'm');

  el('d_technique').textContent = flight.launch_technique
    ? window.t(`public_flight.technique_${flight.launch_technique}`)
    : notRecorded();

  el('d_notes').textContent = flight.notes || notRecorded();

  const profileLink = el('d_profile_link');
  if (flight.owner_has_public_profile) {
    profileLink.hidden = false;
    profileLink.textContent = '';
    const a = document.createElement('a');
    a.href = `/public/profiles/${flight.owner_id}`;
    a.textContent = window.t('public_flight.view_profile', { name: flight.owner_display_name });
    profileLink.appendChild(a);
  } else {
    profileLink.hidden = true;
  }

  el('detailBody').hidden = false;
}

async function init() {
  await bootstrapPage({ page: 'public-flight', anonymous: true });

  const id = flightIdFromUrl();
  console.log(`[FL:public-flight] loading flight ${id}`);
  const flight = await loadFlight(id);
  if (!flight) return;
  render(flight);
}

init();
