/**
 * /api-keys — pilot-facing API key management (v0.8, specs/006-public-api-vidfactory).
 * Create/list/revoke/delete, plus the one-time plaintext reveal on creation — a genuinely
 * new UI pattern for this app (research.md): once the drawer closes, the value is gone.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';

const el = (id) => document.getElementById(id);

let keys = [];
let pendingAction = null; // { kind: 'revoke' | 'delete', keyId }

function showAlert(message) {
  el('alert').textContent = message;
  el('alert').classList.add('visible');
  console.error(`[FL:api_keys] ${message}`);
}

function fmtDate(iso) {
  if (!iso) return window.t('api_keys.never');
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

function keyStatus(key) {
  if (key.revoked_at) return 'revoked';
  if (key.expires_at && new Date(key.expires_at) < new Date()) return 'expired';
  return 'active';
}

async function loadKeys() {
  const started = performance.now();
  const res = await fetchAuth('/api/keys');
  if (!res.ok) {
    showAlert(await errorMessage(res));
    return [];
  }
  const list = await res.json();
  console.log(`[FL:api_keys] loaded ${list.length} keys in ${(performance.now() - started).toFixed(0)}ms`);
  return list;
}

function render() {
  const tbody = el('keysBody');
  tbody.innerHTML = '';

  for (const key of keys) {
    const status = keyStatus(key);
    const tr = document.createElement('tr');
    if (status !== 'active') tr.classList.add('retired');

    const nameTd = document.createElement('td');
    nameTd.textContent = key.name;
    tr.appendChild(nameTd);

    const scopesTd = document.createElement('td');
    scopesTd.textContent = key.scopes.join(', ');
    tr.appendChild(scopesTd);

    const createdTd = document.createElement('td');
    createdTd.textContent = fmtDate(key.created_at);
    tr.appendChild(createdTd);

    const lastUsedTd = document.createElement('td');
    lastUsedTd.textContent = fmtDate(key.last_used_at);
    tr.appendChild(lastUsedTd);

    const statusTd = document.createElement('td');
    statusTd.textContent = window.t(`api_keys.status_${status}`);
    tr.appendChild(statusTd);

    const actionsTd = document.createElement('td');
    if (status === 'active') {
      const revokeBtn = document.createElement('button');
      revokeBtn.type = 'button';
      revokeBtn.className = 'btn-ghost';
      revokeBtn.textContent = window.t('api_keys.revoke');
      revokeBtn.addEventListener('click', () => openConfirm('revoke', key.id));
      actionsTd.appendChild(revokeBtn);
    } else {
      const deleteBtn = document.createElement('button');
      deleteBtn.type = 'button';
      deleteBtn.className = 'btn-ghost';
      deleteBtn.textContent = window.t('api_keys.delete');
      deleteBtn.addEventListener('click', () => openConfirm('delete', key.id));
      actionsTd.appendChild(deleteBtn);
    }
    tr.appendChild(actionsTd);

    tbody.appendChild(tr);
  }

  el('emptyState').hidden = keys.length > 0;
  el('keysTable').hidden = keys.length === 0;
  el('resultCount').textContent = window.t('api_keys.result_count', { count: keys.length });
}

// ---- create drawer ----

function clearFieldErrors() {
  document.querySelectorAll('#keyForm .field-error').forEach((p) => (p.textContent = ''));
  el('drawerAlert').classList.remove('visible');
}

function openDrawer() {
  clearFieldErrors();
  el('keyForm').hidden = false;
  el('keyReveal').hidden = true;
  el('k_name').value = '';
  el('k_scope_flights_read').checked = false;
  el('k_scope_flight_links_write').checked = false;
  el('k_expiry').value = '';
  el('drawerSave').disabled = false;

  el('drawerOverlay').hidden = false;
  el('keyDrawer').hidden = false;
  el('keyDrawer').setAttribute('aria-hidden', 'false');
  console.log('[FL:api_keys] drawer opened');
  el('k_name').focus();
}

function closeDrawer() {
  el('drawerOverlay').hidden = true;
  el('keyDrawer').hidden = true;
  el('keyDrawer').setAttribute('aria-hidden', 'true');
  console.log('[FL:api_keys] drawer closed');
}

function renderFieldErrors(details) {
  const errors = details?.errors || [];
  for (const err of errors) {
    const field = err.loc?.[err.loc.length - 1];
    const target = document.querySelector(`#keyForm .field-error[data-field="${field}"]`);
    if (target) target.textContent = err.msg;
    console.warn(`[FL:api_keys] validation error on ${field}: ${err.msg}`);
  }
  if (errors.length === 0) {
    el('drawerAlert').textContent = window.t('common.error_generic');
    el('drawerAlert').classList.add('visible');
  }
}

function readScopes() {
  const scopes = [];
  if (el('k_scope_flights_read').checked) scopes.push('flights:read');
  if (el('k_scope_flight_links_write').checked) scopes.push('flight_links:write');
  return scopes;
}

async function submitKey(event) {
  event.preventDefault();
  clearFieldErrors();

  const scopes = readScopes();
  if (scopes.length === 0) {
    document.querySelector('#keyForm .field-error[data-field="scopes"]').textContent =
      window.t('common.error_generic');
    return;
  }

  const payload = {
    name: el('k_name').value.trim(),
    scopes,
    // End of the chosen calendar day, UTC — the date input has no timezone of its own, and
    // an unmarked local time here would silently expire the key hours earlier/later than
    // the pilot picked once UtcDateTime stamps it UTC on write.
    expires_at: el('k_expiry').value ? `${el('k_expiry').value}T23:59:59Z` : null,
  };

  const saveBtn = el('drawerSave');
  saveBtn.disabled = true;
  console.log('[FL:api_keys] POST /api/keys', { ...payload, expires_at: payload.expires_at });

  try {
    const res = await fetchAuth('/api/keys', { method: 'POST', body: JSON.stringify(payload) });
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
      console.error(`[FL:api_keys] create failed (${res.status})`);
      return;
    }

    const created = await res.json();
    console.log(`[FL:api_keys] key created: ${created.id}`);
    keys = await loadKeys();
    render();

    el('keyForm').hidden = true;
    el('revealKeyValue').textContent = created.key;
    el('keyReveal').hidden = false;
  } finally {
    saveBtn.disabled = false;
  }
}

async function copyRevealedKey() {
  const value = el('revealKeyValue').textContent;
  try {
    await navigator.clipboard.writeText(value);
    el('revealCopyBtn').textContent = window.t('api_keys.reveal.copied');
    console.log('[FL:api_keys] key copied to clipboard');
    setTimeout(() => {
      el('revealCopyBtn').textContent = window.t('api_keys.reveal.copy');
    }, 2000);
  } catch (err) {
    console.warn(`[FL:api_keys] clipboard write failed: ${err}`);
  }
}

// ---- revoke / delete confirm drawer ----

function openConfirm(kind, keyId) {
  pendingAction = { kind, keyId };
  el('confirmTitle').textContent = window.t(`api_keys.${kind}`);
  el('confirmPrompt').textContent = window.t(`api_keys.${kind}_confirm.prompt`);
  el('confirmYes').textContent = window.t(`api_keys.${kind}_confirm.yes`);
  el('confirmOverlay').hidden = false;
  el('confirmDrawer').hidden = false;
  el('confirmDrawer').setAttribute('aria-hidden', 'false');
  console.log(`[FL:api_keys] confirm opened: ${kind} ${keyId}`);
}

function closeConfirm() {
  pendingAction = null;
  el('confirmOverlay').hidden = true;
  el('confirmDrawer').hidden = true;
  el('confirmDrawer').setAttribute('aria-hidden', 'true');
}

async function runConfirmedAction() {
  if (!pendingAction) return;
  const { kind, keyId } = pendingAction;
  const url = kind === 'revoke' ? `/api/keys/${keyId}/revoke` : `/api/keys/${keyId}`;
  const method = kind === 'revoke' ? 'POST' : 'DELETE';

  const res = await fetchAuth(url, { method });
  if (!res.ok) {
    showAlert(await errorMessage(res));
    closeConfirm();
    return;
  }

  console.log(`[FL:api_keys] ${kind} succeeded: ${keyId}`);
  keys = await loadKeys();
  render();
  closeConfirm();
}

function wireEvents() {
  el('addKeyBtn').addEventListener('click', openDrawer);
  el('drawerClose').addEventListener('click', closeDrawer);
  el('drawerOverlay').addEventListener('click', () => {
    // The reveal panel is deliberately not dismissible by an accidental overlay click.
    if (el('keyReveal').hidden) closeDrawer();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !el('keyDrawer').hidden && el('keyReveal').hidden) closeDrawer();
  });

  el('keyForm').addEventListener('submit', submitKey);
  el('revealCopyBtn').addEventListener('click', copyRevealedKey);
  el('revealDoneBtn').addEventListener('click', closeDrawer);

  el('confirmClose').addEventListener('click', closeConfirm);
  el('confirmNo').addEventListener('click', closeConfirm);
  el('confirmOverlay').addEventListener('click', closeConfirm);
  el('confirmYes').addEventListener('click', runConfirmedAction);
}

async function init() {
  await bootstrapPage({ page: 'api-keys', requireAuth: true });
  wireEvents();
  keys = await loadKeys();
  render();
}

init();
