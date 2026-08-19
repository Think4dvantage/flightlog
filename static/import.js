/**
 * /import — self-service spreadsheet import (v0.9.8, specs/008-self-service-import).
 * Four-step wizard (upload → map → preview → done), plus a past-imports list with undo.
 */

import { bootstrapPage } from '/static/bootstrap.js';
import { fetchAuth, errorMessage } from '/static/auth.js';

const el = (id) => document.getElementById(id);

// Order mirrors core/spreadsheet_import.py's REQUIRED_FIELDS + OPTIONAL_FIELDS exactly.
const FIELDS = [
  { name: 'flight_date', required: true },
  { name: 'launch_site', required: true },
  { name: 'landing_site', required: false },
  { name: 'category', required: false },
  { name: 'glider', required: false },
  { name: 'harness', required: false },
  { name: 'duration_min', required: false },
  { name: 'distance_km', required: false },
  { name: 'max_alt_m', required: false },
  { name: 'launch_technique', required: false },
  { name: 'nickname', required: false },
  { name: 'notes', required: false },
];

let selectedFile = null;
let selectedSheet = null;
let sheetNames = [];
let columns = [];
let lastPreview = null;
let pendingUndoRunId = null;

function showAlert(message) {
  el('alert').textContent = message;
  el('alert').classList.add('visible');
  console.error(`[FL:import] ${message}`);
}

function clearAlert() {
  el('alert').classList.remove('visible');
  el('alert').textContent = '';
}

function showStep(name) {
  for (const id of ['uploadStep', 'mapStep', 'previewStep', 'doneStep']) {
    el(id).hidden = id !== name;
  }
  console.log(`[FL:import] step -> ${name}`);
}

// ---- step 1: upload ----

async function fetchColumnsForSelection() {
  const body = new FormData();
  body.append('file', selectedFile);
  if (selectedSheet) body.append('sheet', selectedSheet);
  const started = performance.now();
  console.log(`[FL:import] POST /api/imports/columns (${selectedFile.name}, sheet=${selectedSheet ?? '(default)'})`);
  const res = await fetchAuth('/api/imports/columns', { method: 'POST', body });
  if (!res.ok) {
    showAlert(await errorMessage(res));
    console.error(`[FL:import] columns read failed (${res.status})`);
    return null;
  }
  const data = await res.json();
  console.log(`[FL:import] ${data.columns.length} columns read in ${(performance.now() - started).toFixed(0)}ms`);
  return data;
}

function populateSheetSelect(names) {
  const select = el('sheetSelect');
  select.innerHTML = '';
  for (const name of names) {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    select.appendChild(opt);
  }
  select.value = selectedSheet || names[0];
}

async function handleSheetChange() {
  selectedSheet = el('sheetSelect').value;
  const data = await fetchColumnsForSelection();
  if (!data) return;
  columns = data.columns;
}

async function handleUploadContinue() {
  const file = el('fileInput').files[0];
  if (!file) {
    showAlert(window.t('common.error_generic'));
    return;
  }
  clearAlert();

  // Columns already fetched for this exact file (and whatever sheet is currently selected,
  // reviewed via the sheet picker below) — a second click just moves on.
  if (selectedFile === file && columns.length > 0) {
    renderMapTable();
    showStep('mapStep');
    return;
  }

  selectedFile = file;
  selectedSheet = null;
  const data = await fetchColumnsForSelection();
  if (!data) return;
  columns = data.columns;
  sheetNames = data.sheet_names;

  if (sheetNames.length > 1) {
    populateSheetSelect(sheetNames);
    selectedSheet = el('sheetSelect').value;
    el('sheetField').hidden = false;
    console.log(`[FL:import] ${sheetNames.length} sheets found — awaiting sheet confirmation`);
    return;
  }

  el('sheetField').hidden = true;
  renderMapTable();
  showStep('mapStep');
}

// ---- step 2: map columns ----

function renderMapTable() {
  const tbody = el('mapBody');
  tbody.innerHTML = '';

  for (const field of FIELDS) {
    const tr = document.createElement('tr');

    const fieldTd = document.createElement('td');
    const label = window.t(`import_page.field.${field.name}`);
    fieldTd.textContent = label;
    tr.appendChild(fieldTd);

    const columnTd = document.createElement('td');
    const select = document.createElement('select');
    select.dataset.field = field.name;
    const noneOpt = document.createElement('option');
    noneOpt.value = '';
    noneOpt.textContent = window.t('import_page.map.unmapped');
    select.appendChild(noneOpt);
    for (const col of columns) {
      const opt = document.createElement('option');
      opt.value = col.name;
      opt.textContent = col.name;
      select.appendChild(opt);
    }
    columnTd.appendChild(select);
    tr.appendChild(columnTd);

    const samplesTd = document.createElement('td');
    samplesTd.className = 'muted';
    samplesTd.dataset.samplesFor = field.name;
    tr.appendChild(samplesTd);

    select.addEventListener('change', () => updateSamples(field.name, select.value));
    tbody.appendChild(tr);
  }
}

