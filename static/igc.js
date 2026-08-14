/**
 * /igc — bulk IGC upload plus the pending-review queue for anything that didn't
 * auto-attach (specs/003-igc-ingest-analysis). See 03-frontend-conventions.md for the
 * logging/i18n/XSS rules this follows.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';
import { loadRefData, siteName } from '/static/refdata.js';

const el = (id) => document.getElementById(id);

let flightsById = new Map();

function showAlert(message) {
  el('alert').textContent = message;
  el('alert').classList.add('visible');
  console.error(`[FL:igc] ${message}`);
}

function clearAlert() {
  el('alert').classList.remove('visible');
}

function flightLabel(flightId) {
  const flight = flightsById.get(flightId);
  if (!flight) return flightId;
  const launch = siteName(flight.launch_site_id) || '?';
  return `${flight.flight_date} — ${launch}`;
}

async function loadFlights() {
  const res = await fetchAuth('/api/flights');
  if (!res.ok) {
    showAlert(await errorMessage(res));
    return [];
  }
  const list = await res.json();
  flightsById = new Map(list.map((f) => [f.id, f]));
  console.log(`[FL:igc] loaded ${list.length} flights for candidate labels`);
  return list;
}

function outcomeLabel(outcome) {
  return window.t(`igc.outcome.${outcome}`);
}

function renderOutcomes(outcomes) {
  const tbody = el('outcomesBody');
  tbody.innerHTML = '';
  el('outcomesTable').hidden = outcomes.length === 0;
  el('outcomesEmpty').hidden = outcomes.length > 0;

  for (const outcome of outcomes) {
    const tr = document.createElement('tr');

    const fileTd = document.createElement('td');
    fileTd.textContent = outcome.filename;
    tr.appendChild(fileTd);

    const outcomeTd = document.createElement('td');
    outcomeTd.textContent = outcomeLabel(outcome.outcome);
    tr.appendChild(outcomeTd);

    const detailTd = document.createElement('td');
    if (outcome.outcome === 'auto_attached') {
      detailTd.textContent = flightLabel(outcome.flight_id);
    } else {
      detailTd.textContent = outcome.reason || '—';
    }
    tr.appendChild(detailTd);

    tbody.appendChild(tr);
  }
}

async function uploadBulk(files) {
  clearAlert();
  const body = new FormData();
  for (const file of files) body.append('files', file);

  console.log(`[FL:igc] POST /api/igc/bulk (${files.length} files)`);
  const res = await fetchAuth('/api/igc/bulk', { method: 'POST', body });
  if (!res.ok) {
    showAlert(await errorMessage(res));
    return;
  }
  const outcomes = await res.json();
  renderOutcomes(outcomes);
  await loadAndRenderPending();
  console.log(`[FL:igc] bulk upload done: ${outcomes.length} files processed`);
}

async function loadPending() {
  const res = await fetchAuth('/api/igc/pending');
  if (!res.ok) {
    showAlert(await errorMessage(res));
    return [];
  }
  return res.json();
}

async function resolvePending(pendingId, flightId, row) {
  const res = await fetchAuth(`/api/igc/pending/${pendingId}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ flight_id: flightId }),
  });
  if (!res.ok) {
    showAlert(await errorMessage(res));
    return;
  }
  console.log(`[FL:igc] pending upload resolved: ${pendingId} -> flight ${flightId}`);
  row.remove();
  await loadAndRenderPending();
}

async function dismissPending(pendingId, row) {
  const res = await fetchAuth(`/api/igc/pending/${pendingId}`, { method: 'DELETE' });
  if (!res.ok) {
    showAlert(await errorMessage(res));
    return;
  }
  console.log(`[FL:igc] pending upload dismissed: ${pendingId}`);
  row.remove();
  await loadAndRenderPending();
}

function renderPending(rows) {
  const tbody = el('pendingBody');
  tbody.innerHTML = '';
  el('pendingTable').hidden = rows.length === 0;
  el('pendingEmpty').hidden = rows.length > 0;

  for (const row of rows) {
    const tr = document.createElement('tr');

    const fileTd = document.createElement('td');
    fileTd.textContent = row.original_filename;
    tr.appendChild(fileTd);

    const statusTd = document.createElement('td');
    statusTd.textContent = row.reason || row.status;
    tr.appendChild(statusTd);

    const candidateTd = document.createElement('td');
    let select = null;
    if (row.candidate_flight_ids && row.candidate_flight_ids.length > 0) {
      select = document.createElement('select');
      for (const flightId of row.candidate_flight_ids) {
        const opt = document.createElement('option');
        opt.value = flightId;
        opt.textContent = flightLabel(flightId);
        select.appendChild(opt);
      }
      candidateTd.appendChild(select);
    } else {
      candidateTd.textContent = '—';
    }
    tr.appendChild(candidateTd);

    const actionTd = document.createElement('td');
    if (select) {
      const resolveBtn = document.createElement('button');
      resolveBtn.type = 'button';
      resolveBtn.textContent = window.t('igc.resolve');
      resolveBtn.addEventListener('click', () => resolvePending(row.id, select.value, tr));
      actionTd.appendChild(resolveBtn);
    }
    const dismissBtn = document.createElement('button');
    dismissBtn.type = 'button';
    dismissBtn.className = 'btn-ghost';
    dismissBtn.textContent = window.t('igc.dismiss');
    dismissBtn.addEventListener('click', () => dismissPending(row.id, tr));
    actionTd.appendChild(dismissBtn);
    tr.appendChild(actionTd);

    tbody.appendChild(tr);
  }
}

async function loadAndRenderPending() {
  const rows = await loadPending();
  renderPending(rows);
}

function wireEvents() {
  el('bulkUploadBtn').addEventListener('click', () => {
    const files = el('bulkFiles').files;
    if (!files || files.length === 0) {
      showAlert(window.t('igc.no_files'));
      return;
    }
    uploadBulk(files);
  });
}

async function init() {
  await bootstrapPage({ page: 'igc', requireAuth: true });
  await loadRefData();
  await loadFlights();
  wireEvents();
  renderOutcomes([]);
  await loadAndRenderPending();
}

init();
