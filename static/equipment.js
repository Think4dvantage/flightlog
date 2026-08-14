/**
 * /equipment — gliders and harnesses: create, edit, retire. Retired gear stays visible
 * (styled distinct) but is excluded from new-flight defaults — see flights.js's drawer.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';

const el = (id) => document.getElementById(id);

let gliders = [];
let harnesses = [];
let editingKind = null;
let editingId = null;

function showAlert(message) {
  el('alert').textContent = message;
  el('alert').classList.add('visible');
  console.error(`[FL:equipment] ${message}`);
}

async function loadAll() {
  const started = performance.now();
  const [gRes, hRes] = await Promise.all([
    fetchAuth('/api/gliders?include_retired=true'),
    fetchAuth('/api/harnesses?include_retired=true'),
  ]);
  if (!gRes.ok || !hRes.ok) {
    showAlert(window.t('common.error_generic'));
    return;
  }
  gliders = await gRes.json();
  harnesses = await hRes.json();
  console.log(
    `[FL:equipment] loaded ${gliders.length} gliders, ${harnesses.length} harnesses in ${(performance.now() - started).toFixed(0)}ms`,
  );
}

function renderGliders() {
  const tbody = el('glidersBody');
  tbody.innerHTML = '';
  for (const g of gliders) {
    const tr = document.createElement('tr');
    if (g.retired_at) tr.classList.add('retired');

    const nameTd = document.createElement('td');
    nameTd.textContent = g.nickname ? `${g.nickname} (${g.brand} ${g.model})` : `${g.brand} ${g.model}`;
    tr.appendChild(nameTd);

    const sizeTd = document.createElement('td');
    sizeTd.textContent = g.size || '—';
    tr.appendChild(sizeTd);

    const enTd = document.createElement('td');
    enTd.textContent = g.en_class || '—';
    tr.appendChild(enTd);

    const statusTd = document.createElement('td');
    statusTd.textContent = g.retired_at
      ? window.t('equipment.status_retired')
      : window.t('equipment.status_active');
    tr.appendChild(statusTd);

    const actionTd = document.createElement('td');
    const editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.className = 'btn-ghost';
    editBtn.textContent = window.t('equipment.edit');
    editBtn.addEventListener('click', () => openDrawer('glider', g));
    actionTd.appendChild(editBtn);
    tr.appendChild(actionTd);

    tbody.appendChild(tr);
  }
}

function renderHarnesses() {
  const tbody = el('harnessesBody');
  tbody.innerHTML = '';
  for (const h of harnesses) {
    const tr = document.createElement('tr');
    if (h.retired_at) tr.classList.add('retired');

    const nameTd = document.createElement('td');
    nameTd.textContent = `${h.brand} ${h.model}`;
    tr.appendChild(nameTd);

    const sizeTd = document.createElement('td');
    sizeTd.textContent = h.size || '—';
    tr.appendChild(sizeTd);

    const typeTd = document.createElement('td');
    typeTd.textContent = h.harness_type || '—';
    tr.appendChild(typeTd);

    const statusTd = document.createElement('td');
    statusTd.textContent = h.retired_at
      ? window.t('equipment.status_retired')
      : window.t('equipment.status_active');
    tr.appendChild(statusTd);

    const actionTd = document.createElement('td');
    const editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.className = 'btn-ghost';
    editBtn.textContent = window.t('equipment.edit');
    editBtn.addEventListener('click', () => openDrawer('harness', h));
    actionTd.appendChild(editBtn);
    tr.appendChild(actionTd);

    tbody.appendChild(tr);
  }
}

function clearFieldErrors() {
  document.querySelectorAll('#itemForm .field-error').forEach((p) => (p.textContent = ''));
  el('drawerAlert').classList.remove('visible');
}

function openDrawer(kind, item) {
  editingKind = kind;
  editingId = item?.id || null;
  clearFieldErrors();

  el('gliderFields').hidden = kind !== 'glider';
  el('harnessFields').hidden = kind !== 'harness';

  const titleKey = item
    ? kind === 'glider'
      ? 'equipment.drawer.edit_glider_title'
      : 'equipment.drawer.edit_harness_title'
    : kind === 'glider'
      ? 'equipment.drawer.add_glider_title'
      : 'equipment.drawer.add_harness_title';
  el('drawerTitle').textContent = window.t(titleKey);

  el('i_id').value = item?.id || '';
  el('i_kind').value = kind;
  el('i_brand').value = item?.brand || '';
  el('i_model').value = item?.model || '';
  el('i_size').value = item?.size || '';
  el('i_nickname').value = item?.nickname || '';
  el('i_enclass').value = item?.en_class || '';
  el('i_type').value = item?.harness_type || '';

  el('drawerRetire').hidden = !item || Boolean(item.retired_at);

  el('drawerOverlay').hidden = false;
  el('itemDrawer').hidden = false;
  el('itemDrawer').setAttribute('aria-hidden', 'false');
  console.log(`[FL:equipment] drawer opened (${kind}, ${item ? 'edit ' + item.id : 'add'})`);
  el('i_brand').focus();
}

function closeDrawer() {
  el('drawerOverlay').hidden = true;
  el('itemDrawer').hidden = true;
  el('itemDrawer').setAttribute('aria-hidden', 'true');
  editingKind = null;
  editingId = null;
}

function endpointFor(kind) {
  return kind === 'glider' ? '/api/gliders' : '/api/harnesses';
}

function readPayload(kind) {
  const base = {
    brand: el('i_brand').value.trim(),
    model: el('i_model').value.trim(),
    size: el('i_size').value.trim() || null,
  };
  if (kind === 'glider') {
    return { ...base, nickname: el('i_nickname').value.trim() || null, en_class: el('i_enclass').value.trim() || null };
  }
  return { ...base, harness_type: el('i_type').value.trim() || null };
}

function renderFieldErrors(details) {
  const errors = details?.errors || [];
  for (const err of errors) {
    const field = err.loc?.[err.loc.length - 1];
    const target = document.querySelector(`#itemForm .field-error[data-field="${field}"]`);
    if (target) target.textContent = err.msg;
    console.warn(`[FL:equipment] validation error on ${field}: ${err.msg}`);
  }
  if (errors.length === 0) {
    el('drawerAlert').textContent = window.t('common.error_generic');
    el('drawerAlert').classList.add('visible');
  }
}

async function submitItem(event) {
  event.preventDefault();
  clearFieldErrors();
  const kind = el('i_kind').value;
  const payload = readPayload(kind);
  const url = editingId ? `${endpointFor(kind)}/${editingId}` : endpointFor(kind);
  const method = editingId ? 'PUT' : 'POST';
  console.log(`[FL:equipment] ${method} ${url}`, payload);

  const res = await fetchAuth(url, { method, body: JSON.stringify(payload) });
  if (!res.ok) {
    let details = null;
    try {
      details = (await res.json())?.error?.details;
    } catch {
      /* no body */
    }
    if (res.status === 422 && details) {
      renderFieldErrors(details);
    } else {
      el('drawerAlert').textContent = await errorMessage(res);
      el('drawerAlert').classList.add('visible');
    }
    console.error(`[FL:equipment] save failed (${res.status})`);
    return;
  }

  await loadAll();
  renderGliders();
  renderHarnesses();
  closeDrawer();
  console.log(`[FL:equipment] ${kind} ${editingId ? 'updated' : 'created'}`);
}

