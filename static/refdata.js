/**
 * Fetch-once, in-memory-cached reference data: sites, gliders, harnesses, categories,
 * buddies, regions. Every list/detail/drawer page that needs to join an id to a display
 * name goes through this module instead of re-fetching.
 *
 * loadRefData() is idempotent — call it from every page that needs joins; the network
 * round-trip only happens once per page load.
 */

import { fetchAuth } from '/static/auth.js';

const ENDPOINTS = {
  sites: '/api/sites',
  gliders: '/api/gliders?include_retired=true',
  harnesses: '/api/harnesses?include_retired=true',
  categories: '/api/categories?include_archived=true',
  buddies: '/api/buddies',
  regions: '/api/regions',
};

let cache = null;
let loadPromise = null;

async function fetchEntity(key, url) {
  const started = performance.now();
  const res = await fetchAuth(url);
  if (!res.ok) {
    console.error(`[FL:refdata] failed to load ${key} (${res.status})`);
    return { list: [], byId: new Map() };
  }
  const list = await res.json();
  const byId = new Map(list.map((row) => [row.id, row]));
  console.log(
    `[FL:refdata] loaded ${key}: ${list.length} rows in ${(performance.now() - started).toFixed(0)}ms`,
  );
  return { list, byId };
}

/** Fetch and cache every reference table. Safe to call from every page — a second call
 * anywhere reuses the in-flight or already-resolved promise. */
export function loadRefData() {
  if (loadPromise) {
    console.log('[FL:refdata] cache hit, reusing loaded data');
    return loadPromise;
  }

  loadPromise = (async () => {
    const entries = await Promise.all(
      Object.entries(ENDPOINTS).map(async ([key, url]) => [key, await fetchEntity(key, url)]),
    );
    cache = Object.fromEntries(entries);
    return cache;
  })();

  return loadPromise;
}

function requireCache() {
  if (!cache) {
    throw new Error('[FL:refdata] accessed before loadRefData() resolved');
  }
  return cache;
}

export function getSites() {
  return requireCache().sites.list;
}
export function getGliders() {
  return requireCache().gliders.list;
}
export function getHarnesses() {
  return requireCache().harnesses.list;
}
export function getCategories() {
  return requireCache().categories.list;
}
export function getBuddies() {
  return requireCache().buddies.list;
}
export function getRegions() {
  return requireCache().regions.list;
}

export function siteName(id) {
  if (!id) return null;
  return requireCache().sites.byId.get(id)?.name ?? null;
}

export function gliderName(id) {
  if (!id) return null;
  const g = requireCache().gliders.byId.get(id);
  if (!g) return null;
  return g.nickname || [g.brand, g.model, g.size].filter(Boolean).join(' ');
}

export function harnessName(id) {
  if (!id) return null;
  const h = requireCache().harnesses.byId.get(id);
  if (!h) return null;
  return [h.brand, h.model, h.size].filter(Boolean).join(' ');
}

export function categoryName(id) {
  if (!id) return null;
  return requireCache().categories.byId.get(id)?.name ?? null;
}

export function buddyName(id) {
  if (!id) return null;
  return requireCache().buddies.byId.get(id)?.display_name ?? null;
}

export function regionName(id) {
  if (!id) return null;
  return requireCache().regions.byId.get(id)?.name ?? null;
}

export function siteRegionName(siteId) {
  if (!siteId) return null;
  const site = requireCache().sites.byId.get(siteId);
  return site ? regionName(site.region_id) : null;
}
