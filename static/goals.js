/**
 * /goals — imported from the Ziele sheet, the one secondary-sheet type that stays fully
 * editable afterward (specs/004-secondary-sheets-xcontest). Full CRUD + status filter +
 * mark-done, following equipment.js's add/edit drawer pattern.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';

const el = (id) => document.getElementById(id);

let goals = [];
let editingId = null;

function showAlert(message) {
  el('alert').textContent = message;
  el('alert').classList.add('visible');
  console.error(`[FL:goals] ${message}`);
}

async function loadGoals() {
  const status = el('filterStatus').value;
  const url = status ? `/api/goals?status=${encodeURIComponent(status)}` : '/api/goals';
  const started = performance.now();
  const res = await fetchAuth(url);
  if (!res.ok) {
    showAlert(await errorMessage(res));
    return [];
  }
  const list = await res.json();
  console.log(`[FL:goals] loaded ${list.length} goals in ${(performance.now() - started).toFixed(0)}ms`);
  return list;
}

function render() {
  const tbody = el('goalsBody');
  tbody.innerHTML = '';

  for (const goal of goals) {
    const tr = document.createElement('tr');
    if (goal.status === 'done') tr.classList.add('retired'); // reuse the muted-row style

    const titleTd = document.createElement('td');
    titleTd.textContent = goal.title;
    tr.appendChild(titleTd);

    const categoryTd = document.createElement('td');
    categoryTd.textContent = goal.category || '—';
    tr.appendChild(categoryTd);

    const difficultyTd = document.createElement('td');
    difficultyTd.textContent = goal.difficulty || '—';
    tr.appendChild(difficultyTd);

    const windTd = document.createElement('td');
    windTd.textContent = goal.wind_direction || '—';
    tr.appendChild(windTd);

    const seasonTd = document.createElement('td');
    seasonTd.textContent = goal.target_season || '—';
    tr.appendChild(seasonTd);

    const statusTd = document.createElement('td');
    statusTd.textContent =
      goal.status === 'done' ? window.t('goals.status_done') : window.t('goals.status_open');
    tr.appendChild(statusTd);

    const actionTd = document.createElement('td');
    const editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.className = 'btn-ghost';
    editBtn.textContent = window.t('goals.edit');
    editBtn.addEventListener('click', () => openDrawer(goal));
    actionTd.appendChild(editBtn);
    tr.appendChild(actionTd);

    tbody.appendChild(tr);
  }

  el('emptyState').hidden = goals.length > 0;
  el('goalsTable').hidden = goals.length === 0;
  el('resultCount').textContent = window.t('goals.result_count', { count: goals.length });
}

function clearFieldErrors() {
  document.querySelectorAll('#goalForm .field-error').forEach((p) => (p.textContent = ''));
  el('drawerAlert').classList.remove('visible');
}

function openDrawer(goal) {
  editingId = goal?.id || null;
  clearFieldErrors();
  el('deleteConfirm').hidden = true;

  el('drawerTitle').textContent = window.t(goal ? 'goals.drawer.edit_title' : 'goals.drawer.add_title');
  el('drawerDelete').hidden = !goal;
  el('drawerMarkDone').hidden = !goal || goal.status === 'done';

  el('g_id').value = goal?.id || '';
  el('g_title').value = goal?.title || '';
  el('g_category').value = goal?.category || '';
  el('g_difficulty').value = goal?.difficulty || '';
  el('g_wind').value = goal?.wind_direction || '';
  el('g_season').value = goal?.target_season || '';
  el('g_description').value = goal?.description || '';
  el('g_links').value = goal?.links || '';

  el('drawerOverlay').hidden = false;
  el('goalDrawer').hidden = false;
  el('goalDrawer').setAttribute('aria-hidden', 'false');
  console.log(`[FL:goals] drawer opened (${goal ? 'edit ' + goal.id : 'add'})`);
  el('g_title').focus();
}

function closeDrawer() {
  el('drawerOverlay').hidden = true;
  el('goalDrawer').hidden = true;
  el('goalDrawer').setAttribute('aria-hidden', 'true');
  editingId = null;
  console.log('[FL:goals] drawer closed');
}

function readFormPayload() {
  return {
    title: el('g_title').value.trim(),
    category: el('g_category').value.trim() || null,
    difficulty: el('g_difficulty').value.trim() || null,
    wind_direction: el('g_wind').value.trim() || null,
    target_season: el('g_season').value.trim() || null,
    description: el('g_description').value.trim() || null,
    links: el('g_links').value.trim() || null,
  };
}

function renderFieldErrors(details) {
  const errors = details?.errors || [];
  for (const err of errors) {
    const field = err.loc?.[err.loc.length - 1];
    const target = document.querySelector(`#goalForm .field-error[data-field="${field}"]`);
    if (target) target.textContent = err.msg;
    console.warn(`[FL:goals] validation error on ${field}: ${err.msg}`);
  }
  if (errors.length === 0) {
    el('drawerAlert').textContent = window.t('common.error_generic');
    el('drawerAlert').classList.add('visible');
  }
}

async function submitGoal(event) {
  event.preventDefault();
  clearFieldErrors();
  const saveBtn = el('drawerSave');
  saveBtn.disabled = true;

  const payload = readFormPayload();
  const url = editingId ? `/api/goals/${editingId}` : '/api/goals';
  const method = editingId ? 'PUT' : 'POST';
  console.log(`[FL:goals] ${method} ${url}`, payload);

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
      console.error(`[FL:goals] save failed (${res.status})`);
      return;
    }

    goals = await loadGoals();
    render();
    closeDrawer();
    console.log(`[FL:goals] goal ${editingId ? 'updated' : 'created'}`);
  } finally {
    saveBtn.disabled = false;
  }
}

async function markDone() {
  if (!editingId) return;
  const res = await fetchAuth(`/api/goals/${editingId}/mark-done`, { method: 'POST' });
  if (!res.ok) {
    el('drawerAlert').textContent = await errorMessage(res);
    el('drawerAlert').classList.add('visible');
    console.error(`[FL:goals] mark-done failed (${res.status})`);
    return;
  }
  goals = await loadGoals();
  render();
  closeDrawer();
  console.log(`[FL:goals] goal marked done: ${editingId}`);
}

async function deleteGoal() {
  if (!editingId) return;
  const id = editingId;
  const res = await fetchAuth(`/api/goals/${id}`, { method: 'DELETE' });
  if (!res.ok) {
    el('drawerAlert').textContent = await errorMessage(res);
    el('drawerAlert').classList.add('visible');
    console.error(`[FL:goals] delete failed (${res.status})`);
    return;
  }
  goals = goals.filter((g) => g.id !== id);
  render();
  closeDrawer();
  console.log(`[FL:goals] goal deleted: ${id}`);
}

function wireEvents() {
  el('addGoalBtn').addEventListener('click', () => openDrawer(null));
  el('drawerClose').addEventListener('click', closeDrawer);
  el('drawerOverlay').addEventListener('click', closeDrawer);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !el('goalDrawer').hidden) closeDrawer();
  });

  el('goalForm').addEventListener('submit', submitGoal);
  el('drawerMarkDone').addEventListener('click', markDone);

  el('drawerDelete').addEventListener('click', () => {
    el('deleteConfirm').hidden = false;
  });
  el('deleteConfirmNo').addEventListener('click', () => {
    el('deleteConfirm').hidden = true;
  });
  el('deleteConfirmYes').addEventListener('click', deleteGoal);

  el('filterStatus').addEventListener('change', async () => {
    goals = await loadGoals();
    render();
  });
}

async function init() {
  await bootstrapPage({ page: 'goals', requireAuth: true });
  wireEvents();
  goals = await loadGoals();
  render();
}

init();
