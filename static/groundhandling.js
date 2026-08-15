/**
 * /groundhandling — read-only list of imported groundhandling sessions. Import-and-view only.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';

const el = (id) => document.getElementById(id);

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

function render(sessions) {
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

    tbody.appendChild(tr);
  }

  el('emptyState').hidden = sessions.length > 0;
  el('sessionsTable').hidden = sessions.length === 0;
  el('resultCount').textContent = window.t('groundhandling.result_count', { count: sessions.length });
}

async function init() {
  await bootstrapPage({ page: 'groundhandling', requireAuth: true });
  const sessions = await loadSessions();
  render(sessions);
}

init();
