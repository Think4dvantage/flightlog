/**
 * /contacts — CRUD for flying buddies (specs/002-flight-log-ui Phase 9, built post-ship per
 * direct pilot feedback). Per-contact flight-tag count is computed client-side from the full
 * flight list, matching Phase 9's own T040 design note.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';

const el = (id) => document.getElementById(id);

let contacts = [];
let flightCounts = new Map();
let editingId = null;

function showAlert(message) {
  el('alert').textContent = message;
  el('alert').classList.add('visible');
  console.error(`[FL:contacts] ${message}`);
}

async function loadContacts() {
  const started = performance.now();
  const res = await fetchAuth('/api/buddies');
  if (!res.ok) {
    showAlert(await errorMessage(res));
    return [];
  }
  const list = await res.json();
  console.log(
    `[FL:contacts] loaded ${list.length} contacts in ${(performance.now() - started).toFixed(0)}ms`,
  );
  return list;
}

async function loadFlightCounts() {
  const started = performance.now();
  const res = await fetchAuth('/api/flights');
  if (!res.ok) {
    console.error(`[FL:contacts] failed to load flights for counts (${res.status})`);
    return new Map();
  }
  const flights = await res.json();
  const counts = new Map();
  for (const f of flights) {
    for (const buddyId of f.buddy_ids || []) {
      counts.set(buddyId, (counts.get(buddyId) || 0) + 1);
    }
  }
  console.log(
    `[FL:contacts] computed flight counts from ${flights.length} flights in ${(performance.now() - started).toFixed(0)}ms`,
  );
  return counts;
}

function render() {
  const tbody = el('contactsBody');
  tbody.innerHTML = '';

  for (const contact of contacts) {
    const tr = document.createElement('tr');

    const nameTd = document.createElement('td');
    nameTd.textContent = contact.display_name;
    tr.appendChild(nameTd);

    const countTd = document.createElement('td');
    countTd.textContent = String(flightCounts.get(contact.id) || 0);
    tr.appendChild(countTd);

    const actionTd = document.createElement('td');
    const editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.className = 'btn-ghost';
    editBtn.textContent = window.t('contacts.edit');
    editBtn.addEventListener('click', () => openDrawer(contact));
    actionTd.appendChild(editBtn);
    tr.appendChild(actionTd);

    tbody.appendChild(tr);
  }

  el('emptyState').hidden = contacts.length > 0;
  el('contactsTable').hidden = contacts.length === 0;
  el('resultCount').textContent = window.t('contacts.result_count', { count: contacts.length });
}

function clearFieldErrors() {
  document.querySelectorAll('#contactForm .field-error').forEach((p) => (p.textContent = ''));
  el('drawerAlert').classList.remove('visible');
}

function openDrawer(contact) {
  editingId = contact?.id || null;
  clearFieldErrors();
  el('deleteConfirm').hidden = true;

  el('drawerTitle').textContent = window.t(
    contact ? 'contacts.drawer.edit_title' : 'contacts.drawer.add_title',
  );
  el('drawerDelete').hidden = !contact;

  el('c_id').value = contact?.id || '';
  el('c_name').value = contact?.display_name || '';

  el('drawerOverlay').hidden = false;
  el('contactDrawer').hidden = false;
  el('contactDrawer').setAttribute('aria-hidden', 'false');
  console.log(`[FL:contacts] drawer opened (${contact ? 'edit ' + contact.id : 'add'})`);
  el('c_name').focus();
}

function closeDrawer() {
  el('drawerOverlay').hidden = true;
  el('contactDrawer').hidden = true;
  el('contactDrawer').setAttribute('aria-hidden', 'true');
  editingId = null;
  console.log('[FL:contacts] drawer closed');
}

function renderFieldErrors(details) {
  const errors = details?.errors || [];
  for (const err of errors) {
    const field = err.loc?.[err.loc.length - 1];
    const target = document.querySelector(`#contactForm .field-error[data-field="${field}"]`);
    if (target) target.textContent = err.msg;
    console.warn(`[FL:contacts] validation error on ${field}: ${err.msg}`);
  }
  if (errors.length === 0) {
    el('drawerAlert').textContent = window.t('common.error_generic');
    el('drawerAlert').classList.add('visible');
  }
}

async function submitContact(event) {
  event.preventDefault();
  clearFieldErrors();
  const saveBtn = el('drawerSave');
  saveBtn.disabled = true;

  const payload = { display_name: el('c_name').value.trim() };
  const url = editingId ? `/api/buddies/${editingId}` : '/api/buddies';
  const method = editingId ? 'PUT' : 'POST';
  console.log(`[FL:contacts] ${method} ${url}`, payload);

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
      console.error(`[FL:contacts] save failed (${res.status})`);
      return;
    }

    contacts = await loadContacts();
    render();
    closeDrawer();
    console.log(`[FL:contacts] contact ${editingId ? 'updated' : 'created'}`);
  } finally {
    saveBtn.disabled = false;
  }
}

async function deleteContact() {
  if (!editingId) return;
  const id = editingId;
  const res = await fetchAuth(`/api/buddies/${id}`, { method: 'DELETE' });
  if (!res.ok) {
    el('drawerAlert').textContent = await errorMessage(res);
    el('drawerAlert').classList.add('visible');
    console.error(`[FL:contacts] delete failed (${res.status})`);
    return;
  }
  contacts = contacts.filter((c) => c.id !== id);
  render();
  closeDrawer();
  console.log(`[FL:contacts] contact deleted: ${id}`);
}

function wireEvents() {
  el('addContactBtn').addEventListener('click', () => openDrawer(null));
  el('drawerClose').addEventListener('click', closeDrawer);
  el('drawerOverlay').addEventListener('click', closeDrawer);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !el('contactDrawer').hidden) closeDrawer();
  });

  el('contactForm').addEventListener('submit', submitContact);

  el('drawerDelete').addEventListener('click', () => {
    el('deleteConfirm').hidden = false;
  });
  el('deleteConfirmNo').addEventListener('click', () => {
    el('deleteConfirm').hidden = true;
  });
  el('deleteConfirmYes').addEventListener('click', deleteContact);
}

async function init() {
  await bootstrapPage({ page: 'contacts', requireAuth: true });
  wireEvents();
  [contacts, flightCounts] = await Promise.all([loadContacts(), loadFlightCounts()]);
  render();
}

init();
