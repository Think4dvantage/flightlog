/**
 * Pure, stateless rendering helpers for the statistics dashboard — extracted from `stats.js`
 * so `/stats` (authenticated, per-section fetch) and `public-stats.js` (anonymous, one bundled
 * fetch) share exactly one implementation of every chart/table builder, instead of drifting the
 * moment one page gets a future tweak the other doesn't. Mechanical extraction: same element
 * ids, same reliance on the global `window.t` every other page in this app already uses — no
 * behavior change from what `stats.js` did inline before.
 *
 * Both pages must render into elements with these same ids for the shared functions below to
 * find them: `yearMonthTable`, `chartMonthlyByYear`, `siteDiversityNote`, `matrixTable`,
 * `matrixEmpty`, plus whatever canvas id each `barChart()` caller passes explicitly.
 */

const el = (id) => document.getElementById(id);

export const MATRIX_DIMENSIONS = ['site', 'region', 'glider', 'harness', 'category', 'buddy'];
export const MONTH_LABELS = Array.from({ length: 12 }, (_, i) =>
  new Date(2000, i, 1).toLocaleString('en', { month: 'short' }),
);
export const MONTH_NUMS = Array.from({ length: 12 }, (_, i) => i + 1);

export const YEAR_PALETTE = ['#63b3ed', '#68d391', '#f6ad55', '#fc8181', '#b794f4', '#4fd1c5', '#f687b3', '#ecc94b'];

export function statTile(mount, label, value) {
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

export function fmtDuration(min) {
  if (min == null) return '—';
  const total = Math.round(min);
  const h = Math.floor(total / 60);
  const m = total % 60;
  return h > 0 ? `${h}h ${String(m).padStart(2, '0')}min` : `${m} min`;
}

export function fmtNum(value, digits = 1) {
  return value == null ? '—' : Number(value).toFixed(digits);
}

export function currencyColor(days) {
  const styles = getComputedStyle(document.documentElement);
  if (days == null) return '';
  if (days <= 14) return styles.getPropertyValue('--success').trim();
  if (days <= 45) return styles.getPropertyValue('--warm').trim();
  return styles.getPropertyValue('--danger').trim();
}

export function accentColor() {
  const styles = getComputedStyle(document.documentElement);
  return styles.getPropertyValue('--accent-strong').trim() || '#63b3ed';
}

export function textColor() {
  const styles = getComputedStyle(document.documentElement);
  return styles.getPropertyValue('--text').trim() || '#e2e8f0';
}

/**
 * Draws each bar's own value above it, so a value never needs a hover to read.
 *
 * The formatter is stashed directly on the chart instance (chart.$barValueLabelFormatter),
 * NOT inside `options` — Chart.js auto-invokes any function found while resolving its own
 * `options` tree as a "scriptable option" (passing its own internal context object, not
 * the bar's value), which crashed every downstream `Math.round()`/`toFixed()` call the
 * first time this tried storing the formatter under `options.plugins.barValueLabel`.
 */
export const barValueLabelPlugin = {
  id: 'barValueLabel',
  afterDatasetsDraw(chart) {
    const formatter = chart.$barValueLabelFormatter;
    if (!formatter) return;
    const { ctx } = chart;
    chart.data.datasets.forEach((dataset, datasetIndex) => {
      const meta = chart.getDatasetMeta(datasetIndex);
      meta.data.forEach((bar, index) => {
        const value = dataset.data[index];
        if (value == null) return;
        ctx.save();
        ctx.fillStyle = textColor();
        ctx.font = '11px system-ui, -apple-system, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        ctx.fillText(formatter(value), bar.x, bar.y - 4);
        ctx.restore();
      });
    });
  },
};

export function barChart(canvasId, labels, data, existing, formatter) {
  existing?.destroy();
  const chart = new Chart(el(canvasId).getContext('2d'), {
    type: 'bar',
    data: { labels, datasets: [{ data, backgroundColor: accentColor() }] },
    plugins: [barValueLabelPlugin],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { top: 18 } }, // room for the tallest bar's label
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });
  chart.$barValueLabelFormatter = formatter || ((v) => String(Math.round(v)));
  return chart;
}

function cardColor() {
  const styles = getComputedStyle(document.documentElement);
  return styles.getPropertyValue('--card').trim() || '#1a1f2e';
}

/**
 * Draws the combined total above each stacked bar's full height, not each segment's own
 * value — `barValueLabelPlugin` labels one dataset's bars directly; a stacked chart with one
 * dataset per contributing flight would otherwise need a label per segment, unreadable the
 * moment a month has more than a couple of flights. Computed from the datasets already on
 * the chart rather than passed in separately, so the caller can't let the two drift apart.
 * Same "formatter lives on the chart instance, never inside `options`" rule as
 * `barValueLabelPlugin` — see that plugin's own docstring for why.
 */
