/**
 * /hikes — read-only list of imported hikes (Fitnessprogramm sheet). Import-and-view only —
 * no add/edit/delete (specs/004-secondary-sheets-xcontest spec.md's Out of Scope). A hike that
 * became a flight (source Airtime/Landeplatz present, unambiguous same-date match) links to
 * that flight's detail page.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';

const el = (id) => document.getElementById(id);

function showAlert(message) {
  el('alert').textContent = message;
  el('alert').classList.add('visible');
  console.error(`[FL:hikes] ${message}`);
}

async function loadHikes() {
  const started = performance.now();
  const res = await fetchAuth('/api/hikes');
  if (!res.ok) {
    showAlert(await errorMessage(res));
    return [];
  }
  const list = await res.json();
  console.log(`[FL:hikes] loaded ${list.length} hikes in ${(performance.now() - started).toFixed(0)}ms`);
  return list;
}

function fmtNumber(value, unit) {
  return value == null ? '—' : `${value} ${unit}`;
}

function render(hikes) {
  const tbody = el('hikesBody');
  tbody.innerHTML = '';

  for (const hike of hikes) {
    const tr = document.createElement('tr');

    const dateTd = document.createElement('td');
    dateTd.textContent = hike.hike_date;
    tr.appendChild(dateTd);

    const routeTd = document.createElement('td');
    routeTd.textContent = `${hike.start_place} → ${hike.destination_place}`;
    tr.appendChild(routeTd);

    const ascentTd = document.createElement('td');
    ascentTd.textContent = fmtNumber(hike.ascent_m, 'm');
    tr.appendChild(ascentTd);

    const descentTd = document.createElement('td');
    descentTd.textContent = fmtNumber(hike.descent_m, 'm');
    tr.appendChild(descentTd);

    const distanceTd = document.createElement('td');
    distanceTd.textContent = fmtNumber(hike.distance_km, 'km');
    tr.appendChild(distanceTd);

    const durationTd = document.createElement('td');
    durationTd.textContent = fmtNumber(hike.duration_min, 'min');
    tr.appendChild(durationTd);

    const flightTd = document.createElement('td');
    if (hike.flight_id) {
      const a = document.createElement('a');
      a.href = `/flights/${hike.flight_id}`;
      a.textContent = window.t('hikes.view_flight');
      flightTd.appendChild(a);
    } else {
      flightTd.textContent = '—';
    }
    tr.appendChild(flightTd);

    tbody.appendChild(tr);
  }

  el('emptyState').hidden = hikes.length > 0;
  el('hikesTable').hidden = hikes.length === 0;
  el('resultCount').textContent = window.t('hikes.result_count', { count: hikes.length });
}

async function init() {
  await bootstrapPage({ page: 'hikes', requireAuth: true });
  const hikes = await loadHikes();
  render(hikes);
}

init();