async function retireItem() {
  if (!editingKind || !editingId) return;
  const url = `${endpointFor(editingKind)}/${editingId}/retire`;
  console.log(`[FL:equipment] POST ${url}`);
  const res = await fetchAuth(url, { method: 'POST' });
  if (!res.ok) {
    el('drawerAlert').textContent = await errorMessage(res);
    el('drawerAlert').classList.add('visible');
    console.error(`[FL:equipment] retire failed (${res.status})`);
    return;
  }
  await loadAll();
  renderGliders();
  renderHarnesses();
  closeDrawer();
  console.log(`[FL:equipment] ${editingKind} retired: ${editingId}`);
}

function wireEvents() {
  el('addGliderBtn').addEventListener('click', () => openDrawer('glider', null));
  el('addHarnessBtn').addEventListener('click', () => openDrawer('harness', null));
  el('drawerClose').addEventListener('click', closeDrawer);
  el('drawerOverlay').addEventListener('click', closeDrawer);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !el('itemDrawer').hidden) closeDrawer();
  });
  el('itemForm').addEventListener('submit', submitItem);
  el('drawerRetire').addEventListener('click', retireItem);
}

async function init() {
  await bootstrapPage({ page: 'equipment', requireAuth: true });
  wireEvents();
  await loadAll();
  renderGliders();
  renderHarnesses();
}

init();
