/**
 * /groundhandling — imported and pilot-created sessions, full CRUD (added post-ship per
 * direct pilot feedback). Follows goals.js's add/edit drawer pattern.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';

const el = (id) => document.getElementById(id);

let sessions = [];
let editingId = null;

function showAlert(message) {
  el('alert').textContent = message;
  el('alert').classList.add('visible');
  console.error(`[FL:groundhandling] ${message}`);
}

async function loadSessions() {
  const started = performance.now();
  const res = await fetchAuth('/api/groundhandling');
  if (!res.ok) {
    showAlert(await errorMessage(res));
    return [];
  }
  const list = await res.json();
  console.log(
    `[FL:groundhandling] loaded ${list.length} sessions in ${(performance.now() - started).toFixed(0)}ms`,
  );
  return list;
}

function render() {
  const tbody = el('sessionsBody');
  tbody.innerHTML = '';

  for (const session of sessions) {
    const tr = document.createElement('tr');

    const dateTd = document.createElement('td');
    dateTd.textContent = session.session_date;
    tr.appendChild(dateTd);

    const placeTd = document.createElement('td');
    placeTd.textContent = session.place;
    tr.appendChild(placeTd);

    const durationTd = document.createElement('td');
    durationTd.textContent = session.duration_min == null ? '—' : `${session.duration_min} min`;
    tr.appendChild(durationTd);

    const commentTd = document.createElement('td');
    commentTd.textContent = session.comment || '—';
    tr.appendChild(commentTd);

    const actionTd = document.createElement('td');
    const editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.className = 'btn-ghost';
    editBtn.textContent = window.t('groundhandling.edit');
    editBtn.addEventListener('click', () => openDrawer(session));
    actionTd.appendChild(editBtn);
    tr.appendChild(actionTd);

    tbody.appendChild(tr);
  }

  el('emptyState').hidden = sessions.length > 0;
  el('sessionsTable').hidden = sessions.length === 0;
  el('resultCount').textContent = window.t('groundhandling.result_count', { count: sessions.length });
}

function clearFieldErrors() {
  document.querySelectorAll('#sessionForm .field-error').forEach((p) => (p.textContent = ''));
  el('drawerAlert').classList.remove('visible');
}

function openDrawer(session) {
  editingId = session?.id || null;
  clearFieldErrors();
  el('deleteConfirm').hidden = true;

  el('drawerTitle').textContent = window.t(
    session ? 'groundhandling.drawer.edit_title' : 'groundhandling.drawer.add_title',
  );
  el('drawerDelete').hidden = !session;

  el('s_id').value = session?.id || '';
  el('s_date').value = session?.session_date || '';
  el('s_place').value = session?.place || '';
  el('s_duration').value = session?.duration_min ?? '';
  el('s_comment').value = session?.comment || '';

  el('drawerOverlay').hidden = false;
  el('sessionDrawer').hidden = false;
  el('sessionDrawer').setAttribute('aria-hidden', 'false');
  console.log(`[FL:groundhandling] drawer opened (${session ? 'edit ' + session.id : 'add'})`);
  el('s_date').focus();
}

function closeDrawer() {
  el('drawerOverlay').hidden = true;
  el('sessionDrawer').hidden = true;
  el('sessionDrawer').setAttribute('aria-hidden', 'true');
  editingId = null;
  console.log('[FL:groundhandling] drawer closed');
}

function readFormPayload() {
  return {
    session_date: el('s_date').value,
    place: el('s_place').value.trim(),
    duration_min: el('s_duration').value === '' ? null : Number(el('s_duration').value),
    comment: el('s_comment').value.trim() || null,
  };
}

function renderFieldErrors(details) {
  const errors = details?.errors || [];
  for (const err of errors) {
    const field = err.loc?.[err.loc.length - 1];
    const target = document.querySelector(`#sessionForm .field-error[data-field="${field}"]`);
    if (target) target.textContent = err.msg;
    console.warn(`[FL:groundhandling] validation error on ${field}: ${err.msg}`);
  }
  if (errors.length === 0) {
    el('drawerAlert').textContent = window.t('common.error_generic');
    el('drawerAlert').classList.add('visible');
  }
}

async function submitSession(event) {
  event.preventDefault();
  clearFieldErrors();
  const saveBtn = el('drawerSave');
  saveBtn.disabled = true;

  const payload = readFormPayload();
  const url = editingId ? `/api/groundhandling/${editingId}` : '/api/groundhandling';
  const method = editingId ? 'PUT' : 'POST';
  console.log(`[FL:groundhandling] ${method} ${url}`, payload);

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
      console.error(`[FL:groundhandling] save failed (${res.status})`);
      return;
    }

    sessions = await loadSessions();
    render();
    closeDrawer();
    console.log(`[FL:groundhandling] session ${editingId ? 'updated' : 'created'}`);
  } finally {
    saveBtn.disabled = false;
  }
}

async function deleteSession() {
  if (!editingId) return;
  const id = editingId;
  const res = await fetchAuth(`/api/groundhandling/${id}`, { method: 'DELETE' });
  if (!res.ok) {
    el('drawerAlert').textContent = await errorMessage(res);
    el('drawerAlert').classList.add('visible');
    console.error(`[FL:groundhandling] delete failed (${res.status})`);
    return;
  }
  sessions = sessions.filter((s) => s.id !== id);
  render();
  closeDrawer();
  console.log(`[FL:groundhandling] session deleted: ${id}`);
}

function wireEvents() {
  el('addSessionBtn').addEventListener('click', () => openDrawer(null));
  el('drawerClose').addEventListener('click', closeDrawer);
  el('drawerOverlay').addEventListener('click', closeDrawer);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !el('sessionDrawer').hidden) closeDrawer();
  });

  el('sessionForm').addEventListener('submit', submitSession);

  el('drawerDelete').addEventListener('click', () => {
    el('deleteConfirm').hidden = false;
  });
  el('deleteConfirmNo').addEventListener('click', () => {
    el('deleteConfirm').hidden = true;
  });
  el('deleteConfirmYes').addEventListener('click', deleteSession);
}

async function init() {
  await bootstrapPage({ page: 'groundhandling', requireAuth: true });
  wireEvents();
  sessions = await loadSessions();
  render();
}

init();