function updateSamples(fieldName, columnName) {
  const cell = document.querySelector(`[data-samples-for="${fieldName}"]`);
  if (!cell) return;
  const col = columns.find((c) => c.name === columnName);
  cell.textContent = col ? col.samples.join(', ') : '';
}

function readMapping() {
  const mapping = {};
  document.querySelectorAll('#mapBody select').forEach((select) => {
    if (select.value) mapping[select.dataset.field] = select.value;
  });
  return mapping;
}

async function handleMapPreview() {
  const mapping = readMapping();
  const missingRequired = FIELDS.filter((f) => f.required && !mapping[f.name]);
  if (missingRequired.length > 0) {
    showAlert(window.t('common.error_generic'));
    return;
  }
  clearAlert();

  const body = new FormData();
  body.append('file', selectedFile);
  body.append('mapping', JSON.stringify(mapping));
  if (selectedSheet) body.append('sheet', selectedSheet);
  console.log('[FL:import] POST /api/imports/preview', mapping);
  const res = await fetchAuth('/api/imports/preview', { method: 'POST', body });
  if (!res.ok) {
    showAlert(await errorMessage(res));
    console.error(`[FL:import] preview failed (${res.status})`);
    return;
  }
  lastPreview = await res.json();
  console.log(
    `[FL:import] preview: ${lastPreview.imported_count}/${lastPreview.row_count} importable, ` +
      `${lastPreview.skipped_count} skipped, ${lastPreview.already_imported_count} already imported`
  );
  renderPreview(lastPreview);
  showStep('previewStep');
}

// ---- step 3: preview ----

function renderList(container, labelKey, values) {
  const p = document.createElement('p');
  const strong = document.createElement('strong');
  strong.textContent = `${window.t(labelKey)}: `;
  p.appendChild(strong);
  p.appendChild(document.createTextNode(values.length ? values.join(', ') : window.t('import_page.preview.none')));
  container.appendChild(p);
}

function renderPreview(preview) {
  el('previewSummary').textContent = window.t('import_page.preview.summary', {
    importable: preview.imported_count,
    total: preview.row_count,
  });

  const alreadyEl = el('previewAlreadyImported');
  if (preview.imported_count === 0 && preview.already_imported_count > 0) {
    alreadyEl.textContent = window.t('import_page.preview.all_already_imported');
    alreadyEl.hidden = false;
  } else if (preview.already_imported_count > 0) {
    alreadyEl.textContent = window.t('import_page.preview.already_imported', {
      count: preview.already_imported_count,
    });
    alreadyEl.hidden = false;
  } else {
    alreadyEl.hidden = true;
  }

  const newData = el('previewNewData');
  newData.innerHTML = '';
  renderList(newData, 'import_page.preview.new_sites', preview.new_sites);
  renderList(newData, 'import_page.preview.new_categories', preview.new_categories);
  renderList(newData, 'import_page.preview.new_gliders', preview.new_gliders);
  renderList(newData, 'import_page.preview.new_harnesses', preview.new_harnesses);

  const errorsBlock = el('previewErrorsBlock');
  const errorsList = el('previewErrorsList');
  errorsList.innerHTML = '';
  if (preview.errors.length > 0) {
    for (const err of preview.errors) {
      const li = document.createElement('li');
      li.textContent = `${window.t('import_page.preview.row_label', { row: err.row })}: ${err.reason}`;
      errorsList.appendChild(li);
    }
    errorsBlock.hidden = false;
  } else {
    errorsBlock.hidden = true;
  }

  el('previewConfirmBtn').textContent = window.t('import_page.preview.confirm_button', {
    count: preview.imported_count,
  });
  el('previewConfirmBtn').disabled = preview.imported_count === 0;
}

