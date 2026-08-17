/**
 * /public/profiles/{user_id} — anonymous-visitor view of a pilot's public flights (v0.9).
 * bootstrapPage is called with `anonymous: true` — see public-flight.js's docstring for why
 * that matters, not just `requireAuth: false`. A disabled or nonexistent profile both 404
 * identically — see api/routers/public.py.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { errorMessage } from '/static/auth.js';

const el = (id) => document.getElementById(id);

function profileIdFromUrl() {
  const parts = window.location.pathname.split('/').filter(Boolean);
  return parts[parts.length - 1];
}

function notRecorded() {
  return window.t('public_profile.not_recorded');
}

function fmtDate(iso) {
  const d = new Date(`${iso}T00:00:00Z`);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
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

async function loadProfile(id) {
  const started = performance.now();
  const res = await fetch(`/api/public/profiles/${id}`);
  console.log(`[FL:public-profile] GET /api/public/profiles/${id} → ${res.status} (${(performance.now() - started).toFixed(0)}ms)`);
  if (!res.ok) {
    el('alert').textContent = await errorMessage(res);
    el('alert').classList.add('visible');
    return null;
  }
  return res.json();
}

function render(profile) {
  // display_name is user data — textContent only, never innerHTML.
  el('p_name').textContent = profile.display_name;
  el('p_count').textContent = window.t('public_profile.flight_count', { count: profile.flights.length });

  const statsLink = el('p_stats_link');
  if (profile.public_stats_enabled) {
    statsLink.hidden = false;
    statsLink.textContent = '';
    const a = document.createElement('a');
    a.href = `/public/stats/${profile.user_id}`;
    a.textContent = window.t('public_profile.view_stats', { name: profile.display_name });
    statsLink.appendChild(a);
  } else {
    statsLink.hidden = true;
  }

  const tbody = el('flightsBody');
  tbody.innerHTML = '';
  for (const flight of profile.flights) {
    const tr = document.createElement('tr');

    const dateTd = document.createElement('td');
    const link = document.createElement('a');
    link.href = `/public/flights/${flight.id}`;
    link.textContent = fmtDate(flight.flight_date);
    dateTd.appendChild(link);
    tr.appendChild(dateTd);

    // flight.nickname is free-text user data — textContent only, never innerHTML.
    const nicknameTd = document.createElement('td');
    nicknameTd.textContent = flight.nickname || notRecorded();
    tr.appendChild(nicknameTd);

    const launchTd = document.createElement('td');
    launchTd.textContent = flight.launch_site_name || notRecorded();
    tr.appendChild(launchTd);

    const categoryTd = document.createElement('td');
    categoryTd.textContent = flight.category_name || notRecorded();
    tr.appendChild(categoryTd);

    const durationTd = document.createElement('td');
    durationTd.textContent = fmtDuration(flight.duration_min);
    tr.appendChild(durationTd);

    const distanceTd = document.createElement('td');
    distanceTd.textContent = fmtNumber(flight.distance_km, 'km');
    tr.appendChild(distanceTd);

    const altTd = document.createElement('td');
    altTd.textContent = fmtNumber(flight.max_alt_m, 'm');
    tr.appendChild(altTd);

    tbody.appendChild(tr);
  }

  el('emptyState').hidden = profile.flights.length > 0;
  el('flightsTable').hidden = profile.flights.length === 0;
  el('profileBody').hidden = false;
}

async function init() {
  await bootstrapPage({ page: 'public-profile', anonymous: true });

  const id = profileIdFromUrl();
  console.log(`[FL:public-profile] loading profile ${id}`);
  const profile = await loadProfile(id);
  if (!profile) return;
  render(profile);
}

init();
