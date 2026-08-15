/**
 * /tandem-flights — imported and pilot-created tandem flights, full CRUD (added post-ship
 * per direct pilot feedback). cost=0 is a real, meaningful value (a free flight-school
 * tandem) — rendered as "0", never as "not recorded". Follows goals.js's drawer pattern.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';

const el = (id) => document.getElementById(id);

let tandems = [];
let editingId = null;

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

function render() {
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

    const actionTd = document.createElement('td');
    const editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.className = 'btn-ghost';
    editBtn.textContent = window.t('tandem_flights.edit');
    editBtn.addEventListener('click', () => openDrawer(t));
    actionTd.appendChild(editBtn);
    tr.appendChild(actionTd);

    tbody.appendChild(tr);
  }

  el('emptyState').hidden = tandems.length > 0;
  el('tandemTable').hidden = tandems.length === 0;
  el('resultCount').textContent = window.t('tandem_flights.result_count', { count: tandems.length });
}

function clearFieldErrors() {
  document.querySelectorAll('#tandemForm .field-error').forEach((p) => (p.textContent = ''));
  el('drawerAlert').classList.remove('visible');
}

function openDrawer(t) {
  editingId = t?.id || null;
  clearFieldErrors();
  el('deleteConfirm').hidden = true;

  el('drawerTitle').textContent = window.t(
    t ? 'tandem_flights.drawer.edit_title' : 'tandem_flights.drawer.add_title',
  );
  el('drawerDelete').hidden = !t;

  el('t_id').value = t?.id || '';
  el('t_date').value = t?.flight_date || '';
  el('t_launch').value = t?.launch_place || '';
  el('t_landing').value = t?.landing_place || '';
  el('t_operator').value = t?.tandem_operator || '';
  el('t_cost').value = t?.cost ?? '';
  el('t_comment').value = t?.comment || '';

  el('drawerOverlay').hidden = false;
  el('tandemDrawer').hidden = false;
  el('tandemDrawer').setAttribute('aria-hidden', 'false');
  console.log(`[FL:tandem-flights] drawer opened (${t ? 'edit ' + t.id : 'add'})`);
  el('t_date').focus();
}

function closeDrawer() {
  el('drawerOverlay').hidden = true;
  el('tandemDrawer').hidden = true;
  el('tandemDrawer').setAttribute('aria-hidden', 'true');
  editingId = null;
  console.log('[FL:tandem-flights] drawer closed');
}

function readFormPayload() {
  return {
    flight_date: el('t_date').value,
    launch_place: el('t_launch').value.trim(),
    landing_place: el('t_landing').value.trim(),
    tandem_operator: el('t_operator').value.trim() || null,
    cost: el('t_cost').value === '' ? null : Number(el('t_cost').value),
    comment: el('t_comment').value.trim() || null,
  };
}

function renderFieldErrors(details) {
  const errors = details?.errors || [];
  for (const err of errors) {
    const field = err.loc?.[err.loc.length - 1];
    const target = document.querySelector(`#tandemForm .field-error[data-field="${field}"]`);
    if (target) target.textContent = err.msg;
    console.warn(`[FL:tandem-flights] validation error on ${field}: ${err.msg}`);
  }
  if (errors.length === 0) {
    el('drawerAlert').textContent = window.t('common.error_generic');
    el('drawerAlert').classList.add('visible');
  }
}

async function submitTandem(event) {
  event.preventDefault();
  clearFieldErrors();
  const saveBtn = el('drawerSave');
  saveBtn.disabled = true;

  const payload = readFormPayload();
  const url = editingId ? `/api/tandem-flights/${editingId}` : '/api/tandem-flights';
  const method = editingId ? 'PUT' : 'POST';
  console.log(`[FL:tandem-flights] ${method} ${url}`, payload);

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
      console.error(`[FL:tandem-flights] save failed (${res.status})`);
      return;
    }

    tandems = await loadTandemFlights();
    render();
    closeDrawer();
    console.log(`[FL:tandem-flights] tandem flight ${editingId ? 'updated' : 'created'}`);
  } finally {
    saveBtn.disabled = false;
  }
}

async function deleteTandem() {
  if (!editingId) return;
  const id = editingId;
  const res = await fetchAuth(`/api/tandem-flights/${id}`, { method: 'DELETE' });
  if (!res.ok) {
    el('drawerAlert').textContent = await errorMessage(res);
    el('drawerAlert').classList.add('visible');
    console.error(`[FL:tandem-flights] delete failed (${res.status})`);
    return;
  }
  tandems = tandems.filter((t) => t.id !== id);
  render();
  closeDrawer();
  console.log(`[FL:tandem-flights] tandem flight deleted: ${id}`);
}

function wireEvents() {
  el('addTandemBtn').addEventListener('click', () => openDrawer(null));
  el('drawerClose').addEventListener('click', closeDrawer);
  el('drawerOverlay').addEventListener('click', closeDrawer);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !el('tandemDrawer').hidden) closeDrawer();
  });

  el('tandemForm').addEventListener('submit', submitTandem);

  el('drawerDelete').addEventListener('click', () => {
    el('deleteConfirm').hidden = false;
  });
  el('deleteConfirmNo').addEventListener('click', () => {
    el('deleteConfirm').hidden = true;
  });
  el('deleteConfirmYes').addEventListener('click', deleteTandem);
}

async function init() {
  await bootstrapPage({ page: 'tandem-flights', requireAuth: true });
  wireEvents();
  tandems = await loadTandemFlights();
  render();
}

init();