async function handleConfirmImport() {
  const mapping = readMapping();
  const body = new FormData();
  body.append('file', selectedFile);
  body.append('mapping', JSON.stringify(mapping));
  if (selectedSheet) body.append('sheet', selectedSheet);
  console.log('[FL:import] POST /api/imports/commit');
  const res = await fetchAuth('/api/imports/commit', { method: 'POST', body });
  if (!res.ok) {
    showAlert(await errorMessage(res));
    console.error(`[FL:import] commit failed (${res.status})`);
    return;
  }
  const result = await res.json();
  console.log(`[FL:import] committed: run=${result.import_run_id}, ${result.imported_count} flights`);
  el('doneSummary').textContent = window.t('import_page.done.summary', { count: result.imported_count });
  showStep('doneStep');
  await loadAndRenderRuns();
}

function resetWizard() {
  selectedFile = null;
  selectedSheet = null;
  sheetNames = [];
  columns = [];
  lastPreview = null;
  el('fileInput').value = '';
  el('sheetField').hidden = true;
  clearAlert();
  showStep('uploadStep');
}

// ---- past imports / undo ----

function fmtDate(iso) {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

async function loadAndRenderRuns() {
  const res = await fetchAuth('/api/imports');
  if (!res.ok) {
    showAlert(await errorMessage(res));
    return;
  }
  const runs = await res.json();
  console.log(`[FL:import] loaded ${runs.length} past import runs`);

  const tbody = el('runsBody');
  tbody.innerHTML = '';
  for (const run of runs) {
    const tr = document.createElement('tr');

    const fileTd = document.createElement('td');
    fileTd.textContent = run.source_filename;
    tr.appendChild(fileTd);

    const dateTd = document.createElement('td');
    dateTd.textContent = fmtDate(run.created_at);
    tr.appendChild(dateTd);

    const importedTd = document.createElement('td');
    importedTd.textContent = run.imported_count;
    tr.appendChild(importedTd);

    const actionsTd = document.createElement('td');
    const undoBtn = document.createElement('button');
    undoBtn.type = 'button';
    undoBtn.className = 'btn-ghost';
    undoBtn.textContent = window.t('import_page.runs.undo');
    undoBtn.addEventListener('click', () => openUndoConfirm(run.id));
    actionsTd.appendChild(undoBtn);
    tr.appendChild(actionsTd);

    tbody.appendChild(tr);
  }

  el('runsEmptyState').hidden = runs.length > 0;
  el('runsTable').hidden = runs.length === 0;
  el('runsResultCount').textContent = window.t('import_page.runs.result_count', { count: runs.length });
}

function openUndoConfirm(runId) {
  pendingUndoRunId = runId;
  el('confirmOverlay').hidden = false;
  el('confirmDrawer').hidden = false;
  el('confirmDrawer').setAttribute('aria-hidden', 'false');
  console.log(`[FL:import] undo confirm opened: ${runId}`);
}

function closeUndoConfirm() {
  pendingUndoRunId = null;
  el('confirmOverlay').hidden = true;
  el('confirmDrawer').hidden = true;
  el('confirmDrawer').setAttribute('aria-hidden', 'true');
}

async function runUndo() {
  if (!pendingUndoRunId) return;
  const runId = pendingUndoRunId;
  const res = await fetchAuth(`/api/imports/${runId}`, { method: 'DELETE' });
  closeUndoConfirm();
  if (!res.ok) {
    showAlert(await errorMessage(res));
    console.error(`[FL:import] undo failed (${res.status})`);
    return;
  }
  const result = await res.json();
  console.log(`[FL:import] undo succeeded: ${runId}`, result);
  showAlert(
    window.t('import_page.undo_result', {
      deleted: result.flights_deleted,
      kept: result.flights_kept,
    })
  );
  await loadAndRenderRuns();
}

function wireEvents() {
  el('uploadContinueBtn').addEventListener('click', handleUploadContinue);
  el('sheetSelect').addEventListener('change', handleSheetChange);
  el('mapBackBtn').addEventListener('click', () => showStep('uploadStep'));
  el('mapPreviewBtn').addEventListener('click', handleMapPreview);
  el('previewBackBtn').addEventListener('click', () => showStep('mapStep'));
  el('previewConfirmBtn').addEventListener('click', handleConfirmImport);
  el('doneAnotherBtn').addEventListener('click', resetWizard);

  el('confirmClose').addEventListener('click', closeUndoConfirm);
  el('confirmNo').addEventListener('click', closeUndoConfirm);
  el('confirmOverlay').addEventListener('click', closeUndoConfirm);
  el('confirmYes').addEventListener('click', runUndo);
}

async function init() {
  await bootstrapPage({ page: 'import', requireAuth: true });
  wireEvents();
  showStep('uploadStep');
  await loadAndRenderRuns();
}

init();
