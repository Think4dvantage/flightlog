/**
 * /hikes — imported (Fitnessprogramm sheet) and pilot-created hikes, full CRUD (added
 * post-ship per direct pilot feedback — "I can't add new ones"). A hike that became a
 * flight (import-time unambiguous match, or a manual link set here) shows a link to that
 * flight's detail page. Follows goals.js's add/edit drawer pattern.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';
import { loadRefData, siteName } from '/static/refdata.js';

const el = (id) => document.getElementById(id);

let hikes = [];
let flights = [];
let editingId = null;

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

async function loadFlights() {
  const res = await fetchAuth('/api/flights');
  if (!res.ok) {
    console.error(`[FL:hikes] failed to load flights for the link dropdown (${res.status})`);
    return [];
  }
  const list = await res.json();
  console.log(`[FL:hikes] loaded ${list.length} flights for the link dropdown`);
  return list;
}

function fmtNumber(value, unit) {
  return value == null ? '—' : `${value} ${unit}`;
}

function populateFlightDropdown() {
  const select = el('h_flight');
  const placeholder = select.querySelector('option[value=""]');
  select.innerHTML = '';
  select.appendChild(placeholder);

  const sorted = [...flights].sort((a, b) => (a.flight_date < b.flight_date ? 1 : -1));
  for (const f of sorted) {
    const opt = document.createElement('option');
    opt.value = f.id;
    opt.textContent = `${f.flight_date} — ${siteName(f.launch_site_id) || '?'}`;
    select.appendChild(opt);
  }
}

function render() {
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

    const actionTd = document.createElement('td');
    const editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.className = 'btn-ghost';
    editBtn.textContent = window.t('hikes.edit');
    editBtn.addEventListener('click', () => openDrawer(hike));
    actionTd.appendChild(editBtn);
    tr.appendChild(actionTd);

    tbody.appendChild(tr);
  }

  el('emptyState').hidden = hikes.length > 0;
  el('hikesTable').hidden = hikes.length === 0;
  el('resultCount').textContent = window.t('hikes.result_count', { count: hikes.length });
}

function clearFieldErrors() {
  document.querySelectorAll('#hikeForm .field-error').forEach((p) => (p.textContent = ''));
  el('drawerAlert').classList.remove('visible');
}

function openDrawer(hike) {
  editingId = hike?.id || null;
  clearFieldErrors();
  el('deleteConfirm').hidden = true;
  populateFlightDropdown();

  el('drawerTitle').textContent = window.t(hike ? 'hikes.drawer.edit_title' : 'hikes.drawer.add_title');
  el('drawerDelete').hidden = !hike;

  el('h_id').value = hike?.id || '';
  el('h_date').value = hike?.hike_date || '';
  el('h_start').value = hike?.start_place || '';
  el('h_destination').value = hike?.destination_place || '';
  el('h_ascent').value = hike?.ascent_m ?? '';
  el('h_descent').value = hike?.descent_m ?? '';
  el('h_distance').value = hike?.distance_km ?? '';
  el('h_duration').value = hike?.duration_min ?? '';
  el('h_route_description').value = hike?.route_description || '';
  el('h_flight').value = hike?.flight_id || '';

  el('drawerOverlay').hidden = false;
  el('hikeDrawer').hidden = false;
  el('hikeDrawer').setAttribute('aria-hidden', 'false');
  console.log(`[FL:hikes] drawer opened (${hike ? 'edit ' + hike.id : 'add'})`);
  el('h_date').focus();
}

function closeDrawer() {
  el('drawerOverlay').hidden = true;
  el('hikeDrawer').hidden = true;
  el('hikeDrawer').setAttribute('aria-hidden', 'true');
  editingId = null;
  console.log('[FL:hikes] drawer closed');
}

function readFormPayload() {
  return {
    hike_date: el('h_date').value,
    start_place: el('h_start').value.trim(),
    destination_place: el('h_destination').value.trim(),
    ascent_m: el('h_ascent').value === '' ? null : Number(el('h_ascent').value),
    descent_m: el('h_descent').value === '' ? null : Number(el('h_descent').value),
    distance_km: el('h_distance').value === '' ? null : Number(el('h_distance').value),
    duration_min: el('h_duration').value === '' ? null : Number(el('h_duration').value),
    route_description: el('h_route_description').value.trim() || null,
    flight_id: el('h_flight').value || null,
  };
}

function renderFieldErrors(details) {
  const errors = details?.errors || [];
  for (const err of errors) {
    const field = err.loc?.[err.loc.length - 1];
    const target = document.querySelector(`#hikeForm .field-error[data-field="${field}"]`);
    if (target) target.textContent = err.msg;
    console.warn(`[FL:hikes] validation error on ${field}: ${err.msg}`);
  }
  if (errors.length === 0) {
    el('drawerAlert').textContent = window.t('common.error_generic');
    el('drawerAlert').classList.add('visible');
  }
}

async function submitHike(event) {
  event.preventDefault();
  clearFieldErrors();
  const saveBtn = el('drawerSave');
  saveBtn.disabled = true;

  const payload = readFormPayload();
  const url = editingId ? `/api/hikes/${editingId}` : '/api/hikes';
  const method = editingId ? 'PUT' : 'POST';
  console.log(`[FL:hikes] ${method} ${url}`, payload);

  try {
    const res = await fetchAuth(url, { method, body: JSON.stringify(payload) });
    if (!res.ok) {
      let details;
      try {
        details = (await res.json())?.error?.details;
      } catch {
        details = null;
      }
      if (res.status === 422 && details) {
        renderFieldErrors(details);
      } else {
        el('drawerAlert').textContent = await errorMessage(res);
        el('drawerAlert').classList.add('visible');
      }
      console.error(`[FL:hikes] save failed (${res.status})`);
      return;
    }

    hikes = await loadHikes();
    render();
    closeDrawer();
    console.log(`[FL:hikes] hike ${editingId ? 'updated' : 'created'}`);
  } finally {
    saveBtn.disabled = false;
  }
}

async function deleteHike() {
  if (!editingId) return;
  const id = editingId;
  const res = await fetchAuth(`/api/hikes/${id}`, { method: 'DELETE' });
  if (!res.ok) {
    el('drawerAlert').textContent = await errorMessage(res);
    el('drawerAlert').classList.add('visible');
    console.error(`[FL:hikes] delete failed (${res.status})`);
    return;
  }
  hikes = hikes.filter((h) => h.id !== id);
  render();
  closeDrawer();
  console.log(`[FL:hikes] hike deleted: ${id}`);
}

function wireEvents() {
  el('addHikeBtn').addEventListener('click', () => openDrawer(null));
  el('drawerClose').addEventListener('click', closeDrawer);
  el('drawerOverlay').addEventListener('click', closeDrawer);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !el('hikeDrawer').hidden) closeDrawer();
  });

  el('hikeForm').addEventListener('submit', submitHike);

  el('drawerDelete').addEventListener('click', () => {
    el('deleteConfirm').hidden = false;
  });
  el('deleteConfirmNo').addEventListener('click', () => {
    el('deleteConfirm').hidden = true;
  });
  el('deleteConfirmYes').addEventListener('click', deleteHike);
}

async function init() {
  await bootstrapPage({ page: 'hikes', requireAuth: true });
  await loadRefData();
  wireEvents();
  [hikes, flights] = await Promise.all([loadHikes(), loadFlights()]);
  render();
}

init();
