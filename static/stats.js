/**
 * /stats — read-only statistics dashboard. Every section is fetched and rendered
 * independently (contracts/endpoints.md's "8 small endpoints" rationale) so the page
 * renders incrementally instead of blocking on the slowest aggregate.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';

const el = (id) => document.getElementById(id);

const MATRIX_DIMENSIONS = ['site', 'region', 'glider', 'harness', 'category', 'buddy'];
const MONTH_LABELS = Array.from({ length: 12 }, (_, i) =>
  new Date(2000, i, 1).toLocaleString('en', { month: 'short' }),
);

let activeDimension = 'site';
const matrixCache = {};

let chartByYear;
let chartByMonth;
let chartDurationDist;
let chartDistanceDist;
let chartAltitudeDist;
let chartProgression;

function showAlert(message) {
  const box = el('alert');
  box.textContent = message;
  box.classList.add('visible');
}

async function getJson(path) {
  const started = performance.now();
  const res = await fetchAuth(path);
  const elapsed = (performance.now() - started).toFixed(0);
  if (!res.ok) {
    console.error(`[FL:stats] GET ${path} → ${res.status} (${elapsed}ms)`);
    showAlert(await errorMessage(res));
    return null;
  }
  console.log(`[FL:stats] GET ${path} → ${res.status} (${elapsed}ms)`);
  return res.json();
}

function statTile(mount, label, value) {
  const tile = document.createElement('div');
  tile.className = 'stat-tile';
  const l = document.createElement('div');
  l.className = 'stat-label';
  l.textContent = label;
  const v = document.createElement('div');
  v.className = 'stat-value';
  v.textContent = value;
  tile.append(l, v);
  mount.appendChild(tile);
}

function fmtDuration(min) {
  if (min == null) return '—';
  const total = Math.round(min);
  const h = Math.floor(total / 60);
  const m = total % 60;
  return h > 0 ? `${h}h ${String(m).padStart(2, '0')}min` : `${m} min`;
}

function fmtNum(value, digits = 1) {
  return value == null ? '—' : Number(value).toFixed(digits);
}

function accentColor() {
  const styles = getComputedStyle(document.documentElement);
  return styles.getPropertyValue('--accent-strong').trim() || '#63b3ed';
}

function barChart(canvasId, labels, data, existing) {
  existing?.destroy();
  return new Chart(el(canvasId).getContext('2d'), {
    type: 'bar',
    data: { labels, datasets: [{ data, backgroundColor: accentColor() }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });
}

// ---- totals ----

async function loadTotals() {
  const data = await getJson('/api/stats/totals');
  if (!data) return;

  const mount = el('totalsGrid');
  mount.textContent = '';
  statTile(mount, window.t('stats.totals.total_flights'), String(data.total_flights));
  statTile(mount, window.t('stats.totals.total_airtime'), fmtDuration(data.total_airtime_min));
  statTile(mount, window.t('stats.totals.total_distance'), `${fmtNum(data.total_distance_km)} km`);
  statTile(mount, window.t('stats.totals.total_alt_gain'), `${data.total_alt_gain_m} m`);
  statTile(mount, window.t('stats.totals.avg_airtime'), fmtDuration(data.avg_airtime_min));
  statTile(
    mount,
    window.t('stats.totals.avg_airtime_excl_training'),
    fmtDuration(data.avg_airtime_min_excl_training),
  );
  statTile(mount, window.t('stats.totals.avg_distance'), `${fmtNum(data.avg_distance_km)} km`);
  console.log(`[FL:stats] totals rendered: ${data.total_flights} flights`);
}

// ---- time breakdown ----

function renderYearMonthMatrix(matrix, years) {
  const table = el('yearMonthTable');
  const thead = table.querySelector('thead');
  const tbody = table.querySelector('tbody');
  thead.textContent = '';
  tbody.textContent = '';

  const headRow = document.createElement('tr');
  headRow.appendChild(document.createElement('th'));
  for (const label of MONTH_LABELS) {
    const th = document.createElement('th');
    th.textContent = label;
    headRow.appendChild(th);
  }
  thead.appendChild(headRow);

  for (const year of years) {
    const row = document.createElement('tr');
    const yearTh = document.createElement('th');
    yearTh.textContent = String(year);
    row.appendChild(yearTh);
    for (let m = 1; m <= 12; m++) {
      const td = document.createElement('td');
      td.textContent = String(matrix[year]?.[m] ?? 0);
      row.appendChild(td);
    }
    tbody.appendChild(row);
  }
}

async function loadTimeBreakdown() {
  const data = await getJson('/api/stats/time-breakdown');
  if (!data) return;

  const years = Object.keys(data.by_year)
    .map(Number)
    .sort((a, b) => a - b);
  chartByYear = barChart(
    'chartByYear',
    years,
    years.map((y) => data.by_year[y]),
    chartByYear,
  );

  const months = Object.keys(data.by_month)
    .map(Number)
    .sort((a, b) => a - b);
  chartByMonth = barChart(
    'chartByMonth',
    months.map((m) => MONTH_LABELS[m - 1]),
    months.map((m) => data.by_month[m]),
    chartByMonth,
  );

  renderYearMonthMatrix(data.year_month_matrix, years);
  console.log(`[FL:stats] time breakdown rendered: ${years.length} years`);
}

// ---- distributions ----

async function loadDistribution() {
  const data = await getJson('/api/stats/distribution');
  if (!data) return;

  chartDurationDist = barChart(
    'chartDurationDist',
    Object.keys(data.duration_buckets),
    Object.values(data.duration_buckets),
    chartDurationDist,
  );
  chartDistanceDist = barChart(
    'chartDistanceDist',
    Object.keys(data.distance_buckets),
    Object.values(data.distance_buckets),
    chartDistanceDist,
  );
  chartAltitudeDist = barChart(
    'chartAltitudeDist',
    Object.keys(data.altitude_buckets),
    Object.values(data.altitude_buckets),
    chartAltitudeDist,
  );
  console.log('[FL:stats] distributions rendered');
}

// ---- personal bests ----

function formatPersonalBestValue(label, value) {
  if (label === 'longest_airtime') return fmtDuration(value);
  if (label.includes('distance')) return `${fmtNum(value)} km`;
  return `${Math.round(value)} m`;
}

async function loadPersonalBests() {
  const data = await getJson('/api/stats/personal-bests');
  if (!data) return;

  const body = el('personalBestsBody');
  body.textContent = '';
  el('personalBestsEmpty').hidden = data.length > 0;

  for (const best of data) {
    const tr = document.createElement('tr');

    const labelTd = document.createElement('td');
    labelTd.textContent = window.t(`stats.personal_bests.label.${best.label}`);
    tr.appendChild(labelTd);

    const valueTd = document.createElement('td');
    valueTd.textContent = formatPersonalBestValue(best.label, best.value);
    tr.appendChild(valueTd);

    const linkTd = document.createElement('td');
    const a = document.createElement('a');
    a.href = `/flights/${best.flight_id}`;
    a.textContent = window.t('stats.personal_bests.view_flight');
    linkTd.appendChild(a);
    tr.appendChild(linkTd);

    body.appendChild(tr);
  }
  console.log(`[FL:stats] personal bests rendered: ${data.length}`);
}

// ---- dimension matrices ----

function renderMatrixTabs() {
  const mount = el('matrixTabs');
  mount.textContent = '';
  for (const dim of MATRIX_DIMENSIONS) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = window.t(`stats.matrix.${dim}_title`);
    btn.className = dim === activeDimension ? 'active' : '';
    btn.addEventListener('click', () => {
      if (dim === activeDimension) return;
      activeDimension = dim;
      console.log(`[FL:stats] matrix tab switched to ${dim}`);
      renderMatrixTabs();
      renderMatrix();
    });
    mount.appendChild(btn);
  }

  el('matrixTitle').textContent = window.t(`stats.matrix.${activeDimension}_title`);
  const hint = el('matrixHint');
  hint.hidden = activeDimension !== 'buddy';
  if (activeDimension === 'buddy') hint.textContent = window.t('stats.matrix.buddy_hint');
}

async function loadMatrix(dimension) {
  if (matrixCache[dimension]) return matrixCache[dimension];
  const data = await getJson(`/api/stats/matrix/${dimension}`);
  matrixCache[dimension] = data;
  return data;
}

async function renderMatrix() {
  const data = await loadMatrix(activeDimension);
  const table = el('matrixTable');
  const thead = table.querySelector('thead');
  const tbody = table.querySelector('tbody');
  thead.textContent = '';
  tbody.textContent = '';

  if (!data || data.rows.length === 0) {
    el('matrixEmpty').hidden = false;
    console.log(`[FL:stats] matrix empty: ${activeDimension}`);
    return;
  }
  el('matrixEmpty').hidden = true;

  const years = [...new Set(data.rows.flatMap((r) => Object.keys(r.by_year).map(Number)))].sort(
    (a, b) => a - b,
  );

  const headRow = document.createElement('tr');
  headRow.appendChild(document.createElement('th'));
  for (const year of years) {
    const th = document.createElement('th');
    th.textContent = String(year);
    headRow.appendChild(th);
  }
  const totalTh = document.createElement('th');
  totalTh.textContent = window.t('stats.matrix.col_total');
  headRow.appendChild(totalTh);
  thead.appendChild(headRow);

  for (const row of data.rows) {
    const tr = document.createElement('tr');

    const nameTd = document.createElement('td');
    nameTd.textContent = row.name || window.t('stats.matrix.not_recorded');
    tr.appendChild(nameTd);

    for (const year of years) {
      const td = document.createElement('td');
      td.textContent = String(row.by_year[year] ?? 0);
      tr.appendChild(td);
    }

    const totalTd = document.createElement('td');
    totalTd.textContent = String(row.total);
    tr.appendChild(totalTd);

    tbody.appendChild(tr);
  }

  console.log(`[FL:stats] matrix rendered: ${activeDimension}, ${data.rows.length} rows`);
}

// ---- launch technique ----

async function loadLaunchTechnique() {
  const data = await getJson('/api/stats/launch-technique');
  if (!data) return;

  const mount = el('launchTechniqueGrid');
  mount.textContent = '';
  statTile(mount, window.t('stats.launch_technique.forward'), String(data.forward));
  statTile(mount, window.t('stats.launch_technique.reverse'), String(data.reverse));
  statTile(mount, window.t('stats.launch_technique.reverse_pct'), `${fmtNum(data.reverse_pct)}%`);
  statTile(mount, window.t('stats.launch_technique.hike_fly_total'), String(data.hike_fly_total));
  console.log(`[FL:stats] launch technique rendered: reverse_pct=${data.reverse_pct}`);
}

// ---- IGC rollup ----

async function loadIgcRollup() {
  const data = await getJson('/api/stats/igc-rollup');
  if (!data) return;

  const mount = el('igcRollupGrid');
  mount.textContent = '';

  if (data.tracks_uploaded === 0) {
    el('igcRollupEmpty').hidden = false;
    console.log('[FL:stats] igc rollup: no tracks uploaded yet');
    return;
  }
  el('igcRollupEmpty').hidden = true;
  statTile(
    mount,
    window.t('stats.igc_rollup.cumulative_climb'),
    `${fmtNum(data.cumulative_thermal_climb_m, 0)} m`,
  );
  statTile(mount, window.t('stats.igc_rollup.tracks_uploaded'), String(data.tracks_uploaded));
  console.log(
    `[FL:stats] igc rollup rendered: ${data.cumulative_thermal_climb_m}m over ${data.tracks_uploaded} tracks`,
  );
}

// ---- streak, YTD pace, progression ----

async function loadProgression() {
  const data = await getJson('/api/stats/progression');
  if (!data) return;

  const mount = el('progressionGrid');
  mount.textContent = '';

  const streakLabel =
    data.current_streak.count > 0
      ? window.t('stats.progression.streak_week', { count: data.current_streak.count })
      : window.t('stats.progression.streak_zero');
  statTile(mount, window.t('stats.progression.title'), streakLabel);
  statTile(mount, window.t('stats.progression.ytd_this_year'), String(data.ytd_pace.this_year));
  statTile(
    mount,
    window.t('stats.progression.ytd_prior_year'),
    String(data.ytd_pace.same_point_prior_year),
  );

  chartProgression?.destroy();
  chartProgression = new Chart(el('chartProgression').getContext('2d'), {
    type: 'line',
    data: {
      labels: data.cumulative_series.map((p) => p.date),
      datasets: [
        {
          data: data.cumulative_series.map((p) => p.cumulative_count),
          borderColor: accentColor(),
          pointRadius: 0,
          tension: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { ticks: { maxTicksLimit: 12 } }, y: { beginAtZero: true } },
    },
  });
  console.log(
    `[FL:stats] progression rendered: streak=${data.current_streak.count}${data.current_streak.unit}, ${data.cumulative_series.length} points`,
  );
}

async function init() {
  await bootstrapPage({ page: 'stats', requireAuth: true });
  renderMatrixTabs();

  await Promise.all([
    loadTotals(),
    loadTimeBreakdown(),
    loadDistribution(),
    loadPersonalBests(),
    renderMatrix(),
    loadLaunchTechnique(),
    loadIgcRollup(),
    loadProgression(),
  ]);
}

init();
