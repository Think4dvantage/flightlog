/**
 * /sites — the site catalogue plus a Leaflet map for placing/moving pins.
 * Leaflet is self-hosted under /static/vendor/leaflet (03-frontend-conventions.md — no CDN,
 * CSP script-src 'self' would block one anyway). Tiles come from the public OSM raster server;
 * that's an <img> load, not a script, so CSP's img-src 'self' data: https: already allows it
 * (see specs/002-flight-log-ui/research.md).
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';
import { loadRefData, regionName } from '/static/refdata.js';

const DEFAULT_CENTER = [46.68, 7.85]; // Bernese Oberland — this pilot's home flying area
const DEFAULT_ZOOM = 10;

const el = (id) => document.getElementById(id);

let map;
let markers = new Map(); // site id -> Leaflet marker
let sites = [];
let armedSiteId = null; // site id awaiting a map click to place its first pin

function showAlert(message) {
  el('alert').textContent = message;
  el('alert').classList.add('visible');
  console.error(`[FL:sites] ${message}`);
}

async function loadSites() {
  const started = performance.now();
  const res = await fetchAuth('/api/sites');
  if (!res.ok) {
    showAlert(await errorMessage(res));
    return [];
  }
  const list = await res.json();
  console.log(`[FL:sites] loaded ${list.length} sites in ${(performance.now() - started).toFixed(0)}ms`);
  return list;
}

async function updateSiteCoords(siteId, lat, lon) {
  console.log(`[FL:sites] PUT /api/sites/${siteId} lat=${lat} lon=${lon}`);
  const res = await fetchAuth(`/api/sites/${siteId}`, {
    method: 'PUT',
    body: JSON.stringify({ lat, lon }),
  });
  if (!res.ok) {
    showAlert(await errorMessage(res));
    return null;
  }
  return res.json();
}

function initMap() {
  // Explicit, not auto-detected: Leaflet's CSS-background-image detection is unreliable
  // and we vendor the marker images ourselves rather than pulling them from a CDN.
  L.Icon.Default.mergeOptions({
    iconUrl: '/static/vendor/leaflet/images/marker-icon.png',
    iconRetinaUrl: '/static/vendor/leaflet/images/marker-icon-2x.png',
    shadowUrl: '/static/vendor/leaflet/images/marker-shadow.png',
  });

  map = L.map('siteMap').setView(DEFAULT_CENTER, DEFAULT_ZOOM);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19,
  }).addTo(map);

  map.on('click', async (event) => {
    if (!armedSiteId) return;
    const site = sites.find((s) => s.id === armedSiteId);
    const { lat, lng } = event.latlng;
    console.log(`[FL:sites] placing pin for ${site.name} at ${lat}, ${lng}`);
    const updated = await updateSiteCoords(armedSiteId, lat, lng);
    disarm();
    if (updated) {
      Object.assign(site, updated);
      addOrMoveMarker(site);
      renderTable();
    }
  });
}

function disarm() {
  armedSiteId = null;
  el('siteMap').classList.remove('armed');
}

function addOrMoveMarker(site) {
  if (site.lat == null || site.lon == null) return;
  let marker = markers.get(site.id);
  if (marker) {
    marker.setLatLng([site.lat, site.lon]);
    return;
  }
  marker = L.marker([site.lat, site.lon], { draggable: true });
  // Leaflet's bindTooltip(string) sets innerHTML internally — site.name is free-text user
  // data, so pass a DOM node built with textContent instead, per 03-frontend-conventions.md.
  const tooltipNode = document.createElement('span');
  tooltipNode.textContent = site.name;
  marker.bindTooltip(tooltipNode);
  marker.on('dragend', async () => {
    const { lat, lng } = marker.getLatLng();
    const updated = await updateSiteCoords(site.id, lat, lng);
    if (updated) {
      Object.assign(site, updated);
      renderTable();
    } else {
      marker.setLatLng([site.lat, site.lon]); // revert on failure
    }
  });
  marker.addTo(map);
  markers.set(site.id, marker);
}

function renderTable() {
  const tbody = el('sitesBody');
  tbody.innerHTML = '';

  for (const site of sites) {
    const tr = document.createElement('tr');
    if (site.id === armedSiteId) tr.classList.add('row-highlight');

    const nameTd = document.createElement('td');
    nameTd.textContent = site.name;
    tr.appendChild(nameTd);

    const launchTd = document.createElement('td');
    launchTd.textContent = site.is_launch ? '✓' : '';
    tr.appendChild(launchTd);

    const landingTd = document.createElement('td');
    landingTd.textContent = site.is_landing ? '✓' : '';
    tr.appendChild(landingTd);

    const regionTd = document.createElement('td');
    regionTd.textContent = regionName(site.region_id) || '—';
    tr.appendChild(regionTd);

    const elevTd = document.createElement('td');
    elevTd.textContent = site.elevation_m != null ? `${site.elevation_m} m` : '—';
    tr.appendChild(elevTd);

    const coordTd = document.createElement('td');
    if (site.lat != null && site.lon != null) {
      coordTd.textContent = `${site.lat.toFixed(4)}, ${site.lon.toFixed(4)}`;
    } else {
      coordTd.textContent = window.t('sites.unpinned');
      tr.classList.add('retired'); // reuse the muted-row style for "not yet placed"
    }
    tr.appendChild(coordTd);

    tr.addEventListener('click', () => {
      if (site.lat != null && site.lon != null) {
        map.panTo([site.lat, site.lon]);
        markers.get(site.id)?.openTooltip();
        return;
      }
      armedSiteId = armedSiteId === site.id ? null : site.id;
      el('siteMap').classList.toggle('armed', Boolean(armedSiteId));
      console.log(`[FL:sites] ${armedSiteId ? 'armed' : 'disarmed'} pin placement for ${site.name}`);
      renderTable();
    });

    tbody.appendChild(tr);
  }
}

async function init() {
  await bootstrapPage({ page: 'sites', requireAuth: true });
  await loadRefData();

  initMap();
  sites = await loadSites();
  for (const site of sites) addOrMoveMarker(site);
  renderTable();
}

init();
