/**
 * /stats — read-only statistics dashboard. Every section is fetched and rendered
 * independently (contracts/endpoints.md's "8 small endpoints" rationale) so the page
 * renders incrementally instead of blocking on the slowest aggregate.
 *
 * Rendering (chart/table builders) lives in `stats-render.js`, shared with `public-stats.js` —
 * this file owns only fetching and the per-page state (active matrix tab, chart instances).
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';
import {
  barChart,
  daysAgoText,
  fmtDuration,
  fmtNum,
  formatPersonalBestValue,
  currencyColor,
  MATRIX_DIMENSIONS,
  MONTH_LABELS,
  MONTH_NUMS,
  renderAirtimeByMonthChart,
  renderMatrixTable,
  renderMonthlyByYearChart,
  renderSiteDiversityNote,
  renderYearMonthMatrix,
  statTile,
} from '/static/stats-render.js';

const el = (id) => document.getElementById(id);

let activeDimension = 'site';
const matrixCache = {};

let totalFlights = null;

let chartByYear;
let chartByMonth;
let chartAirtimeByMonth;
let chartDurationDist;
let chartDistanceDist;
let chartAltitudeDist;
let chartMonthlyDuration;
let chartMonthlyDistance;
let chartMonthlyAltitude;
let chartXcProgression;
let chartMonthlyByYear;
let chartMonthlyThermals;

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

// ---- totals ----

async function loadTotals() {
  // igc-rollup is fetched here (and again in loadIgcRollup() below) so the IGC-derived total
  // airtime can render directly beside the self-reported one — a pilot-requested side-by-side
  // comparison, since the two numbers routinely disagree. A small duplicate GET, accepted rather
  // than threading shared state between the two independently-owned render functions.
  const [data, igc] = await Promise.all([
    getJson('/api/stats/totals'),
    getJson('/api/stats/igc-rollup'),
  ]);
  if (!data) return;

  totalFlights = data.total_flights;

  const mount = el('totalsGrid');
  mount.textContent = '';
  statTile(mount, window.t('stats.totals.total_flights'), String(data.total_flights));
  statTile(mount, window.t('stats.totals.total_airtime'), fmtDuration(data.total_airtime_min));
  if (igc && igc.tracks_uploaded > 0) {
    statTile(
      mount,
      window.t('stats.totals.total_airtime_igc'),
      fmtDuration(igc.total_igc_airtime_min),
    );
  }
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
  chartMonthlyByYear = renderMonthlyByYearChart(data.year_month_matrix, years, chartMonthlyByYear);
  console.log(`[FL:stats] time breakdown rendered: ${years.length} years`);
}

// ---- airtime by month ----

async function loadAirtimeByMonth() {
  const data = await getJson('/api/stats/airtime-by-month');
  if (!data) return;

  chartAirtimeByMonth = renderAirtimeByMonthChart(data.by_month, chartAirtimeByMonth);
  console.log(
    `[FL:stats] airtime by month rendered: ${MONTH_NUMS.map((m) => data.by_month[m].length).join(',')} flights/month`,
  );
}

// ---- XC progression ----

async function loadXcProgression() {
  const data = await getJson('/api/stats/xc-progression');
  if (!data) return;

  const threshold = data.threshold_km;
  el('xcProgressionHint').textContent = window.t('stats.xc_progression.hint', { threshold });

  chartXcProgression = barChart(
    'chartXcProgression',
    data.rows.map((r) => String(r.year)),
    data.rows.map((r) => r.xc_pct),
    chartXcProgression,
    (v) => `${Math.round(v)}%`,
  );
  console.log(`[FL:stats] XC progression rendered: ${data.rows.length} years, threshold=${threshold}km`);
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

// ---- monthly extremes ----

async function loadMonthlyExtremes() {
  const data = await getJson('/api/stats/monthly-extremes');
  if (!data) return;

  chartMonthlyDuration = barChart(
    'chartMonthlyDuration',
    MONTH_LABELS,
    MONTH_NUMS.map((m) => data.max_duration_min_by_month[m] ?? null),
    chartMonthlyDuration,
    (v) => fmtDuration(v),
  );
  chartMonthlyDistance = barChart(
    'chartMonthlyDistance',
    MONTH_LABELS,
    MONTH_NUMS.map((m) => data.max_distance_km_by_month[m] ?? null),
    chartMonthlyDistance,
    (v) => `${fmtNum(v)} km`,
  );
  chartMonthlyAltitude = barChart(
    'chartMonthlyAltitude',
    MONTH_LABELS,
    MONTH_NUMS.map((m) => data.max_alt_gain_m_by_month[m] ?? null),
    chartMonthlyAltitude,
    (v) => `${Math.round(v)} m`,
  );
  console.log('[FL:stats] monthly extremes rendered');
}

// ---- personal bests ----

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

    const setTd = document.createElement('td');
    setTd.className = 'muted';
    setTd.textContent = daysAgoText(best.flight_date);
    tr.appendChild(setTd);

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
  renderSiteDiversityNote(activeDimension, data?.rows);
  renderMatrixTable(data);
  console.log(
    data && data.rows.length > 0
      ? `[FL:stats] matrix rendered: ${activeDimension}, ${data.rows.length} rows`
      : `[FL:stats] matrix empty: ${activeDimension}`,
  );
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

  if (totalFlights) {
    const coveragePct = (data.tracks_uploaded / totalFlights) * 100;
    statTile(
      mount,
      window.t('stats.igc_rollup.coverage'),
      `${fmtNum(coveragePct, 1)}% (${data.tracks_uploaded}/${totalFlights})`,
    );
  }

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
  statTile(mount, window.t('stats.igc_rollup.total_thermals'), String(data.total_thermals));

  el('igcRollupThermalsChart').hidden = false;
  chartMonthlyThermals = barChart(
    'chartMonthlyThermals',
    MONTH_LABELS,
    MONTH_NUMS.map((m) => data.avg_thermals_by_month[m] ?? null),
    chartMonthlyThermals,
    (v) => fmtNum(v, 1),
  );

  console.log(
    `[FL:stats] igc rollup rendered: ${data.cumulative_thermal_climb_m}m, ${data.total_thermals} thermals over ${data.tracks_uploaded} tracks`,
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

  if (data.days_since_last_flight != null) {
    const currencyValue = window.t('stats.progression.currency_days', {
      count: data.days_since_last_flight,
    });
    statTile(mount, window.t('stats.progression.currency'), currencyValue);
    const lastTile = mount.lastElementChild.querySelector('.stat-value');
    lastTile.style.color = currencyColor(data.days_since_last_flight);
  }

  statTile(mount, window.t('stats.progression.ytd_this_year'), String(data.ytd_pace.this_year));
  statTile(
    mount,
    window.t('stats.progression.ytd_prior_year'),
    String(data.ytd_pace.same_point_prior_year),
  );

  // The monthly-by-year chart under this section is rendered by loadTimeBreakdown()
  // (it's built from year_month_matrix, already fetched there — no separate call here).
  console.log(
    `[FL:stats] progression rendered: streak=${data.current_streak.count}${data.current_streak.unit}, days_since_last_flight=${data.days_since_last_flight}`,
  );
}

async function init() {
  await bootstrapPage({ page: 'stats', requireAuth: true });
  renderMatrixTabs();

  // totalFlights (module-level) must be known before loadIgcRollup()'s coverage nudge —
  // awaited alone rather than folded into the Promise.all below.
  await loadTotals();

  await Promise.all([
    loadTimeBreakdown(),
    loadAirtimeByMonth(),
    loadXcProgression(),
    loadDistribution(),
    loadMonthlyExtremes(),
    loadPersonalBests(),
    renderMatrix(),
    loadLaunchTechnique(),
    loadIgcRollup(),
    loadProgression(),
  ]);
}

init();
