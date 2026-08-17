/**
 * /profile — the real account-settings home: display name, password change, and the
 * public-profile toggle (moved here from /api-keys, which only ever hosted it as a stand-in —
 * see api-keys.js's history). Password change and display-name update both had working
 * backends since v0.1 (`POST /api/auth/me/password`, `PUT /api/auth/me`) with no page calling
 * them until now.
 */

import { bootstrapPage, renderNavAuth } from '/static/bootstrap.js';
import { fetchAuth, errorMessage, loadCurrentUser } from '/static/auth.js';

const el = (id) => document.getElementById(id);

// ---- account details ----

function renderAccount(user) {
  el('p_display_name').value = user.display_name;
  el('p_email').value = user.email;
}

function clearAccountAlerts() {
  el('accountAlert').classList.remove('visible');
  el('accountSuccess').classList.remove('visible');
  document.querySelectorAll('#accountForm .field-error').forEach((p) => (p.textContent = ''));
}

function renderAccountFieldErrors(details) {
  const errors = details?.errors || [];
  for (const err of errors) {
    const field = err.loc?.[err.loc.length - 1];
    const target = document.querySelector(`#accountForm .field-error[data-field="${field}"]`);
    if (target) target.textContent = err.msg;
    console.warn(`[FL:profile] validation error on ${field}: ${err.msg}`);
  }
  if (errors.length === 0) {
    el('accountAlert').textContent = window.t('common.error_generic');
    el('accountAlert').classList.add('visible');
  }
}

async function submitAccount(event) {
  event.preventDefault();
  clearAccountAlerts();
  const saveBtn = el('accountSave');
  saveBtn.disabled = true;

  const payload = { display_name: el('p_display_name').value.trim() };
  console.log('[FL:profile] PUT /api/auth/me', payload);

  try {
    const res = await fetchAuth('/api/auth/me', { method: 'PUT', body: JSON.stringify(payload) });
    if (!res.ok) {
      let details;
      try {
        details = (await res.json())?.error?.details;
      } catch {
        details = null;
      }
      if (res.status === 422 && details) {
        renderAccountFieldErrors(details);
      } else {
        el('accountAlert').textContent = await errorMessage(res);
        el('accountAlert').classList.add('visible');
      }
      console.error(`[FL:profile] account update failed (${res.status})`);
      return;
    }

    const user = await res.json();
    renderAccount(user);
    el('accountSuccess').textContent = window.t('profile.account.success');
    el('accountSuccess').classList.add('visible');
    console.log('[FL:profile] display name updated');

    // loadCurrentUser() always fetches fresh (no caching), but the nav link text was already
    // rendered at bootstrap with the old name — re-render it in place.
    await renderNavAuth();
  } finally {
    saveBtn.disabled = false;
  }
}

// ---- password change ----

function clearPasswordAlerts() {
  el('passwordAlert').classList.remove('visible');
  el('passwordSuccess').classList.remove('visible');
  document.querySelectorAll('#passwordForm .field-error').forEach((p) => (p.textContent = ''));
}

function renderPasswordFieldErrors(details) {
  const errors = details?.errors || [];
  for (const err of errors) {
    const field = err.loc?.[err.loc.length - 1];
    const target = document.querySelector(`#passwordForm .field-error[data-field="${field}"]`);
    if (target) target.textContent = err.msg;
    console.warn(`[FL:profile] validation error on ${field}: ${err.msg}`);
  }
  if (errors.length === 0) {
    el('passwordAlert').textContent = window.t('common.error_generic');
    el('passwordAlert').classList.add('visible');
  }
}

async function submitPassword(event) {
  event.preventDefault();
  clearPasswordAlerts();

  const currentPassword = el('p_current_password').value;
  const newPassword = el('p_new_password').value;
  const confirmPassword = el('p_confirm_password').value;

  if (newPassword !== confirmPassword) {
    document.querySelector('#passwordForm .field-error[data-field="confirm_password"]').textContent =
      window.t('profile.password.mismatch');
    console.warn('[FL:profile] new password and confirmation do not match');
    return;
  }

  const saveBtn = el('passwordSave');
  saveBtn.disabled = true;
  console.log('[FL:profile] POST /api/auth/me/password');

  try {
    const res = await fetchAuth('/api/auth/me/password', {
      method: 'POST',
      body: JSON.stringify({ current_password: currentPassword, password: newPassword }),
    });
    if (!res.ok) {
      let details;
      try {
        details = (await res.json())?.error?.details;
      } catch {
        details = null;
      }
      if (res.status === 401) {
        document.querySelector('#passwordForm .field-error[data-field="current_password"]').textContent =
          await errorMessage(res);
      } else if (res.status === 422 && details) {
        renderPasswordFieldErrors(details);
      } else {
        el('passwordAlert').textContent = await errorMessage(res);
        el('passwordAlert').classList.add('visible');
      }
      console.error(`[FL:profile] password change failed (${res.status})`);
      return;
    }

    el('passwordForm').reset();
    el('passwordSuccess').textContent = window.t('profile.password.success');
    el('passwordSuccess').classList.add('visible');
    console.log('[FL:profile] password changed');
  } finally {
    saveBtn.disabled = false;
  }
}

// ---- public profile toggle (moved from api-keys.js, v0.9) ----

function renderPublicProfile(user) {
  el('publicProfileToggle').checked = user.public_profile_enabled;
  el('profileHint').textContent = window.t(
    user.public_profile_enabled
      ? 'public_profile_settings.hint_on'
      : 'public_profile_settings.hint_off',
  );
  el('profileLinkRow').hidden = !user.public_profile_enabled;
  if (user.public_profile_enabled) {
    el('profileLinkValue').textContent = `${window.location.origin}/public/profiles/${user.id}`;
  }
}

async function togglePublicProfile(enabled) {
  el('profileAlert').classList.remove('visible');
  console.log(`[FL:profile] PUT /api/auth/me public_profile_enabled=${enabled}`);

  const res = await fetchAuth('/api/auth/me', {
    method: 'PUT',
    body: JSON.stringify({ public_profile_enabled: enabled }),
  });
  if (!res.ok) {
    el('publicProfileToggle').checked = !enabled; // revert the optimistic click
    el('profileAlert').textContent = await errorMessage(res);
    el('profileAlert').classList.add('visible');
    console.error(`[FL:profile] public profile toggle failed (${res.status})`);
    return;
  }

  renderPublicProfile(await res.json());
  console.log(`[FL:profile] public profile ${enabled ? 'enabled' : 'disabled'}`);
}

function wireEvents() {
  el('accountForm').addEventListener('submit', submitAccount);
  el('passwordForm').addEventListener('submit', submitPassword);
  el('publicProfileToggle').addEventListener('change', (event) => {
    togglePublicProfile(event.target.checked);
  });
}

async function init() {
  await bootstrapPage({ page: 'profile', requireAuth: true });
  wireEvents();

  const user = await loadCurrentUser();
  if (user) {
    renderAccount(user);
    renderPublicProfile(user);
  }
}

init();
