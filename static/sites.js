/**
 * /sites — the site catalogue plus a Leaflet map for placing/moving pins.
 * Leaflet is self-hosted under /static/vendor/leaflet (03-frontend-conventions.md — no CDN,
 * CSP script-src 'self' would block one anyway). Tiles come from the public OSM raster server;
 * that's an <img> load, not a script, so CSP's img-src 'self' data: https: already allows it
 * (see specs/002-flight-log-ui/research.md).
 *
 * Editing lives in a drawer (name/flags/region/elevation/coordinates), not on the row click —
 * a site with an existing pin still needs a way back into "place mode", and a manual lat/lon
 * fallback matters because the map's own marker rendering is one more thing that can fail
 * (network, browser extension, tile host) independently of whether the coordinates are right.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';
import { loadRefData, getRegions, regionName } from '/static/refdata.js';

const DEFAULT_CENTER = [46.68, 7.85]; // Bernese Oberland — this pilot's home flying area
const DEFAULT_ZOOM = 10;

const el = (id) => document.getElementById(id);

let map;
let landingIcon; // set in initMap() — green pin for landing-only sites
let markers = new Map(); // site id -> Leaflet marker (confirmed, saved position)
let pickerMarker = null; // preview marker for a not-yet-saved pick, while the drawer is open
let sites = [];
let editingId = null;
let pickerArmed = false;

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

function initMap() {
  // Explicit, not auto-detected: Leaflet's CSS-background-image detection is unreliable
  // and we vendor the marker images ourselves rather than pulling them from a CDN.
  //
  // IconDefault._getIconUrl() unconditionally returns
  // `(this.options.imagePath || <CSS-sniffed path>) + <name>Url`  — it has no "this is
  // already absolute" mode. Passing full absolute paths as iconUrl/iconRetinaUrl/shadowUrl
  // (as this used to) doesn't disable that prefixing, it just means the prefix lands in
  // front of an already-absolute path: on a retina display this produced
  // "/static/vendor/leaflet/images//static/vendor/leaflet/images/marker-icon-2x.png" — a
  // 404, silently broken (the icon and shadow, whose lookups both go through the retina
  // branch or plain Url fallback; the non-retina iconUrl name is never requested on a
  // retina display, which is why only *-2x.png and shadow ever appeared in the console).
  // Setting `imagePath` explicitly and leaving the three Url options as bare filenames
  // (Leaflet's own default shape) lets `imagePath + name` compose correctly instead.
  L.Icon.Default.mergeOptions({
    imagePath: '/static/vendor/leaflet/images/',
    iconUrl: 'marker-icon.png',
    iconRetinaUrl: 'marker-icon-2x.png',
    shadowUrl: 'marker-shadow.png',
  });

  // Landing-only sites get a green pin instead of the default blue — same teardrop shape as
  // Leaflet's vendored marker-icon.png, drawn as inline SVG so no new binary asset is needed.
  // A site that's both launch and landing keeps the default blue marker (launch takes
  // priority), so "launches stay blue" holds even for a dual-role site.
  landingIcon = L.divIcon({
    className: 'site-pin site-pin-landing',
    html: '<svg width="25" height="41" viewBox="0 0 25 41" xmlns="http://www.w3.org/2000/svg">'
      + '<path d="M12.5 0C5.6 0 0 5.6 0 12.5c0 9.4 12.5 28.5 12.5 28.5S25 21.9 25 12.5C25 5.6 19.4 0 12.5 0z" '
      + 'style="fill:var(--success)" stroke="#1a1a1a" stroke-width="1"/>'
      + '<circle cx="12.5" cy="12.5" r="5" fill="#fff"/></svg>',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    tooltipAnchor: [1, -34],
  });

  map = L.map('siteMap').setView(DEFAULT_CENTER, DEFAULT_ZOOM);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19,
  }).addTo(map);

  map.on('click', (event) => {
    if (!pickerArmed) return;
    const { lat, lng } = event.latlng;
    console.log(`[FL:sites] picked ${lat}, ${lng}`);
    setPickedCoords(lat, lng);
    disarmPicker();
  });
}

function armPicker() {
  pickerArmed = true;
  el('siteMap').classList.add('armed');
  el('pickHint').hidden = false;
  // The drawer overlay is a fixed, full-viewport layer that sits above the map (same
  // stacking context, higher z-index) and closes the drawer on click — left in place, a
  // map click while armed would hit the overlay first and discard the edit instead of
  // picking a point. Hide it only for the duration of picking; the drawer itself (a
  // separate, higher layer) stays open and interactive throughout.
  el('drawerOverlay').hidden = true;
}

function disarmPicker() {
  pickerArmed = false;
  el('siteMap').classList.remove('armed');
  el('pickHint').hidden = true;
  if (!el('siteDrawer').hidden) el('drawerOverlay').hidden = false;
}

function setPickedCoords(lat, lon) {
  el('s_lat').value = lat.toFixed(6);
  el('s_lon').value = lon.toFixed(6);
  showPickerMarker(lat, lon);
}

// The confirmed marker (from `markers`) and the picker preview are two different Leaflet
// markers; showing both at once for the site being edited would draw two overlapping pins.
// Hide the confirmed one for the duration of the edit — restored in closeDrawer().
function hideConfirmedMarker() {
  markers.get(editingId)?.setOpacity(0);
}

function showPickerMarker(lat, lon) {
  if (lat == null || lon == null) {
    if (pickerMarker) {
      map.removeLayer(pickerMarker);
      pickerMarker = null;
    }
    return;
  }
  hideConfirmedMarker();
  if (pickerMarker) {
    pickerMarker.setLatLng([lat, lon]);
  } else {
    pickerMarker = L.marker([lat, lon], { draggable: true, opacity: 0.75 }).addTo(map);
    pickerMarker.on('dragend', () => {
      const { lat: dLat, lng: dLng } = pickerMarker.getLatLng();
      el('s_lat').value = dLat.toFixed(6);
      el('s_lon').value = dLng.toFixed(6);
    });
  }
  map.panTo([lat, lon]);
}

// Launch (or launch+landing) keeps Leaflet's default blue pin; landing-only gets the green one.
function iconForSite(site) {
  return site.is_launch ? undefined : landingIcon;
}

function addOrMoveMarker(site) {
  if (site.lat == null || site.lon == null) return;
  let marker = markers.get(site.id);
  if (marker) {
    marker.setLatLng([site.lat, site.lon]);
    marker.setIcon(iconForSite(site) || new L.Icon.Default());
    return;
  }
  marker = L.marker([site.lat, site.lon], { icon: iconForSite(site) });
  // Leaflet's bindTooltip(string) sets innerHTML internally — site.name is free-text user
  // data, so pass a DOM node built with textContent instead, per 03-frontend-conventions.md.
  const tooltipNode = document.createElement('span');
  tooltipNode.textContent = site.name;
  marker.bindTooltip(tooltipNode);
  marker.addTo(map);
  markers.set(site.id, marker);
}

function removeMarker(siteId) {
  const marker = markers.get(siteId);
  if (marker) {
    map.removeLayer(marker);
    markers.delete(siteId);
  }
}

function renderTable() {
  const tbody = el('sitesBody');
  tbody.innerHTML = '';

  for (const site of sites) {
    const tr = document.createElement('tr');
    tr.dataset.id = site.id;

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

    const actionTd = document.createElement('td');
    const editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.className = 'btn-ghost';
    editBtn.textContent = window.t('sites.edit');
    editBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      openDrawer(site);
    });
    actionTd.appendChild(editBtn);
    tr.appendChild(actionTd);

    tr.addEventListener('click', () => {
      if (site.lat != null && site.lon != null) {
        map.panTo([site.lat, site.lon]);
        markers.get(site.id)?.openTooltip();
      }
    });

    tbody.appendChild(tr);
  }
}

// ---- drawer ----

function clearFieldErrors() {
  document.querySelectorAll('#siteForm .field-error').forEach((p) => (p.textContent = ''));
  el('drawerAlert').classList.remove('visible');
}

function populateRegionOptions() {
  const select = el('s_region');
  const placeholder = select.querySelector('option[value=""]');
  select.innerHTML = '';
  select.appendChild(placeholder);
  for (const region of getRegions()) {
    const opt = document.createElement('option');
    opt.value = region.id;
    opt.textContent = region.name;
    select.appendChild(opt);
  }
}

function openDrawer(site) {
  editingId = site.id;
  clearFieldErrors();
  disarmPicker();
  el('deleteConfirm').hidden = true;
  populateRegionOptions();

  el('drawerTitle').textContent = window.t('sites.drawer.edit_title');
  el('drawerDelete').hidden = false;

  el('s_id').value = site.id;
  el('s_name').value = site.name;
  el('s_launch').checked = site.is_launch;
  el('s_landing').checked = site.is_landing;
  el('s_region').value = site.region_id || '';
  el('s_elevation').value = site.elevation_m ?? '';
  el('s_lat').value = site.lat ?? '';
  el('s_lon').value = site.lon ?? '';

  // Pan to the existing pin without drawing a second (picker) marker on top of it — the
  // picker only appears once the coordinates actually change (pick, drag, or manual edit).
  if (site.lat != null && site.lon != null) map.panTo([site.lat, site.lon]);

  el('drawerOverlay').hidden = false;
  el('siteDrawer').hidden = false;
  el('siteDrawer').setAttribute('aria-hidden', 'false');
  console.log(`[FL:sites] drawer opened (edit ${site.id})`);
  el('s_name').focus();
}

function closeDrawer() {
  disarmPicker();
  showPickerMarker(null, null);
  markers.get(editingId)?.setOpacity(1);
  el('drawerOverlay').hidden = true;
  el('siteDrawer').hidden = true;
  el('siteDrawer').setAttribute('aria-hidden', 'true');
  editingId = null;
  console.log('[FL:sites] drawer closed');
}

// Plain text inputs, not type="number": a browser set to a comma-decimal locale (common
// for a Swiss user) silently reports "" for "46,4" typed into a number input, which would
// turn into a null coordinate — i.e. quietly unpin the site on save. Comma is accepted here
// and normalised to a dot before parsing.
function parseCoord(raw) {
  const trimmed = raw.trim().replace(',', '.');
  if (trimmed === '') return null;
  const value = Number(trimmed);
  return Number.isFinite(value) ? value : null;
}

function readFormPayload() {
  return {
    name: el('s_name').value.trim(),
    is_launch: el('s_launch').checked,
    is_landing: el('s_landing').checked,
    region_id: el('s_region').value || null,
    elevation_m: el('s_elevation').value === '' ? null : Number(el('s_elevation').value),
    lat: parseCoord(el('s_lat').value),
    lon: parseCoord(el('s_lon').value),
  };
}

function renderFieldErrors(details) {
  const errors = details?.errors || [];
  for (const err of errors) {
    const field = err.loc?.[err.loc.length - 1];
    const target = document.querySelector(`#siteForm .field-error[data-field="${field}"]`);
    if (target) target.textContent = err.msg;
    console.warn(`[FL:sites] validation error on ${field}: ${err.msg}`);
  }
  if (errors.length === 0) {
    el('drawerAlert').textContent = window.t('common.error_generic');
    el('drawerAlert').classList.add('visible');
  }
}

function upsertSiteInPlace(site) {
  const idx = sites.findIndex((s) => s.id === site.id);
  if (idx >= 0) sites[idx] = site;
  else sites.push(site);
}

async function submitSite(event) {
  event.preventDefault();
  clearFieldErrors();
  if (!el('s_launch').checked && !el('s_landing').checked) {
    el('drawerAlert').textContent = window.t('sites.drawer.needs_launch_or_landing');
    el('drawerAlert').classList.add('visible');
    return;
  }

  const saveBtn = el('drawerSave');
  saveBtn.disabled = true;

  const payload = readFormPayload();
  const url = `/api/sites/${editingId}`;
  console.log(`[FL:sites] PUT ${url}`, payload);

  try {
    const res = await fetchAuth(url, { method: 'PUT', body: JSON.stringify(payload) });
    if (!res.ok) {
      let details;
      try {
        details = (await res.json())?.error?.details;
      } catch {
        details = null;
      }
      if (res.status === 422 && details) {
        renderFieldErrors(details);
      } else {
        el('drawerAlert').textContent = await errorMessage(res);
        el('drawerAlert').classList.add('visible');
      }
      console.error(`[FL:sites] save failed (${res.status})`);
      return;
    }

    const saved = await res.json();
    upsertSiteInPlace(saved);
    addOrMoveMarker(saved);
    if (saved.lat == null || saved.lon == null) removeMarker(saved.id);
    renderTable();
    closeDrawer();
    console.log(`[FL:sites] site updated: ${saved.id}`);
  } catch (err) {
    console.error('[FL:sites] save request failed', err);
    el('drawerAlert').textContent = window.t('common.error_generic');
    el('drawerAlert').classList.add('visible');
  } finally {
    saveBtn.disabled = false;
  }
}

async function deleteSite() {
  if (!editingId) return;
  const id = editingId;
  console.log(`[FL:sites] deleting site ${id}`);
  const res = await fetchAuth(`/api/sites/${id}`, { method: 'DELETE' });
  if (!res.ok) {
    el('drawerAlert').textContent = await errorMessage(res);
    el('drawerAlert').classList.add('visible');
    console.error(`[FL:sites] delete failed (${res.status})`);
    return;
  }
  sites = sites.filter((s) => s.id !== id);
  removeMarker(id);
  renderTable();
  closeDrawer();
  console.log(`[FL:sites] site deleted: ${id}`);
}

function wireEvents() {
  el('drawerClose').addEventListener('click', closeDrawer);
  el('drawerOverlay').addEventListener('click', closeDrawer);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !el('siteDrawer').hidden) closeDrawer();
  });

  el('siteForm').addEventListener('submit', submitSite);

  el('pickOnMap').addEventListener('click', armPicker);

  const onCoordInput = () => {
    const lat = parseCoord(el('s_lat').value);
    const lon = parseCoord(el('s_lon').value);
    if (lat != null && lon != null) showPickerMarker(lat, lon);
  };
  el('s_lat').addEventListener('change', onCoordInput);
  el('s_lon').addEventListener('change', onCoordInput);

  el('drawerDelete').addEventListener('click', () => {
    el('deleteConfirm').hidden = false;
  });
  el('deleteConfirmNo').addEventListener('click', () => {
    el('deleteConfirm').hidden = true;
  });
  el('deleteConfirmYes').addEventListener('click', deleteSite);
}

async function init() {
  await bootstrapPage({ page: 'sites', requireAuth: true });
  await loadRefData();

  initMap();
  wireEvents();
  sites = await loadSites();
  for (const site of sites) addOrMoveMarker(site);
  renderTable();
}

init();
