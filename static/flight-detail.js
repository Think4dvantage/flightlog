/**
 * /flights/{id} — read-only detail view. Fresh-load safe: reads the id from the URL path,
 * not from any in-memory list state.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';
import {
  loadRefData,
  siteName,
  gliderName,
  harnessName,
  categoryName,
  getBuddies,
} from '/static/refdata.js';

const el = (id) => document.getElementById(id);

function flightIdFromUrl() {
  const parts = window.location.pathname.split('/').filter(Boolean);
  return parts[parts.length - 1];
}

function notRecorded() {
  return window.t('flight_detail.not_recorded');
}

function fmtDate(iso) {
  const d = new Date(`${iso}T00:00:00Z`);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
}

function fmtDuration(min) {
  if (min == null) return notRecorded();
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h > 0 ? `${h}h ${String(m).padStart(2, '0')}min` : `${m} min`;
}

function fmtNumber(value, unit) {
  return value == null ? notRecorded() : `${value} ${unit}`;
}

function linkOrText(mount, name, href) {
  mount.textContent = '';
  if (!name) {
    mount.textContent = notRecorded();
    return;
  }
  const a = document.createElement('a');
  a.href = href;
  a.textContent = name;
  mount.appendChild(a);
}

async function loadFlight(id) {
  const started = performance.now();
  const res = await fetchAuth(`/api/flights/${id}`);
  console.log(`[FL:flight-detail] GET /api/flights/${id} → ${res.status} (${(performance.now() - started).toFixed(0)}ms)`);
  if (!res.ok) {
    el('alert').textContent = await errorMessage(res);
    el('alert').classList.add('visible');
    return null;
  }
  return res.json();
}

function render(flight) {
  el('d_date').textContent = fmtDate(flight.flight_date);

  linkOrText(el('d_launch'), siteName(flight.launch_site_id), '/sites');
  linkOrText(el('d_landing'), siteName(flight.landing_site_id), '/sites');
  el('d_category').textContent = categoryName(flight.category_id) || notRecorded();
  linkOrText(el('d_glider'), gliderName(flight.glider_id), '/equipment');
  linkOrText(el('d_harness'), harnessName(flight.harness_id), '/equipment');

  el('d_duration').textContent = fmtDuration(flight.duration_min);
  el('d_distance').textContent = fmtNumber(flight.distance_km, 'km');
  el('d_maxalt').textContent = fmtNumber(flight.max_alt_m, 'm');
  el('d_altgain').textContent = fmtNumber(flight.alt_gain_m, 'm');
  el('d_sitedrop').textContent = fmtNumber(flight.site_drop_m, 'm');
  el('d_totaldescent').textContent = fmtNumber(flight.total_descent_m, 'm');

  el('d_technique').textContent = flight.launch_technique
    ? window.t(`flight_detail.technique_${flight.launch_technique}`)
    : notRecorded();

  const buddyMap = new Map(getBuddies().map((b) => [b.id, b.display_name]));
  const names = flight.buddy_ids.map((id) => buddyMap.get(id)).filter(Boolean);
  el('d_buddies').textContent = names.length > 0 ? names.join(', ') : notRecorded();

  el('d_notes').textContent = flight.notes || notRecorded();

  renderLinks(flight.links || []);

  el('detailBody').hidden = false;
}

function renderLinks(links) {
  const dt = el('d_links_dt');
  const dd = el('d_links');
  dd.textContent = '';

  if (links.length === 0) {
    dt.hidden = true;
    dd.hidden = true;
    return;
  }

  dt.hidden = false;
  dd.hidden = false;
  for (const link of links) {
    const a = document.createElement('a');
    a.href = link.url;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.textContent = link.label || link.url;
    dd.appendChild(a);
    dd.appendChild(document.createElement('br'));
  }
}

// ---- track (IGC) ----

const SEGMENT_KINDS_TO_SHADE = new Set(['thermal', 'glide']);

let trackMap;
let trackPolyline;
let barogramChart;

function trackColors() {
  const styles = getComputedStyle(document.documentElement);
  return {
    thermal: styles.getPropertyValue('--warm').trim() || '#f6ad55',
    glide: styles.getPropertyValue('--accent-strong').trim() || '#63b3ed',
    neutral: styles.getPropertyValue('--text-dim').trim() || '#94a3b8',
  };
}

function fmtTrackDuration(seconds) {
  if (seconds == null) return notRecorded();
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${String(m).padStart(2, '0')}min` : `${m} min`;
}

function fmtRate(value) {
  return value == null ? notRecorded() : `${value.toFixed(1)} m/s`;
}

function showTrackAlert(message) {
  const box = el('trackAlert');
  box.textContent = message;
  box.classList.add('visible');
}

function clearTrackAlert() {
  el('trackAlert').classList.remove('visible');
}

async function loadTrack(flightId) {
  const res = await fetchAuth(`/api/flights/${flightId}/igc`);
  if (res.status === 404) return null;
  if (!res.ok) {
    console.error(`[FL:flight-detail] failed to load track (${res.status})`);
    return null;
  }
  return res.json();
}

function renderTrackFigures(track) {
  el('t_duration').textContent = fmtTrackDuration(track.duration_s);
  el('t_distance').textContent = fmtNumber(track.distance_km, 'km');
  el('t_maxalt').textContent = fmtNumber(track.max_alt_igc_m, 'm');
  el('t_altgain').textContent = fmtNumber(track.alt_gain_igc_m, 'm');
  el('t_thermals').textContent = track.thermal_count ?? notRecorded();
  el('t_bestclimb').textContent = fmtRate(track.best_climb_ms);
  el('t_peakclimb').textContent = fmtRate(track.peak_climb_ms);
  el('t_glideratio').textContent = track.glide_ratio != null ? track.glide_ratio.toFixed(1) : notRecorded();
  el('t_altsource').textContent =
    track.alt_source === 'PRESS'
      ? window.t('flight_detail.track_alt_source_press')
      : track.alt_source === 'GNSS'
        ? window.t('flight_detail.track_alt_source_gnss')
        : notRecorded();
}

async function renderTrackMap(flightId) {
  const res = await fetchAuth(`/api/flights/${flightId}/igc/track.geojson`);
  if (!res.ok) {
    console.error(`[FL:flight-detail] failed to load track.geojson (${res.status})`);
    return null;
  }
  const geojson = await res.json();

  if (!trackMap) {
    trackMap = L.map('trackMap');
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(trackMap);
  }
  if (trackPolyline) trackMap.removeLayer(trackPolyline);

  const latlngs = geojson.geometry.coordinates.map(([lon, lat]) => [lat, lon]);
  trackPolyline = L.polyline(latlngs, { color: trackColors().glide, weight: 3 }).addTo(trackMap);
  trackMap.fitBounds(trackPolyline.getBounds(), { padding: [20, 20] });

  return geojson;
}

async function renderBarogram(flightId, geojson) {
  const res = await fetchAuth(`/api/flights/${flightId}/igc/segments`);
  const segments = res.ok ? await res.json() : [];
  if (!res.ok) console.error(`[FL:flight-detail] failed to load segments (${res.status})`);

  const shaded = segments.filter((s) => SEGMENT_KINDS_TO_SHADE.has(s.kind));
  const colors = trackColors();

  const offsets = geojson.properties.offsets_s;
  const altitudes = geojson.geometry.coordinates.map((c) => c[2]);
  const pointColors = offsets.map((offset) => {
    const seg = shaded.find(
      (s) => offset >= s.start_offset_s && offset <= s.start_offset_s + (s.duration_s || 0),
    );
    return seg ? colors[seg.kind] : colors.neutral;
  });

  if (barogramChart) barogramChart.destroy();
  barogramChart = new Chart(el('barogram').getContext('2d'), {
    type: 'line',
    data: {
      labels: offsets,
      datasets: [
        {
          data: altitudes,
          borderWidth: 2,
          pointRadius: 0,
          tension: 0,
          fill: false,
          segment: {
            borderColor: (ctx) => pointColors[ctx.p0DataIndex] || colors.neutral,
          },
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { title: { display: true, text: window.t('flight_detail.track_chart_x') } },
        y: { title: { display: true, text: window.t('flight_detail.track_chart_y') } },
      },
    },
  });
  console.log(`[FL:flight-detail] barogram rendered: ${offsets.length} points, ${shaded.length} shaded segments`);
}

async function renderTrack(flightId, track) {
  el('trackCard').hidden = false;
  clearTrackAlert();

  if (!track) {
    el('trackEmpty').hidden = false;
    el('trackPresent').hidden = true;
    return;
  }

  el('trackEmpty').hidden = true;
  el('trackPresent').hidden = false;
  renderTrackFigures(track);
  const geojson = await renderTrackMap(flightId);
  if (geojson) await renderBarogram(flightId, geojson);
}

async function uploadTrack(flightId, file) {
  clearTrackAlert();
  const body = new FormData();
  body.append('file', file);
  console.log(`[FL:flight-detail] POST /api/flights/${flightId}/igc (${file.name}, ${file.size}B)`);
  const res = await fetchAuth(`/api/flights/${flightId}/igc`, { method: 'POST', body });
  if (!res.ok) {
    showTrackAlert(await errorMessage(res));
    console.error(`[FL:flight-detail] track upload failed (${res.status})`);
    return;
  }
  const track = await res.json();
  await renderTrack(flightId, track);
  console.log(`[FL:flight-detail] track uploaded: ${track.id}`);
}

async function detachTrack(flightId) {
  const res = await fetchAuth(`/api/flights/${flightId}/igc`, { method: 'DELETE' });
  if (!res.ok) {
    showTrackAlert(await errorMessage(res));
    console.error(`[FL:flight-detail] track detach failed (${res.status})`);
    return;
  }
  el('trackDetachConfirm').hidden = true;
  await renderTrack(flightId, null);
  console.log(`[FL:flight-detail] track detached for flight ${flightId}`);
}

function wireTrackEvents(flightId) {
  el('trackUploadBtn').addEventListener('click', () => {
    const file = el('trackFile').files[0];
    if (!file) {
      showTrackAlert(window.t('flight_detail.track_no_file'));
      return;
    }
    uploadTrack(flightId, file);
  });

  el('trackReplaceBtn').addEventListener('click', () => {
    const file = el('trackReplaceFile').files[0];
    if (!file) {
      showTrackAlert(window.t('flight_detail.track_no_file'));
      return;
    }
    uploadTrack(flightId, file);
  });

  el('trackDetachBtn').addEventListener('click', () => {
    el('trackDetachConfirm').hidden = false;
  });
  el('trackDetachNo').addEventListener('click', () => {
    el('trackDetachConfirm').hidden = true;
  });
  el('trackDetachYes').addEventListener('click', () => detachTrack(flightId));
}

async function init() {
  await bootstrapPage({ page: 'flights', requireAuth: true });
  await loadRefData();

  const id = flightIdFromUrl();
  console.log(`[FL:flight-detail] loading flight ${id}`);
  const flight = await loadFlight(id);
  if (!flight) return;
  render(flight);

  wireTrackEvents(id);
  const track = await loadTrack(id);
  await renderTrack(id, track);
}

init();
