/**
 * /flights — browse, search, filter, sort, paginate; add/edit/delete via a drawer.
 * See .ai/instructions/03-frontend-conventions.md for the logging/i18n/XSS rules this follows.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';
import {
  loadRefData,
  getSites,
  getGliders,
  getHarnesses,
  getCategories,
  getBuddies,
  getRegions,
  siteName,
  gliderName,
  harnessName,
  categoryName,
  siteRegionName,
} from '/static/refdata.js';

const PAGE_SIZE = 50;

let allFlights = [];
let filtered = [];
let sortKey = 'flight_date';
let sortDir = 'desc';
let page = 1;
let editingId = null;

const el = (id) => document.getElementById(id);

function setSelectOptions(select, items, { value = 'id', label, placeholderKey } = {}) {
  const placeholder = select.querySelector('option[value=""]');
  select.innerHTML = '';
  if (placeholder) select.appendChild(placeholder);
  else if (placeholderKey) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.setAttribute('data-i18n', placeholderKey);
    opt.textContent = window.t(placeholderKey);
    select.appendChild(opt);
  }
  for (const item of items) {
    const opt = document.createElement('option');
    opt.value = item.id;
    opt.textContent = label(item);
    select.appendChild(opt);
  }
}

// ---- load ----

async function loadFlights() {
  const started = performance.now();
  const res = await fetchAuth('/api/flights');
  if (!res.ok) {
    showAlert(await errorMessage(res));
    console.error(`[FL:flights] failed to load flights (${res.status})`);
    return [];
  }
  const flights = await res.json();
  console.log(
    `[FL:flights] loaded ${flights.length} flights in ${(performance.now() - started).toFixed(0)}ms`,
  );
  for (const f of flights) {
    f._launch = siteName(f.launch_site_id) || '';
    f._landing = siteName(f.landing_site_id) || '';
    f._category = categoryName(f.category_id) || '';
    f._glider = gliderName(f.glider_id) || '';
    f._region = siteRegionName(f.launch_site_id) || '';
    f._year = new Date(f.flight_date).getUTCFullYear();
  }
  return flights;
}

// ---- filters ----

function populateFilterOptions() {
  const years = [...new Set(allFlights.map((f) => f._year))].sort((a, b) => b - a);
  setSelectOptions(el('filterYear'), years.map((y) => ({ id: y })), { label: (y) => String(y.id) });

  setSelectOptions(el('filterCategory'), getCategories(), { label: (c) => c.name });
  setSelectOptions(el('filterGlider'), getGliders(), { label: (g) => gliderName(g.id) });
  setSelectOptions(
    el('filterSite'),
    getSites().filter((s) => s.is_launch),
    { label: (s) => s.name },
  );
  setSelectOptions(el('filterRegion'), getRegions(), { label: (r) => r.name });
}

function readFiltersFromUrl() {
  const params = new URLSearchParams(window.location.search);
  el('searchInput').value = params.get('q') || '';
  el('filterYear').value = params.get('year') || '';
  el('filterCategory').value = params.get('category') || '';
  el('filterGlider').value = params.get('glider') || '';
  el('filterSite').value = params.get('site') || '';
  el('filterRegion').value = params.get('region') || '';
  sortKey = params.get('sort') || 'flight_date';
  sortDir = params.get('dir') || 'desc';
  page = Number(params.get('page')) || 1;
}

function writeFiltersToUrl() {
  const params = new URLSearchParams();
  const q = el('searchInput').value.trim();
  if (q) params.set('q', q);
  if (el('filterYear').value) params.set('year', el('filterYear').value);
  if (el('filterCategory').value) params.set('category', el('filterCategory').value);
  if (el('filterGlider').value) params.set('glider', el('filterGlider').value);
  if (el('filterSite').value) params.set('site', el('filterSite').value);
  if (el('filterRegion').value) params.set('region', el('filterRegion').value);
  if (sortKey !== 'flight_date' || sortDir !== 'desc') {
    params.set('sort', sortKey);
    params.set('dir', sortDir);
  }
  if (page !== 1) params.set('page', String(page));
  const qs = params.toString();
  history.replaceState(null, '', qs ? `?${qs}` : window.location.pathname);
}

function matchesSearch(flight, term) {
  if (!term) return true;
  const haystack = [flight._launch, flight._landing, flight._category, flight._glider, flight.notes]
    .join(' ')
    .toLowerCase();
  return haystack.includes(term);
}

function applyFiltersAndSort({ resetPage = false } = {}) {
  const term = el('searchInput').value.trim().toLowerCase();
  const year = el('filterYear').value;
  const category = el('filterCategory').value;
  const glider = el('filterGlider').value;
  const site = el('filterSite').value;
  const region = el('filterRegion').value;

  filtered = allFlights.filter((f) => {
    if (year && String(f._year) !== year) return false;
    if (category && f.category_id !== category) return false;
    if (glider && f.glider_id !== glider) return false;
    if (site && f.launch_site_id !== site) return false;
    if (region) {
      const launchSite = getSites().find((s) => s.id === f.launch_site_id);
      if (!launchSite || launchSite.region_id !== region) return false;
    }
    if (!matchesSearch(f, term)) return false;
    return true;
  });

  filtered.sort((a, b) => {
    const ka = sortValue(a, sortKey);
    const kb = sortValue(b, sortKey);
    let cmp;
    if (ka == null && kb == null) cmp = 0;
    else if (ka == null) cmp = -1;
    else if (kb == null) cmp = 1;
    else if (typeof ka === 'string') cmp = ka.localeCompare(kb);
    else cmp = ka - kb;
    return sortDir === 'asc' ? cmp : -cmp;
  });

  if (resetPage) page = 1;
  const maxPage = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  if (page > maxPage) page = maxPage;

  console.log(
    `[FL:flights] filtered ${filtered.length}/${allFlights.length} (sort=${sortKey} ${sortDir}, page=${page})`,
  );

  writeFiltersToUrl();
  render();
}

function sortValue(flight, key) {
  switch (key) {
    case 'launch':
      return flight._launch;
    case 'landing':
      return flight._landing;
    case 'category':
      return flight._category;
    case 'glider':
      return flight._glider;
    case 'flight_date':
      return flight.flight_date;
    default:
      return flight[key];
  }
}

// ---- render ----

function fmtDuration(min) {
  if (min == null) return '';
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h > 0 ? `${h}h${String(m).padStart(2, '0')}` : `${m}min`;
}

function render() {
  const tbody = el('flightsBody');
  const start = (page - 1) * PAGE_SIZE;
  const pageRows = filtered.slice(start, start + PAGE_SIZE);

  tbody.innerHTML = '';
  for (const f of pageRows) {
    const tr = document.createElement('tr');
    tr.dataset.id = f.id;

    const cells = [
      f.flight_date,
      f._launch,
      f._landing || '—',
      f._category,
      f._glider || '—',
      fmtDuration(f.duration_min) || '—',
      f.distance_km != null ? `${f.distance_km} km` : '—',
    ];
    for (const text of cells) {
      const td = document.createElement('td');
      td.textContent = text;
      tr.appendChild(td);
    }

    const actionTd = document.createElement('td');
    const editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.className = 'btn-ghost';
    editBtn.setAttribute('data-i18n', 'flights.edit');
    editBtn.textContent = window.t('flights.edit');
    editBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      openDrawer(f);
    });
    actionTd.appendChild(editBtn);
    tr.appendChild(actionTd);

    tr.addEventListener('click', () => {
      window.location.href = `/flights/${f.id}`;
    });

    tbody.appendChild(tr);
  }

  el('emptyState').hidden = filtered.length > 0;
  el('flightsTable').hidden = filtered.length === 0;
  el('resultCount').textContent = window.t('flights.result_count', { count: filtered.length });

  document.querySelectorAll('#flightsTable th[data-sort]').forEach((th) => {
    th.classList.toggle('sorted', th.dataset.sort === sortKey);
  });

  renderPagination();
}

function renderPagination() {
  const pager = el('pagination');
  const maxPage = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  pager.innerHTML = '';
  if (maxPage <= 1) return;

  const prev = document.createElement('button');
  prev.type = 'button';
  prev.className = 'btn-ghost';
  prev.textContent = '‹';
  prev.disabled = page <= 1;
  prev.addEventListener('click', () => {
    page -= 1;
    applyFiltersAndSort();
  });
  pager.appendChild(prev);

  const label = document.createElement('span');
  label.className = 'muted';
  label.textContent = window.t('flights.page_of', { page, total: maxPage });
  pager.appendChild(label);

  const next = document.createElement('button');
  next.type = 'button';
  next.className = 'btn-ghost';
  next.textContent = '›';
  next.disabled = page >= maxPage;
  next.addEventListener('click', () => {
    page += 1;
    applyFiltersAndSort();
  });
  pager.appendChild(next);
}

function showAlert(message) {
  const box = el('alert');
  box.textContent = message;
  box.classList.add('visible');
}

// ---- drawer ----

function populateDrawerDropdowns(flight) {
  const sites = getSites();
  setSelectOptions(
    el('f_launch'),
    sites.filter((s) => s.is_launch),
    { label: (s) => s.name },
  );
  setSelectOptions(
    el('f_landing'),
    sites.filter((s) => s.is_landing),
    { label: (s) => s.name },
  );
  setSelectOptions(el('f_category'), getCategories(), { label: (c) => c.name });

  const gliders = getGliders().filter((g) => !g.retired_at || g.id === flight?.glider_id);
  setSelectOptions(el('f_glider'), gliders, { label: (g) => gliderName(g.id) });

  const harnesses = getHarnesses().filter((h) => !h.retired_at || h.id === flight?.harness_id);
  setSelectOptions(el('f_harness'), harnesses, { label: (h) => harnessName(h.id) });

  setSelectOptions(el('f_buddies'), getBuddies(), { label: (b) => b.display_name });
}

function clearFieldErrors() {
  document.querySelectorAll('#flightForm .field-error').forEach((p) => (p.textContent = ''));
  el('drawerAlert').classList.remove('visible');
}

function openDrawer(flight) {
  editingId = flight?.id || null;
  clearFieldErrors();
  el('deleteConfirm').hidden = true;
  populateDrawerDropdowns(flight);

  el('drawerTitle').textContent = window.t(
    flight ? 'flights.drawer.edit_title' : 'flights.drawer.add_title',
  );
  el('drawerDelete').hidden = !flight;

  el('f_id').value = flight?.id || '';
  el('f_date').value = flight?.flight_date || '';
  el('f_launch').value = flight?.launch_site_id || '';
  el('f_landing').value = flight?.landing_site_id || '';
  el('f_category').value = flight?.category_id || '';
  el('f_glider').value = flight?.glider_id || '';
  el('f_harness').value = flight?.harness_id || '';
  el('f_duration').value = flight?.duration_min ?? '';
  el('f_distance').value = flight?.distance_km ?? '';
  el('f_maxalt').value = flight?.max_alt_m ?? '';
  el('f_technique').value = flight?.launch_technique || '';
  el('f_notes').value = flight?.notes || '';

  const buddyIds = new Set(flight?.buddy_ids || []);
  for (const opt of el('f_buddies').options) opt.selected = buddyIds.has(opt.value);

  el('drawerOverlay').hidden = false;
  el('flightDrawer').hidden = false;
  el('flightDrawer').setAttribute('aria-hidden', 'false');
  console.log(`[FL:flights] drawer opened (${flight ? 'edit ' + flight.id : 'add'})`);
  el('f_date').focus();
}

function closeDrawer() {
  el('drawerOverlay').hidden = true;
  el('flightDrawer').hidden = true;
  el('flightDrawer').setAttribute('aria-hidden', 'true');
  editingId = null;
  console.log('[FL:flights] drawer closed');
}

function readFormPayload() {
  const buddy_ids = [...el('f_buddies').selectedOptions].map((o) => o.value);
  return {
    flight_date: el('f_date').value,
    launch_site_id: el('f_launch').value,
    landing_site_id: el('f_landing').value || null,
    category_id: el('f_category').value,
    glider_id: el('f_glider').value || null,
    harness_id: el('f_harness').value || null,
    duration_min: el('f_duration').value === '' ? null : Number(el('f_duration').value),
    distance_km: el('f_distance').value === '' ? null : Number(el('f_distance').value),
    max_alt_m: el('f_maxalt').value === '' ? null : Number(el('f_maxalt').value),
    launch_technique: el('f_technique').value || null,
    notes: el('f_notes').value || null,
    buddy_ids,
  };
}

function renderFieldErrors(details) {
  const errors = details?.errors || [];
  for (const err of errors) {
    const field = err.loc?.[err.loc.length - 1];
    const target = document.querySelector(`#flightForm .field-error[data-field="${field}"]`);
    if (target) target.textContent = err.msg;
    console.warn(`[FL:flights] validation error on ${field}: ${err.msg}`);
  }
  if (errors.length === 0) {
    el('drawerAlert').textContent = window.t('common.error_generic');
    el('drawerAlert').classList.add('visible');
  }
}

function upsertFlightInPlace(flight) {
  flight._launch = siteName(flight.launch_site_id) || '';
  flight._landing = siteName(flight.landing_site_id) || '';
  flight._category = categoryName(flight.category_id) || '';
  flight._glider = gliderName(flight.glider_id) || '';
  flight._region = siteRegionName(flight.launch_site_id) || '';
  flight._year = new Date(flight.flight_date).getUTCFullYear();

  const idx = allFlights.findIndex((f) => f.id === flight.id);
  if (idx >= 0) allFlights[idx] = flight;
  else allFlights.push(flight);
}

async function submitFlight(event) {
  event.preventDefault();
  clearFieldErrors();
  const saveBtn = el('drawerSave');
  saveBtn.disabled = true;

  const payload = readFormPayload();
  const url = editingId ? `/api/flights/${editingId}` : '/api/flights';
  const method = editingId ? 'PUT' : 'POST';
  console.log(`[FL:flights] ${method} ${url}`, payload);

  try {
    const res = await fetchAuth(url, { method, body: JSON.stringify(payload) });
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
      console.error(`[FL:flights] save failed (${res.status})`);
      return;
    }

    const saved = await res.json();
    upsertFlightInPlace(saved);
    applyFiltersAndSort();
    closeDrawer();

    requestAnimationFrame(() => {
      const row = document.querySelector(`tr[data-id="${saved.id}"]`);
      if (row) {
        row.scrollIntoView({ block: 'center', behavior: 'smooth' });
        row.classList.add('row-highlight');
        setTimeout(() => row.classList.remove('row-highlight'), 1500);
      }
    });
    console.log(`[FL:flights] flight ${editingId ? 'updated' : 'created'}: ${saved.id}`);
  } catch (err) {
    console.error('[FL:flights] save request failed', err);
    el('drawerAlert').textContent = window.t('common.error_generic');
    el('drawerAlert').classList.add('visible');
  } finally {
    saveBtn.disabled = false;
  }
}

async function deleteFlight() {
  if (!editingId) return;
  const id = editingId;
  console.log(`[FL:flights] deleting flight ${id}`);
  const res = await fetchAuth(`/api/flights/${id}`, { method: 'DELETE' });
  if (!res.ok) {
    el('drawerAlert').textContent = await errorMessage(res);
    el('drawerAlert').classList.add('visible');
    console.error(`[FL:flights] delete failed (${res.status})`);
    return;
  }
  allFlights = allFlights.filter((f) => f.id !== id);
  applyFiltersAndSort();
  closeDrawer();
  console.log(`[FL:flights] flight deleted: ${id}`);
}

// ---- wiring ----

function wireEvents() {
  el('addFlightBtn').addEventListener('click', () => openDrawer(null));
  el('drawerClose').addEventListener('click', closeDrawer);
  el('drawerOverlay').addEventListener('click', closeDrawer);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !el('flightDrawer').hidden) closeDrawer();
  });

  el('flightForm').addEventListener('submit', submitFlight);

  el('drawerDelete').addEventListener('click', () => {
    el('deleteConfirm').hidden = false;
  });
  el('deleteConfirmNo').addEventListener('click', () => {
    el('deleteConfirm').hidden = true;
  });
  el('deleteConfirmYes').addEventListener('click', deleteFlight);

  ['searchInput', 'filterYear', 'filterCategory', 'filterGlider', 'filterSite', 'filterRegion'].forEach(
    (id) => {
      const eventName = id === 'searchInput' ? 'input' : 'change';
      el(id).addEventListener(eventName, () => applyFiltersAndSort({ resetPage: true }));
    },
  );

  document.querySelectorAll('#flightsTable th[data-sort]').forEach((th) => {
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      if (sortKey === key) {
        sortDir = sortDir === 'asc' ? 'desc' : 'asc';
      } else {
        sortKey = key;
        sortDir = 'asc';
      }
      applyFiltersAndSort();
    });
  });
}

async function init() {
  await bootstrapPage({ page: 'flights', requireAuth: true });
  await loadRefData();
  allFlights = await loadFlights();
  populateFilterOptions();
  readFiltersFromUrl();
  wireEvents();
  applyFiltersAndSort();
}

init();
