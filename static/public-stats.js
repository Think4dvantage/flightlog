/**
 * /public/stats/{id} — anonymous-visitor view of a pilot's full statistics dashboard (v0.9.5).
 * One bundled `GET /api/public/stats/{id}` fetch, not the ten-plus requests the authenticated
 * `/stats` page makes — this surface is `slowapi`-rate-limited per request, and a visitor
 * clicking through matrix tabs must not burn through that budget for data already in hand.
 *
 * Rendering reuses `stats-render.js` — the same chart/table builders `/stats` uses, so the two
 * pages can't silently drift apart. `bootstrapPage` runs with `anonymous: true`, same as
 * `public-flight.js`/`public-profile.js`: a visitor's own (possibly stale) localStorage token
 * must never trigger a redirect-to-/login on a page anyone must be able to load.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { errorMessage } from '/static/auth.js';
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
  renderMatrixTable,
  renderMonthlyByYearChart,
  renderSiteDiversityNote,
  renderYearMonthMatrix,
  statTile,
} from '/static/stats-render.js';

const el = (id) => document.getElementById(id);

let activeDimension = 'site';
let stats = null;

let chartByYear;
let chartByMonth;
let chartDurationDist;
let chartDistanceDist;
let chartAltitudeDist;
let chartMonthlyDuration;
let chartMonthlyDistance;
let chartMonthlyAltitude;
let chartXcProgression;
let chartMonthlyByYear;
let chartMonthlyThermals;

function userIdFromUrl() {
  const parts = window.location.pathname.split('/').filter(Boolean);
  return parts[parts.length - 1];
}

function showAlert(message) {
  el('alert').textContent = message;
  el('alert').classList.add('visible');
  console.error(`[FL:public-stats] ${message}`);
}

async function loadStats(id) {
  const started = performance.now();
  const res = await fetch(`/api/public/stats/${id}`);
  console.log(`[FL:public-stats] GET /api/public/stats/${id} → ${res.status} (${(performance.now() - started).toFixed(0)}ms)`);
  if (!res.ok) {
    showAlert(await errorMessage(res));
    return null;
  }
  return res.json();
}

// ---- totals ----

function renderTotals() {
  const { totals, igc_rollup: igc } = stats;
  const mount = el('totalsGrid');
  mount.textContent = '';
  statTile(mount, window.t('stats.totals.total_flights'), String(totals.total_flights));
  statTile(mount, window.t('stats.totals.total_airtime'), fmtDuration(totals.total_airtime_min));
  if (igc.tracks_uploaded > 0) {
    statTile(mount, window.t('stats.totals.total_airtime_igc'), fmtDuration(igc.total_igc_airtime_min));
  }
  statTile(mount, window.t('stats.totals.total_distance'), `${fmtNum(totals.total_distance_km)} km`);
  statTile(mount, window.t('stats.totals.total_alt_gain'), `${totals.total_alt_gain_m} m`);
  statTile(mount, window.t('stats.totals.avg_airtime'), fmtDuration(totals.avg_airtime_min));
  statTile(
    mount,
    window.t('stats.totals.avg_airtime_excl_training'),
    fmtDuration(totals.avg_airtime_min_excl_training),
  );
  statTile(mount, window.t('stats.totals.avg_distance'), `${fmtNum(totals.avg_distance_km)} km`);
}

// ---- time breakdown ----

function renderTimeBreakdown() {
  const data = stats.time_breakdown;

  const years = Object.keys(data.by_year)
    .map(Number)
    .sort((a, b) => a - b);
  chartByYear = barChart('chartByYear', years, years.map((y) => data.by_year[y]), chartByYear);

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
}

// ---- XC progression ----

function renderXcProgression() {
  const data = stats.xc_progression;
  el('xcProgressionHint').textContent = window.t('stats.xc_progression.hint', {
    threshold: data.threshold_km,
  });
  chartXcProgression = barChart(
    'chartXcProgression',
    data.rows.map((r) => String(r.year)),
    data.rows.map((r) => r.xc_pct),
    chartXcProgression,
    (v) => `${Math.round(v)}%`,
  );
}

// ---- distributions ----

function renderDistribution() {
  const data = stats.distribution;
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
}

// ---- monthly extremes ----

function renderMonthlyExtremes() {
  const data = stats.monthly_extremes;
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
}

// ---- personal bests ----

function renderPersonalBests() {
  const data = stats.personal_bests;
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

    // Only a public/unlisted flight gets a link — a private one that still won the record
    // has no flight_id here at all (never a link that would 404), see api/routers/public.py.
    const linkTd = document.createElement('td');
    if (best.flight_id) {
      const a = document.createElement('a');
      a.href = `/public/flights/${best.flight_id}`;
      a.textContent = window.t('stats.personal_bests.view_flight');
      linkTd.appendChild(a);
    }
    tr.appendChild(linkTd);

    body.appendChild(tr);
  }
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
      console.log(`[FL:public-stats] matrix tab switched to ${dim}`);
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

function renderMatrix() {
  const data = stats.matrices[activeDimension];
  renderSiteDiversityNote(activeDimension, data?.rows);
  renderMatrixTable(data);
}

// ---- launch technique ----

function renderLaunchTechnique() {
  const data = stats.launch_technique;
  const mount = el('launchTechniqueGrid');
  mount.textContent = '';
  statTile(mount, window.t('stats.launch_technique.forward'), String(data.forward));
  statTile(mount, window.t('stats.launch_technique.reverse'), String(data.reverse));
  statTile(mount, window.t('stats.launch_technique.reverse_pct'), `${fmtNum(data.reverse_pct)}%`);
  statTile(mount, window.t('stats.launch_technique.hike_fly_total'), String(data.hike_fly_total));
}

// ---- IGC rollup ----

function renderIgcRollup() {
  const data = stats.igc_rollup;
  const totalFlights = stats.totals.total_flights;
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
}

// ---- progression ----

function renderProgression() {
  const data = stats.progression;
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
}

// ---- header ----

function renderHeader() {
  // owner_display_name is user data — textContent only, never innerHTML.
  el('s_title').textContent = window.t('public_stats.title_for', {
    name: stats.owner_display_name,
  });

  const profileLink = el('s_profile_link');
  if (stats.owner_has_public_profile) {
    profileLink.hidden = false;
    profileLink.textContent = '';
    const a = document.createElement('a');
    a.href = `/public/profiles/${stats.owner_id}`;
    a.textContent = window.t('public_stats.view_profile', { name: stats.owner_display_name });
    profileLink.appendChild(a);
  } else {
    profileLink.hidden = true;
  }
}

function render() {
  renderHeader();
  renderTotals();
  renderTimeBreakdown();
  renderXcProgression();
  renderDistribution();
  renderMonthlyExtremes();
  renderPersonalBests();
  renderMatrixTabs();
  renderMatrix();
  renderLaunchTechnique();
  renderIgcRollup();
  renderProgression();
  el('statsBody').hidden = false;
  console.log('[FL:public-stats] rendered');
}

async function init() {
  await bootstrapPage({ page: 'public-stats', anonymous: true });

  const id = userIdFromUrl();
  console.log(`[FL:public-stats] loading stats for ${id}`);
  stats = await loadStats(id);
  if (!stats) return;
  render();
}

init();
