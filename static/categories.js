/**
 * /categories — CRUD + reorder + archive for the pilot's own flight categories. The backend
 * (`/api/categories`) has been owner-scoped since v0.2; this page closes the one real gap —
 * there was never a UI to manage them, only a seed on registration and a read-only dropdown
 * in the flight form (`refdata.js`).
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';

const el = (id) => document.getElementById(id);

let categories = [];
let editingId = null;
let pendingDelete = null; // category id awaiting the delete-confirm step

function showAlert(message) {
  el('alert').textContent = message;
  el('alert').classList.add('visible');
  console.error(`[FL:categories] ${message}`);
}

async function loadCategories() {
  const started = performance.now();
  const res = await fetchAuth('/api/categories?include_archived=true');
  if (!res.ok) {
    showAlert(await errorMessage(res));
    return [];
  }
  const list = await res.json();
  console.log(
    `[FL:categories] loaded ${list.length} categories in ${(performance.now() - started).toFixed(0)}ms`,
  );
  return list;
}

function flagsText(category) {
  const flags = [];
  if (category.is_hike_fly) flags.push(window.t('categories.drawer.is_hike_fly_label'));
  if (category.is_training) flags.push(window.t('categories.drawer.is_training_label'));
  return flags.length ? flags.join(', ') : '—';
}

function activeCategories() {
  return categories.filter((c) => !c.archived_at);
}

async function persistOrder(orderedIds) {
  console.log('[FL:categories] PUT /api/categories/reorder', orderedIds);
  const res = await fetchAuth('/api/categories/reorder', {
    method: 'PUT',
    body: JSON.stringify({ ids: orderedIds }),
  });
  if (!res.ok) {
    showAlert(await errorMessage(res));
    return false;
  }
  return true;
}

async function moveCategory(categoryId, direction) {
  const active = activeCategories();
  const index = active.findIndex((c) => c.id === categoryId);
  const swapWith = index + direction;
  if (index === -1 || swapWith < 0 || swapWith >= active.length) return;

  [active[index], active[swapWith]] = [active[swapWith], active[index]];
  const orderedIds = active.map((c) => c.id);

  const ok = await persistOrder(orderedIds);
  if (!ok) return;

  categories = await loadCategories();
  render();
  console.log(`[FL:categories] reordered ${categoryId} (${direction > 0 ? 'down' : 'up'})`);
}

function renderRow(category, { active, index, total }) {
  const tr = document.createElement('tr');
  if (!active) tr.classList.add('retired');

  const nameTd = document.createElement('td');
  nameTd.textContent = category.name;
  tr.appendChild(nameTd);

  const flagsTd = document.createElement('td');
  flagsTd.textContent = flagsText(category);
  tr.appendChild(flagsTd);

  const statusTd = document.createElement('td');
  statusTd.textContent = active
    ? window.t('categories.status_active')
    : window.t('categories.status_archived');
  tr.appendChild(statusTd);

  const orderTd = document.createElement('td');
  if (active) {
    const upBtn = document.createElement('button');
    upBtn.type = 'button';
    upBtn.className = 'btn-ghost';
    upBtn.textContent = '▲';
    upBtn.disabled = index === 0;
    upBtn.setAttribute('aria-label', window.t('categories.move_up'));
    upBtn.addEventListener('click', () => moveCategory(category.id, -1));
    orderTd.appendChild(upBtn);

    const downBtn = document.createElement('button');
    downBtn.type = 'button';
    downBtn.className = 'btn-ghost';
    downBtn.textContent = '▼';
    downBtn.disabled = index === total - 1;
    downBtn.setAttribute('aria-label', window.t('categories.move_down'));
    downBtn.addEventListener('click', () => moveCategory(category.id, 1));
    orderTd.appendChild(downBtn);
  } else {
    orderTd.textContent = '—';
  }
  tr.appendChild(orderTd);

  const actionTd = document.createElement('td');
  const editBtn = document.createElement('button');
  editBtn.type = 'button';
  editBtn.className = 'btn-ghost';
  editBtn.textContent = window.t('categories.edit');
  editBtn.addEventListener('click', () => openDrawer(category));
  actionTd.appendChild(editBtn);
  tr.appendChild(actionTd);

  return tr;
}

function render() {
  const tbody = el('categoriesBody');
  tbody.innerHTML = '';

  const active = activeCategories();
  const archived = categories.filter((c) => c.archived_at);

  active.forEach((category, index) => {
    tbody.appendChild(renderRow(category, { active: true, index, total: active.length }));
  });
  archived.forEach((category) => {
    tbody.appendChild(renderRow(category, { active: false, index: 0, total: 0 }));
  });

  el('emptyState').hidden = categories.length > 0;
  el('categoriesTable').hidden = categories.length === 0;
  el('resultCount').textContent = window.t('categories.result_count', { count: categories.length });
}

function clearFieldErrors() {
  document.querySelectorAll('#categoryForm .field-error').forEach((p) => (p.textContent = ''));
  el('drawerAlert').classList.remove('visible');
}

function openDrawer(category) {
  editingId = category?.id || null;
  clearFieldErrors();
  el('archiveConfirm').hidden = true;
  el('deleteConfirm').hidden = true;

  el('drawerTitle').textContent = window.t(
    category ? 'categories.drawer.edit_title' : 'categories.drawer.add_title',
  );

  el('c_id').value = category?.id || '';
  el('c_name').value = category?.name || '';
  el('c_hike_fly').checked = Boolean(category?.is_hike_fly);
  el('c_training').checked = Boolean(category?.is_training);

  el('drawerArchive').hidden = !category || Boolean(category.archived_at);
  el('drawerDelete').hidden = !category;

  el('drawerOverlay').hidden = false;
  el('categoryDrawer').hidden = false;
  el('categoryDrawer').setAttribute('aria-hidden', 'false');
  console.log(`[FL:categories] drawer opened (${category ? 'edit ' + category.id : 'add'})`);
  el('c_name').focus();
}

function closeDrawer() {
  el('drawerOverlay').hidden = true;
  el('categoryDrawer').hidden = true;
  el('categoryDrawer').setAttribute('aria-hidden', 'true');
  editingId = null;
  console.log('[FL:categories] drawer closed');
}

function renderFieldErrors(details) {
  const errors = details?.errors || [];
  for (const err of errors) {
    const field = err.loc?.[err.loc.length - 1];
    const target = document.querySelector(`#categoryForm .field-error[data-field="${field}"]`);
    if (target) target.textContent = err.msg;
    console.warn(`[FL:categories] validation error on ${field}: ${err.msg}`);
  }
  if (errors.length === 0) {
    el('drawerAlert').textContent = window.t('common.error_generic');
    el('drawerAlert').classList.add('visible');
  }
}

async function submitCategory(event) {
  event.preventDefault();
  clearFieldErrors();
  const saveBtn = el('drawerSave');
  saveBtn.disabled = true;

  const payload = {
    name: el('c_name').value.trim(),
    is_hike_fly: el('c_hike_fly').checked,
    is_training: el('c_training').checked,
  };
  const url = editingId ? `/api/categories/${editingId}` : '/api/categories';
  const method = editingId ? 'PUT' : 'POST';
  console.log(`[FL:categories] ${method} ${url}`, payload);

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
      console.error(`[FL:categories] save failed (${res.status})`);
      return;
    }

    categories = await loadCategories();
    render();
    closeDrawer();
    console.log(`[FL:categories] category ${editingId ? 'updated' : 'created'}`);
  } finally {
    saveBtn.disabled = false;
  }
}

async function archiveCategory() {
  if (!editingId) return;
  const res = await fetchAuth(`/api/categories/${editingId}/archive`, { method: 'POST' });
  if (!res.ok) {
    el('drawerAlert').textContent = await errorMessage(res);
    el('drawerAlert').classList.add('visible');
    console.error(`[FL:categories] archive failed (${res.status})`);
    return;
  }
  console.log(`[FL:categories] category archived: ${editingId}`);
  categories = await loadCategories();
  render();
  closeDrawer();
}

async function deleteCategory() {
  if (!pendingDelete) return;
  const id = pendingDelete;
  const res = await fetchAuth(`/api/categories/${id}`, { method: 'DELETE' });
  if (!res.ok) {
    // 409 CONFLICT (still referenced by a flight) surfaces here with the server's own message.
    el('drawerAlert').textContent = await errorMessage(res);
    el('drawerAlert').classList.add('visible');
    el('deleteConfirm').hidden = true;
    console.error(`[FL:categories] delete failed (${res.status})`);
    return;
  }
  console.log(`[FL:categories] category deleted: ${id}`);
  categories = categories.filter((c) => c.id !== id);
  render();
  closeDrawer();
}

function wireEvents() {
  el('addCategoryBtn').addEventListener('click', () => openDrawer(null));
  el('drawerClose').addEventListener('click', closeDrawer);
  el('drawerOverlay').addEventListener('click', closeDrawer);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !el('categoryDrawer').hidden) closeDrawer();
  });

  el('categoryForm').addEventListener('submit', submitCategory);

  el('drawerArchive').addEventListener('click', () => {
    el('archiveConfirm').hidden = false;
  });
  el('archiveConfirmNo').addEventListener('click', () => {
    el('archiveConfirm').hidden = true;
  });
  el('archiveConfirmYes').addEventListener('click', archiveCategory);

  el('drawerDelete').addEventListener('click', () => {
    pendingDelete = editingId;
    el('deleteConfirm').hidden = false;
  });
  el('deleteConfirmNo').addEventListener('click', () => {
    pendingDelete = null;
    el('deleteConfirm').hidden = true;
  });
  el('deleteConfirmYes').addEventListener('click', deleteCategory);
}

async function init() {
  await bootstrapPage({ page: 'categories', requireAuth: true });
  wireEvents();
  categories = await loadCategories();
  render();
}

init();
