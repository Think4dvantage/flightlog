/**
 * /import — read-only view of the v0.2 production import's findings. Performs no write,
 * re-import, or resolution action; see core/import_history.py for the frozen source.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';

const el = (id) => document.getElementById(id);

function fillTable(rows, tbodyId, emptyId, rowBuilder) {
  const tbody = el(tbodyId);
  tbody.innerHTML = '';
  el(emptyId).hidden = rows.length > 0;
  el(tbodyId).closest('table').hidden = rows.length === 0;

  for (const row of rows) {
    const tr = document.createElement('tr');
    for (const text of rowBuilder(row)) {
      const td = document.createElement('td');
      td.textContent = text;
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
}

async function loadReport() {
  const started = performance.now();
  const res = await fetchAuth('/api/import-report');
  console.log(`[FL:import] GET /api/import-report → ${res.status} (${(performance.now() - started).toFixed(0)}ms)`);
  if (!res.ok) {
    el('alert').textContent = await errorMessage(res);
    el('alert').classList.add('visible');
    return null;
  }
  return res.json();
}

function render(report) {
  el('importedAt').textContent = window.t('import.imported_at', { date: report.imported_at });

  fillTable(report.unresolved_gear, 'gearBody', 'gearEmpty', (g) => [
    g.kind,
    g.value,
    String(g.flight_count),
  ]);

  fillTable(report.region_mismatches, 'regionBody', 'regionEmpty', (r) => [
    r.region,
    String(r.computed),
    String(r.sheet),
  ]);

  fillTable(report.altgain_mismatches, 'altgainBody', 'altgainEmpty', (a) => [
    String(a.row),
    `${a.computed_alt_gain_m} m`,
    `${a.sheet_altgain} m`,
    `${a.delta} m`,
  ]);

  fillTable(report.buddy_proposals, 'buddyBody', 'buddyEmpty', (b) => [
    b.name,
    String(b.flight_count),
  ]);
}

async function init() {
  await bootstrapPage({ page: 'import', requireAuth: true });
  const report = await loadReport();
  if (report) render(report);
}

init();