export const stackedTotalLabelPlugin = {
  id: 'stackedTotalLabel',
  afterDatasetsDraw(chart) {
    const formatter = chart.$stackedTotalFormatter;
    if (!formatter) return;
    const { ctx } = chart;
    const meta = chart.getDatasetMeta(0);
    chart.data.labels.forEach((_, index) => {
      const total = chart.data.datasets.reduce((sum, ds) => sum + (ds.data[index] ?? 0), 0);
      if (total === 0) return;
      const bar = meta.data[index];
      const yPixel = chart.scales.y.getPixelForValue(total);
      ctx.save();
      ctx.fillStyle = textColor();
      ctx.font = '11px system-ui, -apple-system, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'bottom';
      ctx.fillText(formatter(total), bar.x, yPixel - 4);
      ctx.restore();
    });
  },
};

/**
 * One bar per calendar month, each stacked from every contributing flight's own
 * `duration_min` (largest first — see `core/stats.py::airtime_by_month`'s docstring) rather
 * than a single pre-summed value. `borderColor` matches the card background so each segment
 * gets a hairline seam: a month built from many short flights renders as fine stripes, a
 * month built from a few long ones renders as a handful of solid chunks — the visual point
 * of this chart. Months don't all have the same number of flights, so shorter months get
 * `null` in the higher-numbered slots; Chart.js simply omits a `null` segment rather than
 * drawing a zero-height one.
 */
export function renderAirtimeByMonthChart(byMonth, existing) {
  const maxSlots = Math.max(0, ...MONTH_NUMS.map((m) => (byMonth[m] || []).length));
  const seam = cardColor();
  const fill = accentColor();

  const datasets = Array.from({ length: maxSlots }, (_, slot) => ({
    data: MONTH_NUMS.map((m) => (byMonth[m] || [])[slot] ?? null),
    backgroundColor: fill,
    borderColor: seam,
    borderWidth: 1,
    stack: 'airtime',
  }));

  existing?.destroy();
  const chart = new Chart(el('chartAirtimeByMonth').getContext('2d'), {
    type: 'bar',
    data: { labels: MONTH_LABELS, datasets },
    plugins: [stackedTotalLabelPlugin],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { top: 18 } },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: () => '',
            label: (ctx) => (ctx.raw == null ? '' : fmtDuration(ctx.raw)),
          },
        },
      },
      scales: {
        x: { stacked: true },
        y: { stacked: true, beginAtZero: true, ticks: { callback: (v) => fmtDuration(v) } },
      },
    },
  });
  chart.$stackedTotalFormatter = fmtDuration;
  return chart;
}

export function renderYearMonthMatrix(matrix, years) {
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

/**
 * Replaces the old "cumulative flights over time" chart (v0.7.4) — a running total is
 * monotonically increasing by construction and carries no information (a straight line
 * regardless of the pilot's real activity). This instead overlays one line per year across
 * Jan-Dec, built entirely from time-breakdown's own year_month_matrix.
 */
export function renderMonthlyByYearChart(matrix, years, existing) {
  const datasets = years.map((year, idx) => ({
    label: String(year),
    data: MONTH_NUMS.map((m) => matrix[year]?.[m] ?? 0),
    borderColor: YEAR_PALETTE[idx % YEAR_PALETTE.length],
    backgroundColor: YEAR_PALETTE[idx % YEAR_PALETTE.length],
    pointRadius: 2,
    tension: 0.25,
    fill: false,
  }));

  existing?.destroy();
  return new Chart(el('chartMonthlyByYear').getContext('2d'), {
    type: 'line',
    data: { labels: MONTH_LABELS, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: true, position: 'bottom', labels: { boxWidth: 12 } } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });
}

export function formatPersonalBestValue(label, value) {
  if (label === 'longest_airtime') return fmtDuration(value);
  if (label.includes('distance')) return `${fmtNum(value)} km`;
  return `${Math.round(value)} m`;
}

export function daysAgoText(isoDate) {
  const days = Math.round((Date.now() - new Date(`${isoDate}T00:00:00Z`).getTime()) / 86400000);
  if (days >= 365) {
    return window.t('stats.personal_bests.set_years_ago', { count: (days / 365).toFixed(1) });
  }
  return window.t('stats.personal_bests.set_days_ago', { count: days });
}

export function renderSiteDiversityNote(activeDimension, rows) {
  const note = el('siteDiversityNote');
  if (activeDimension !== 'site' || !rows || rows.length === 0) {
    note.hidden = true;
    return;
  }
  const sorted = [...rows].sort((a, b) => b.total - a.total);
  const top5Total = sorted.slice(0, 5).reduce((sum, r) => sum + r.total, 0);
  const grandTotal = rows.reduce((sum, r) => sum + r.total, 0);
  const pct = grandTotal ? Math.round((top5Total / grandTotal) * 100) : 0;
  note.hidden = false;
  note.textContent = window.t('stats.matrix.site_diversity', { pct, siteCount: rows.length });
}

export function renderMatrixTable(data) {
  const table = el('matrixTable');
  const thead = table.querySelector('thead');
  const tbody = table.querySelector('tbody');
  thead.textContent = '';
  tbody.textContent = '';

  if (!data || data.rows.length === 0) {
    el('matrixEmpty').hidden = false;
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
}
