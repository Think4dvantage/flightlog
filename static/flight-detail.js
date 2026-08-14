/**
 * /flights/{id} — read-only detail view. Fresh-load safe: reads the id from the URL path,
 * not from any in-memory list state.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';
import {
  loadRefData,
  siteName,
  gliderName,
  harnessName,
  categoryName,
  getBuddies,
} from '/static/refdata.js';

const el = (id) => document.getElementById(id);

function flightIdFromUrl() {
  const parts = window.location.pathname.split('/').filter(Boolean);
  return parts[parts.length - 1];
}

function notRecorded() {
  return window.t('flight_detail.not_recorded');
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

function linkOrText(mount, name, href) {
  mount.textContent = '';
  if (!name) {
    mount.textContent = notRecorded();
    return;
  }
  const a = document.createElement('a');
  a.href = href;
  a.textContent = name;
  mount.appendChild(a);
}

async function loadFlight(id) {
  const started = performance.now();
  const res = await fetchAuth(`/api/flights/${id}`);
  console.log(`[FL:flight-detail] GET /api/flights/${id} → ${res.status} (${(performance.now() - started).toFixed(0)}ms)`);
  if (!res.ok) {
    el('alert').textContent = await errorMessage(res);
    el('alert').classList.add('visible');
    return null;
  }
  return res.json();
}

function render(flight) {
  el('d_date').textContent = fmtDate(flight.flight_date);

  linkOrText(el('d_launch'), siteName(flight.launch_site_id), '/sites');
  linkOrText(el('d_landing'), siteName(flight.landing_site_id), '/sites');
  el('d_category').textContent = categoryName(flight.category_id) || notRecorded();
  linkOrText(el('d_glider'), gliderName(flight.glider_id), '/equipment');
  linkOrText(el('d_harness'), harnessName(flight.harness_id), '/equipment');

  el('d_duration').textContent = fmtDuration(flight.duration_min);
  el('d_distance').textContent = fmtNumber(flight.distance_km, 'km');
  el('d_maxalt').textContent = fmtNumber(flight.max_alt_m, 'm');
  el('d_altgain').textContent = fmtNumber(flight.alt_gain_m, 'm');
  el('d_sitedrop').textContent = fmtNumber(flight.site_drop_m, 'm');
  el('d_totaldescent').textContent = fmtNumber(flight.total_descent_m, 'm');

  el('d_technique').textContent = flight.launch_technique
    ? window.t(`flight_detail.technique_${flight.launch_technique}`)
    : notRecorded();

  const buddyMap = new Map(getBuddies().map((b) => [b.id, b.display_name]));
  const names = flight.buddy_ids.map((id) => buddyMap.get(id)).filter(Boolean);
  el('d_buddies').textContent = names.length > 0 ? names.join(', ') : notRecorded();

  el('d_notes').textContent = flight.notes || notRecorded();

  el('detailBody').hidden = false;
}

async function init() {
  await bootstrapPage({ page: 'flights', requireAuth: true });
  await loadRefData();

  const id = flightIdFromUrl();
  console.log(`[FL:flight-detail] loading flight ${id}`);
  const flight = await loadFlight(id);
  if (flight) render(flight);
}

init();
