/**
 * /public/flights/{id} — anonymous-visitor view of a single unlisted-or-public flight
 * (v0.9). Deliberately built without any assumption of a logged-in session: bootstrapPage
 * is called with `anonymous: true`, which skips the token check entirely — a visitor's own
 * (possibly stale) localStorage token must never trigger a redirect-to-/login on this page,
 * and a visitor who is logged in as some other pilot in this browser must never see that
 * identity surfaced here (FR-013). A private or nonexistent flight both 404 identically —
 * see api/routers/public.py.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { errorMessage } from '/static/auth.js';

const el = (id) => document.getElementById(id);

function flightIdFromUrl() {
  const parts = window.location.pathname.split('/').filter(Boolean);
  return parts[parts.length - 1];
}

function notRecorded() {
  return window.t('public_flight.not_recorded');
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

function fmtTrackDuration(seconds) {
  if (seconds == null) return notRecorded();
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${String(m).padStart(2, '0')}min` : `${m} min`;
}

function fmtRate(value) {
  return value == null ? notRecorded() : `${value.toFixed(1)} m/s`;
}

const SEGMENT_KINDS_TO_SHADE = new Set(['thermal', 'glide']);

function trackColors() {
  const styles = getComputedStyle(document.documentElement);
  return {
    thermal: styles.getPropertyValue('--warm').trim() || '#f6ad55',
    glide: styles.getPropertyValue('--accent-strong').trim() || '#63b3ed',
    neutral: styles.getPropertyValue('--text-dim').trim() || '#94a3b8',
  };
}

async function loadFlight(id) {
  const started = performance.now();
  const res = await fetch(`/api/public/flights/${id}`);
  console.log(`[FL:public-flight] GET /api/public/flights/${id} → ${res.status} (${(performance.now() - started).toFixed(0)}ms)`);
  if (!res.ok) {
    el('alert').textContent = await errorMessage(res);
    el('alert').classList.add('visible');
    return null;
  }
  return res.json();
}

function renderTrackFigures(igc) {
  el('t_duration').textContent = fmtTrackDuration(igc.duration_s);
  el('t_distance').textContent = fmtNumber(igc.distance_km, 'km');
  el('t_maxalt').textContent = fmtNumber(igc.max_alt_igc_m, 'm');
  el('t_altgain').textContent = fmtNumber(igc.alt_gain_igc_m, 'm');
  el('t_thermals').textContent = igc.thermal_count ?? notRecorded();
  el('t_bestclimb').textContent = fmtRate(igc.best_climb_ms);
  el('t_peakclimb').textContent = fmtRate(igc.peak_climb_ms);
  el('t_glideratio').textContent = igc.glide_ratio != null ? igc.glide_ratio.toFixed(1) : notRecorded();
  el('t_altsource').textContent =
    igc.alt_source === 'PRESS'
      ? window.t('flight_detail.track_alt_source_press')
      : igc.alt_source === 'GNSS'
        ? window.t('flight_detail.track_alt_source_gnss')
        : notRecorded();
}

function renderTrackMap(igc) {
  const trackMap = L.map('trackMap');
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19,
  }).addTo(trackMap);

  const latlngs = igc.geometry.coordinates.map(([lon, lat]) => [lat, lon]);
  const polyline = L.polyline(latlngs, { color: trackColors().glide, weight: 3 }).addTo(trackMap);
  trackMap.fitBounds(polyline.getBounds(), { padding: [20, 20] });
}

function renderBarogram(igc) {
  const shaded = igc.segments.filter((s) => SEGMENT_KINDS_TO_SHADE.has(s.kind));
  const colors = trackColors();

  const offsets = igc.offsets_s;
  const altitudes = igc.geometry.coordinates.map((c) => c[2]);
  const pointColors = offsets.map((offset) => {
    const seg = shaded.find(
      (s) => offset >= s.start_offset_s && offset <= s.start_offset_s + (s.duration_s || 0),
    );
    return seg ? colors[seg.kind] : colors.neutral;
  });

  new Chart(el('barogram').getContext('2d'), {
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
  console.log(`[FL:public-flight] barogram rendered: ${offsets.length} points, ${shaded.length} shaded segments`);
}

function renderTrack(igc) {
  if (!igc) {
    el('trackCard').hidden = true;
    return;
  }
  el('trackCard').hidden = false;
  renderTrackFigures(igc);
  renderTrackMap(igc);
  renderBarogram(igc);
  console.log(`[FL:public-flight] track rendered: ${igc.offsets_s.length} points, ${igc.segments.length} segments`);
}

function render(flight) {
  // nickname / owner_display_name / site / category names are user data — textContent only,
  // never innerHTML.
  el('d_date').textContent = flight.nickname
    ? `${flight.nickname} — ${fmtDate(flight.flight_date)}`
    : fmtDate(flight.flight_date);
  el('d_owner').textContent = window.t('public_flight.shared_by', { name: flight.owner_display_name });

  el('d_launch').textContent = flight.launch_site_name || notRecorded();
  el('d_landing').textContent = flight.landing_site_name || notRecorded();
  el('d_category').textContent = flight.category_name || notRecorded();

  el('d_duration').textContent = fmtDuration(flight.duration_min);
  el('d_distance').textContent = fmtNumber(flight.distance_km, 'km');
  el('d_maxalt').textContent = fmtNumber(flight.max_alt_m, 'm');
  el('d_altgain').textContent = fmtNumber(flight.alt_gain_m, 'm');
  el('d_totaldescent').textContent = fmtNumber(flight.total_descent_m, 'm');

  el('d_technique').textContent = flight.launch_technique
    ? window.t(`public_flight.technique_${flight.launch_technique}`)
    : notRecorded();

  el('d_notes').textContent = flight.notes || notRecorded();

  const profileLink = el('d_profile_link');
  if (flight.owner_has_public_profile) {
    profileLink.hidden = false;
    profileLink.textContent = '';
    const a = document.createElement('a');
    a.href = `/public/profiles/${flight.owner_id}`;
    a.textContent = window.t('public_flight.view_profile', { name: flight.owner_display_name });
    profileLink.appendChild(a);
  } else {
    profileLink.hidden = true;
  }

  el('detailBody').hidden = false;
  renderTrack(flight.igc);
}

async function init() {
  await bootstrapPage({ page: 'public-flight', anonymous: true });

  const id = flightIdFromUrl();
  console.log(`[FL:public-flight] loading flight ${id}`);
  const flight = await loadFlight(id);
  if (!flight) return;
  render(flight);
}

init();
