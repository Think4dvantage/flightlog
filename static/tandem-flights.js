/**
 * /tandem-flights — read-only list of imported tandem flights (the pilot as passenger).
 * Import-and-view only. cost=0 is a real, meaningful value (a free flight-school tandem) —
 * rendered as "0", never as "not recorded".
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';

const el = (id) => document.getElementById(id);

function showAlert(message) {
  el('alert').textContent = message;
  el('alert').classList.add('visible');
  console.error(`[FL:tandem-flights] ${message}`);
}

async function loadTandemFlights() {
  const started = performance.now();
  const res = await fetchAuth('/api/tandem-flights');
  if (!res.ok) {
    showAlert(await errorMessage(res));
    return [];
  }
  const list = await res.json();
  console.log(
    `[FL:tandem-flights] loaded ${list.length} tandem flights in ${(performance.now() - started).toFixed(0)}ms`,
  );
  return list;
}

function render(tandems) {
  const tbody = el('tandemBody');
  tbody.innerHTML = '';

  for (const t of tandems) {
    const tr = document.createElement('tr');

    const dateTd = document.createElement('td');
    dateTd.textContent = t.flight_date;
    tr.appendChild(dateTd);

    const launchTd = document.createElement('td');
    launchTd.textContent = t.launch_place;
    tr.appendChild(launchTd);

    const landingTd = document.createElement('td');
    landingTd.textContent = t.landing_place;
    tr.appendChild(landingTd);

    const operatorTd = document.createElement('td');
    operatorTd.textContent = t.tandem_operator || '—';
    tr.appendChild(operatorTd);

    const costTd = document.createElement('td');
    // Deliberately `!= null`, not truthiness — 0 is a real cost (a free tandem), not absent.
    costTd.textContent = t.cost != null ? t.cost : '—';
    tr.appendChild(costTd);

    const commentTd = document.createElement('td');
    commentTd.textContent = t.comment || '—';
    tr.appendChild(commentTd);

    tbody.appendChild(tr);
  }

  el('emptyState').hidden = tandems.length > 0;
  el('tandemTable').hidden = tandems.length === 0;
  el('resultCount').textContent = window.t('tandem_flights.result_count', { count: tandems.length });
}

async function init() {
  await bootstrapPage({ page: 'tandem-flights', requireAuth: true });
  const tandems = await loadTandemFlights();
  render(tandems);
}

init();
