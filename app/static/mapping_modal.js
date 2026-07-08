const AGG_OPTIONS = [
  { v: 'sum', l: '求和 sum — 所有行相加（SKU 级）' },
  { v: 'count', l: '计数 count — 行数' },
  { v: 'count_distinct', l: '去重计数 — 按去重键计唯一值（订单数）' },
  { v: 'sum_dedup', l: '去重求和 — 每组只计一次（订单级金额/折扣）' },
  { v: 'max_dedup', l: '去重取最大 — 每组取最大再相加' },
  { v: 'avg', l: '平均值 avg' },
];

const DATE_FMT_OPTIONS = [
  { v: '', l: '自动识别' },
  { v: 'us', l: '美式 MM/DD/YYYY（订单 Created Time）' },
  { v: 'eu', l: '欧式 DD/MM/YYYY（退货/联盟）' },
  { v: 'iso', l: 'ISO YYYY/MM/DD（结算表）' },
];

const FILTER_OPS = [
  { v: 'eq', l: '等于' },
  { v: 'ne', l: '不等于' },
  { v: 'in', l: '属于(多值)' },
  { v: 'not_in', l: '不属于(多值)' },
  { v: 'gt', l: '大于' },
  { v: 'gte', l: '大于等于' },
  { v: 'lt', l: '小于' },
  { v: 'lte', l: '小于等于' },
  { v: 'contains', l: '包含' },
  { v: 'not_contains', l: '不包含' },
  { v: 'starts_with', l: '开头是' },
  { v: 'ends_with', l: '结尾是' },
  { v: 'between', l: '介于(两值)' },
  { v: 'nonempty', l: '非空' },
  { v: 'empty', l: '为空' },
];

const DEFAULT_JOIN_KEYS = ['Order ID'];
const DEFAULT_BENCHMARK_KEY = 'Order ID';

let currentMappingId = null;
const allColumnsCache = {};
let currentDataSourceId = null;
let currentLogicalFieldCode = '';
let parts = [];
let modalSession = 0;
/** 取数方式 Tab：fetch(计算) | per_order(每单金额) | placeholder(占位) */
let activeTab = 'fetch';
/** 定位叠层：保存父弹窗表单状态，关闭子层时恢复 */
const mappingContextStack = [];

function mappingOpCycleHtml(combineOp = 'add', extraClass = '') {
  const isSub = combineOp === 'subtract';
  const val = isSub ? 'subtract' : 'add';
  return `<button type="button" class="mapping-op-cycle ${extraClass}" data-value="${val}" title="点击切换加减" aria-label="加减运算">${isSub ? '−' : '+'}</button>`;
}

function setMappingOpCycle(el, combineOp = 'add') {
  if (!el) return;
  const isSub = combineOp === 'subtract';
  el.dataset.value = isSub ? 'subtract' : 'add';
  el.textContent = isSub ? '−' : '+';
}

function readMappingOp(el) {
  if (!el) return 'add';
  return el.dataset?.value || el.value || 'add';
}

function wireMappingOpCycle(el, { onChange } = {}) {
  if (!el || el.dataset.wired === '1') return;
  el.dataset.wired = '1';
  el.addEventListener('click', () => {
    const next = el.dataset.value === 'subtract' ? 'add' : 'subtract';
    setMappingOpCycle(el, next);
    onChange?.(next);
  });
}

function findReuseField(code) {
  if (!code) return null;
  const list = window.REUSE_FIELDS_BY_DS?.[currentDataSourceId]
    || window.REUSE_FIELDS_BY_DS?.[String(currentDataSourceId)]
    || [];
  return list.find((f) => f.code === code) || null;
}

function captureMappingFormState() {
  return {
    mappingId: currentMappingId,
    dataSourceId: currentDataSourceId,
    logicalFieldCode: currentLogicalFieldCode,
    title: document.getElementById('modalTitle')?.textContent || '',
    subtitle: document.getElementById('modalSubtitle')?.textContent || '',
    label: document.getElementById('mappingLabel')?.value || '',
    group: document.getElementById('mappingGroup')?.value || '',
    sort: document.getElementById('mappingSort')?.value || '0',
    activeTab,
    perOrderAmount: document.getElementById('perOrderAmount')?.value || '1',
    perOrderBasis: document.getElementById('perOrderBasis')?.value || 'valid_orders',
    ratioPercent: document.getElementById('ratioPercent')?.value || '100',
    ratioBase: ratioBaseSelect?.val() || '',
    parts: JSON.parse(JSON.stringify(parts)),
    newMappingHidden: document.getElementById('newMappingFields')?.classList.contains('hidden') ?? true,
    deleteHidden: document.getElementById('btnDeleteMapping')?.classList.contains('hidden') ?? true,
  };
}

async function restoreMappingFormState(state) {
  const session = ++modalSession;
  currentMappingId = state.mappingId;
  currentDataSourceId = state.dataSourceId;
  currentLogicalFieldCode = state.logicalFieldCode;
  document.getElementById('modalTitle').textContent = state.title;
  document.getElementById('modalSubtitle').textContent = state.subtitle;
  document.getElementById('mappingLabel').value = state.label;
  document.getElementById('mappingGroup').value = state.group;
  document.getElementById('mappingSort').value = state.sort;
  const perOrderInput = document.getElementById('perOrderAmount');
  if (perOrderInput) perOrderInput.value = state.perOrderAmount || '1';
  const perOrderBasisSel = document.getElementById('perOrderBasis');
  if (perOrderBasisSel) perOrderBasisSel.value = state.perOrderBasis || 'valid_orders';
  const ratioPercentInput = document.getElementById('ratioPercent');
  if (ratioPercentInput) ratioPercentInput.value = state.ratioPercent || '100';
  document.getElementById('newMappingFields')?.classList.toggle('hidden', state.newMappingHidden);
  document.getElementById('btnDeleteMapping')?.classList.toggle('hidden', state.deleteHidden);
  parts = state.parts;
  await ensureFiles(currentDataSourceId);
  await refreshReuseFields();
  if (session !== modalSession) return;
  ensureRatioBaseSelect(state.ratioBase || '');
  setActiveTab(state.activeTab || 'fetch');
  renderParts();
  updateNestedChrome();
  focusMappingModal();
}

function updateNestedChrome() {
  const backLink = document.getElementById('modalBackLink');
  const modal = document.getElementById('mappingModal');
  const nested = mappingContextStack.length > 0;
  backLink?.classList.toggle('hidden', !nested);
  modal?.classList.toggle('mapping-modal--stacked', nested);
  if (nested && backLink) {
    const parent = mappingContextStack[mappingContextStack.length - 1];
    backLink.textContent = `← 返回 ${parent.title}`;
  }
}

function setActiveTab(tab) {
  activeTab = tab || 'fetch';
  const usesParts = activeTab === 'fetch' || activeTab === 'reuse';
  document.querySelectorAll('.mapping-tab').forEach((btn) => {
    btn.classList.toggle('is-active', btn.dataset.tab === activeTab);
    btn.setAttribute('aria-selected', btn.dataset.tab === activeTab ? 'true' : 'false');
  });
  document.querySelectorAll('.mapping-tab-panel').forEach((panel) => {
    panel.classList.toggle('hidden', panel.dataset.panel !== activeTab);
  });
  const region = document.getElementById('partsRegion');
  if (region) region.classList.toggle('hidden', !usesParts);
  document.getElementById('btnAddPart')?.classList.toggle('hidden', activeTab !== 'fetch');
  document.getElementById('btnAddFieldRef')?.classList.toggle('hidden', activeTab !== 'reuse');
  const title = document.getElementById('partsRegionTitle');
  const hint = document.getElementById('partsRegionHint');
  if (title && hint) {
    if (activeTab === 'reuse') {
      title.textContent = '复用已配置字段';
      hint.textContent = '引用同店铺其它字段的值，可多项加减组合';
    } else {
      title.textContent = '取数规则';
      hint.textContent = '支持多来源组与组内多列加减合并';
    }
  }
  if (activeTab === 'ratio') ensureRatioBaseSelect();
}

let ratioBaseSelect = null;

function ensureRatioBaseSelect(value) {
  const host = document.getElementById('ratioBaseHost');
  if (!host) return;
  const options = getReuseFieldOptions().map((f) => ({ value: f.code, label: f.name }));
  const current = value != null ? value : (ratioBaseSelect?.val() || '');
  if (ratioBaseSelect) ratioBaseSelect.destroy?.();
  ratioBaseSelect = new SelectField(host, {
    placeholder: options.length ? '选择基准字段' : '暂无可选字段',
    options,
    value: current,
  });
}

function focusMappingModal() {
  const panel = document.getElementById('mappingPanel');
  const focusable = panel?.querySelector(
    'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])',
  );
  focusable?.focus({ preventScroll: true });
}

async function goAuxFieldOnPage(mappingId) {
  const modal = document.getElementById('mappingModal');
  if (!window.AppModal?.isOpen(modal)) {
    await openModal('edit', mappingId);
    return;
  }
  mappingContextStack.push(captureMappingFormState());
  await openModal('edit', mappingId, { stacked: true });
}

function toast(msg, ok = true) {
  window.showAppToast?.(msg, ok);
}

function getMeta(dsId) {
  if (!window.DATA_SOURCE_META[dsId]) window.DATA_SOURCE_META[dsId] = { files: [] };
  return window.DATA_SOURCE_META[dsId];
}

async function apiFetch(url) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 10000);
  try {
    const res = await fetch(url, { signal: ctrl.signal });
    if (!res.ok) {
      toast(`接口错误 ${res.status}`, false);
      return null;
    }
    return await res.json();
  } catch (err) {
    const msg = err.name === 'AbortError'
      ? '请求超时，请重启服务：uvicorn app.main:app --port 8081'
      : '网络错误，无法连接后端';
    toast(msg, false);
    return null;
  } finally {
    clearTimeout(timer);
  }
}

async function ensureFiles(dsId) {
  const meta = getMeta(dsId);
  if (meta.files?.length) return meta.files;
  const data = await apiFetch(`/api/data-sources/${dsId}/schema`);
  if (!data) return [];
  meta.files = data.files || [];
  return meta.files;
}

async function fetchSheets(dsId, fileKeyword) {
  if (!fileKeyword) return [];
  const data = await apiFetch(
    `/api/data-sources/${dsId}/schema?file=${encodeURIComponent(fileKeyword)}`,
  );
  return data?.sheets || [];
}

async function fetchColumns(dsId, fileKeyword, sheetName) {
  if (!fileKeyword || !sheetName) return [];
  const data = await apiFetch(
    `/api/data-sources/${dsId}/schema?file=${encodeURIComponent(fileKeyword)}&sheet=${encodeURIComponent(sheetName)}`,
  );
  return data?.columns || [];
}

/** 将用户输入（关键字或完整文件名）归一为 schema 关键字 */
function resolveFileKey(input, files) {
  const v = (input || '').trim();
  if (!v || !files?.length) return v;
  const vl = v.toLowerCase();
  for (const f of files) {
    const kw = f.keyword || '';
    const fn = f.file_name || '';
    if (v === kw || v === fn) return kw;
    if (kw && vl === kw.toLowerCase()) return kw;
    if (fn && fn.toLowerCase() === vl) return kw;
    if (fn && fn.toLowerCase().includes(vl)) return kw;
    if (kw && vl.includes(kw.toLowerCase())) return kw;
  }
  return v;
}

function applyFilterColOpts(blockEl) {
  const cols = blockEl._filterCols || [];
  if (blockEl._dedupColCombo) blockEl._dedupColCombo.setOpts(cols);
  (blockEl._joinKeyCombos || []).forEach((c) => c.setOpts(cols));
}

async function refreshLineFilterCols(lineEl, blockEl) {
  const st = blockEl._sourceState;
  const sheet = lineEl._sheetSelect?.val();
  const cols = [];
  if (st?.file && sheet) {
    const sheetCols = await fetchColumns(currentDataSourceId, st.file, sheet);
    (sheetCols || []).forEach((c) => cols.push(c));
  }
  lineEl._filterCols = cols.sort((a, b) => a.localeCompare(b));
  (lineEl._filterEntries || []).forEach((e) => e.colC?.setOpts(lineEl._filterCols));
  updateFilterColHint(lineEl, blockEl);
  return lineEl._filterCols;
}

async function refreshBlockFilterCols(blockEl) {
  const cols = new Set();
  const st = blockEl._sourceState;

  blockEl.querySelectorAll('.source-line').forEach((row) => {
    (row._colCombo?.options || []).forEach((c) => cols.add(c));
  });

  if (st?.file && currentDataSourceId) {
    const sheets = st.sheets?.length
      ? st.sheets
      : await fetchSheets(currentDataSourceId, st.file);
    for (const sheet of sheets) {
      const sheetCols = await fetchColumns(currentDataSourceId, st.file, sheet);
      (sheetCols || []).forEach((c) => cols.add(c));
    }
  }

  blockEl._filterCols = [...cols].sort((a, b) => a.localeCompare(b));
  applyFilterColOpts(blockEl);
  return blockEl._filterCols;
}

async function loadRowColumns(blockEl, row, sheet, keepCol) {
  const st = blockEl._sourceState;
  if (!st?.file || !sheet) {
    row._colCombo?.setOpts([]);
    if (keepCol === undefined) row._colCombo?.set('');
    refreshBlockFilterCols(blockEl).catch(() => {});
    return;
  }
  const cols = await fetchColumns(currentDataSourceId, st.file, sheet);
  row._colCombo.setOpts(cols);
  if (keepCol !== undefined) {
    row._colCombo.set(keepCol && cols.includes(keepCol) ? keepCol : '');
  }
  refreshBlockFilterCols(blockEl).catch(() => {});
  refreshLineFilterCols(row, blockEl).catch(() => {});
}

function wireSourceLine(blockEl, row, { sheet_name: sheetName = '', column_header: col = '', row_filters = [] } = {}) {
  const st = blockEl._sourceState;
  const sheetHost = row.querySelector('.s-sheet-combo');
  const colHost = row.querySelector('.s-col-combo');
  if (!sheetHost || !colHost) return;
  const sheetSelect = new SelectField(sheetHost, {
    placeholder: st.file ? '请选择 Sheet' : '请先选本组文件',
    options: st.sheets || [],
    value: sheetName,
    onChange: (sheet) => loadRowColumns(blockEl, row, sheet),
  });
  sheetSelect.setDisabled(!st.file || !st.sheets?.length);

  const colCombo = new SearchCombo(colHost, [], {
    value: col,
    placeholder: '搜索列头',
    emptyHint: '请先选择 Sheet',
  });
  row._sheetSelect = sheetSelect;
  row._colCombo = colCombo;
  if (row_filters?.length) {
    row._rowFilters = [...row_filters];
  } else if (!row._rowFilters) {
    row._rowFilters = [];
  }

  row._getSource = () => ({
    source_file_keyword: st.file || null,
    sheet_name: sheetSelect.val(),
    column_header: colCombo.val(),
    combine_op: readMappingOp(row.querySelector('.s-row-op')),
    row_filters: collectRowFilters(row),
  });

  if (st.file && sheetName) {
    loadRowColumns(blockEl, row, sheetName, col);
  }
  initRowFilterSection(row, blockEl);
}

function refreshAllRowSheets(blockEl, { keepCols = true } = {}) {
  const st = blockEl._sourceState;
  blockEl.querySelectorAll('.source-line').forEach((row) => {
    const prevSheet = keepCols ? row._sheetSelect?.val() : '';
    const prevCol = keepCols ? row._colCombo?.val() : '';
    if (!row._sheetSelect) {
      wireSourceLine(blockEl, row, {
        sheet_name: prevSheet,
        column_header: prevCol,
        row_filters: row._rowFilters || [],
      });
      return;
    }
    row._sheetSelect.setOpts(st.sheets || [], st.sheets?.length ? '请选择 Sheet' : '该文件无 Sheet');
    row._sheetSelect.setDisabled(!st.file || !st.sheets?.length);
    const sheet = (prevSheet && st.sheets?.includes(prevSheet)) ? prevSheet : (st.sheets?.[0] || '');
    row._sheetSelect.set(sheet);
    loadRowColumns(blockEl, row, sheet, keepCols ? prevCol : '');
  });
}

/** 组级：先选文件，每行独立选 Sheet + 列头（同文件可跨 Sheet） */
async function bootstrapBlockSource(blockEl, sources, { blockIdx } = {}) {
  const dsId = currentDataSourceId;
  const first = sources[0] || {};
  const st = blockEl._sourceState = { file: '', sheets: [], files: [] };

  const fileHost = blockEl.querySelector('.g-block-file');
  if (!fileHost) return;

  const files = await ensureFiles(dsId);
  st.files = files;
  if (!files.length) toast('暂无来源文件，请先导入数据', false);

  const fileSelect = new SelectField(fileHost, {
    placeholder: '请选择来源文件',
    options: fileSelectOptions(files),
    value: resolveFileKey(first.source_file_keyword || '', files),
    onChange: (file) => cascadeBlockFile(file),
  });
  blockEl._fileSelect = fileSelect;

  async function cascadeBlockFile(file, keepAll = true) {
    const resolved = resolveFileKey(file, st.files);
    fileSelect.set(resolved);
    st.file = resolved;
    if (!resolved) {
      st.sheets = [];
      refreshAllRowSheets(blockEl, { keepCols: false });
      return;
    }
    const sheets = await fetchSheets(dsId, resolved);
    st.sheets = sheets;
    refreshAllRowSheets(blockEl, { keepCols: keepAll });
    await refreshBlockFilterCols(blockEl);
    await Promise.all([...blockEl.querySelectorAll('.source-line')].map((row) => refreshLineFilterCols(row, blockEl)));
    if (!sheets.length) toast(`「${resolved}」未找到 Sheet`, false);
    syncBenchmarkVisibility();
  }

  blockEl.querySelectorAll('.source-line').forEach((row, i) => {
    const src = sources[i] || {};
    wireSourceLine(blockEl, row, {
      sheet_name: src.sheet_name || '',
      column_header: src.column_header || '',
      row_filters: src.row_filters || [],
    });
  });

  const initFile = resolveFileKey(first.source_file_keyword || '', files);
  if (initFile) {
    await cascadeBlockFile(initFile, true);
  }
}

function inferAggregation(stored, dedupKeys) {
  if (!dedupKeys.length) return 'sum';
  if (stored === 'count_distinct') return 'count_distinct';
  return 'sum_dedup';
}

function partUsesDedup(part) {
  const agg = part.aggregation || 'sum';
  if (['sum_dedup', 'max_dedup', 'count_distinct'].includes(agg)) return true;
  return (part.dedup_keys || []).length > 0;
}

function partDateMeta(part) {
  return {
    date_filter_column: part?.date_filter_column || null,
    date_format: part?.date_format || null,
  };
}

function getReuseFieldOptions() {
  window.REUSE_FIELDS_BY_DS = window.REUSE_FIELDS_BY_DS || {};
  const byDs = window.REUSE_FIELDS_BY_DS;
  const key = currentDataSourceId;
  const list = byDs[key] || byDs[String(key)] || [];
  return list.filter((f) => f.code !== currentLogicalFieldCode);
}

async function refreshReuseFields() {
  if (!currentDataSourceId) return;
  const ex = currentLogicalFieldCode
    ? `?exclude=${encodeURIComponent(currentLogicalFieldCode)}`
    : '';
  const data = await apiFetch(`/api/data-sources/${currentDataSourceId}/mapped-fields${ex}`);
  if (!data?.fields) return;
  window.REUSE_FIELDS_BY_DS = window.REUSE_FIELDS_BY_DS || {};
  window.REUSE_FIELDS_BY_DS[currentDataSourceId] = data.fields;
}

/** API parts → UI 块（来源组 | 字段复用） */
function flatPartsToBlocks(flatParts) {
  if (!flatParts?.length) return [];
  return flatParts.map((p, i) => {
    if (p.ref_field_code) {
      return {
        type: 'field_ref',
        ref_field_code: p.ref_field_code,
        combine_op: i === 0 ? 'add' : (p.combine_op || 'add'),
        benchmark_keys: p.benchmark_keys || [],
      };
    }
    return {
      type: 'source',
      ...p,
      combine_op: i === 0 ? 'add' : (p.combine_op || 'add'),
      sources: partToSources(p),
    };
  });
}

function partToSources(part) {
  const partFilters = part.row_filters || [];
  if (part.sources?.length) {
    return part.sources.map((s, i) => ({
      source_file_keyword: s.source_file_keyword || null,
      sheet_name: s.sheet_name || '',
      column_header: s.column_header || '',
      combine_op: s.combine_op || 'add',
      row_filters: (s.row_filters?.length ? s.row_filters : (i === 0 && partFilters.length ? partFilters : [])),
    }));
  }
  return [{
    source_file_keyword: part.source_file_keyword || null,
    sheet_name: part.sheet_name || '',
    column_header: part.column_header || '',
    combine_op: 'add',
    row_filters: partFilters,
  }];
}

function fieldRefPartTemplate(part, idx) {
  const options = getReuseFieldOptions();
  const wrap = document.createElement('div');
  wrap.className = 'field-ref-part mapping-part-block';
  wrap.dataset.idx = idx;
  wrap.dataset.partType = 'field_ref';
  wrap.dataset.combineOp = part.combine_op || 'add';
  wrap.dataset.benchmarkPreset = (part.benchmark_keys || [])[0] || '';
  wrap._dateMeta = partDateMeta(part);
  wrap.innerHTML = `
    ${idx > 0 ? groupConnectorHtml(part.combine_op || 'add') : ''}
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-xs font-semibold text-teal-700 shrink-0">复用字段</span>
      <div class="ref-field-select flex-1 min-w-[12rem]"></div>
      <code class="ref-field-code text-xs text-slate-500 font-mono shrink-0"></code>
      <span class="ref-field-hint text-xs text-slate-400 shrink-0 hidden sm:inline">点击定位可编辑该字段</span>
      <button type="button" class="btn-goto-aux text-xs text-link shrink-0 hidden">定位</button>
      <button type="button" class="btn-rm-block text-xs text-red-600 hover:underline shrink-0 ml-auto">删除</button>
    </div>`;

  const gotoBtn = wrap.querySelector('.btn-goto-aux');
  const fieldSelect = new SelectField(wrap.querySelector('.ref-field-select'), {
    placeholder: options.length ? '选择已配置的字段' : '暂无其他已配字段',
    options: options.map((f) => ({
      value: f.code,
      label: f.name,
    })),
    value: part.ref_field_code || '',
    onChange: (code) => {
      wrap.querySelector('.ref-field-code').textContent = code ? `{field:${code}}` : '';
      syncGotoAuxButton(gotoBtn, code);
      syncBenchmarkVisibility();
    },
  });

  const syncGotoAuxButton = (btn, code) => {
    const meta = findReuseField(code);
    if (meta?.mapping_id) {
      btn.classList.remove('hidden');
      btn.title = meta.configured ? '打开该字段配置' : '打开并配置该字段';
    } else {
      btn.classList.add('hidden');
    }
  };

  if (part.ref_field_code) {
    wrap.querySelector('.ref-field-code').textContent = `{field:${part.ref_field_code}}`;
  }
  syncGotoAuxButton(gotoBtn, part.ref_field_code || fieldSelect.val());

  gotoBtn.onclick = () => {
    const meta = findReuseField(fieldSelect.val());
    if (meta?.mapping_id) goAuxFieldOnPage(meta.mapping_id);
  };

  const bOp = wrap.querySelector('.b-op');
  if (bOp) wireMappingOpCycle(bOp, { onChange: (v) => { wrap.dataset.combineOp = v; } });

  wrap.querySelector('.btn-rm-block').onclick = () => {
    wrap.remove();
    reindexParts();
  };

  wrap._getData = () => {
    const blockIdx = parseInt(wrap.dataset.idx, 10);
    const code = fieldSelect.val();
    return {
      ref_field_code: code || null,
      label: null,
      source_file_keyword: null,
      sheet_name: '',
      column_header: '',
      sources: [],
      aliases: [],
      combine_op: blockIdx === 0 ? 'add' : readMappingOp(wrap.querySelector('.b-op')) || wrap.dataset.combineOp || 'add',
      aggregation: 'sum',
      dedup_keys: [],
      date_filter_column: wrap._dateMeta?.date_filter_column || null,
      date_format: wrap._dateMeta?.date_format || null,
      exclude_sample: false,
      exclude_review: false,
      join_to_orders: false,
      join_keys: [],
      benchmark_keys: readBenchmarkKeys(wrap),
      row_filters: [],
    };
  };

  return wrap;
}

function renderPartBlock(part, idx) {
  if (part.type === 'field_ref') return fieldRefPartTemplate(part, idx);
  return partTemplate(part, idx);
}

async function ensureAllColumns(dsId) {
  if (allColumnsCache[dsId]) return allColumnsCache[dsId];
  const data = await apiFetch(`/api/data-sources/${dsId}/catalog`);
  const cols = new Set();
  for (const f of data.files || []) {
    const sheets = f.sheets || {};
    Object.values(sheets).forEach((arr) => (arr || []).forEach((c) => cols.add(c)));
  }
  allColumnsCache[dsId] = [...cols].sort((a, b) => a.localeCompare(b));
  return allColumnsCache[dsId];
}

function readBenchmarkKeys(wrap) {
  const bench = wrap.querySelector('.group-connector__benchmark');
  if (bench?.classList.contains('hidden')) return [];
  const key = wrap._benchmarkCombo?.val()?.trim();
  return key ? [key] : [];
}

function getRefFieldSourceFiles(code) {
  const meta = findReuseField(code);
  const files = meta?.source_files || [];
  return new Set(files.filter(Boolean));
}

function getBlockSourceFiles(blockEl) {
  if (!blockEl) return new Set();
  if (blockEl.dataset.partType === 'field_ref') {
    const select = blockEl.querySelector('.ref-field-select select');
    return getRefFieldSourceFiles(select?.value || '');
  }
  const files = new Set();
  const blockFile = blockEl._sourceState?.file;
  if (blockFile) files.add(blockFile);
  return files;
}

function sameSourceFileSet(a, b) {
  if (!a.size && !b.size) return true;
  if (!a.size || !b.size) return false;
  if (a.size !== b.size) return false;
  return [...a].every((f) => b.has(f));
}

function blocksShareSameFile(prevEl, currEl) {
  return sameSourceFileSet(getBlockSourceFiles(prevEl), getBlockSourceFiles(currEl));
}

function syncBenchmarkVisibility() {
  const blocks = [...document.querySelectorAll('#partsContainer .mapping-part-block')];
  blocks.forEach((el, i) => {
    if (i === 0) return;
    const bench = el.querySelector(':scope > .group-connector .group-connector__benchmark');
    if (!bench) return;
    const need = !blocksShareSameFile(blocks[i - 1], el);
    bench.classList.toggle('hidden', !need);
    if (!need) {
      el._benchmarkCombo?.destroy?.();
      el._benchmarkCombo = null;
    } else if (!el._benchmarkCombo) {
      const preset = el.dataset.benchmarkPreset || DEFAULT_BENCHMARK_KEY;
      wireBenchmarkCombo(el, { benchmark_keys: preset ? [preset] : [] }).catch(() => {});
    }
  });
}

async function wireBenchmarkCombo(wrap, part = {}) {
  const slot = wrap.querySelector('.b-benchmark-wrap');
  if (!slot) return;
  const cols = await ensureAllColumns(currentDataSourceId);
  const blockIdx = parseInt(wrap.dataset.idx, 10);
  const preset = (part.benchmark_keys || [])[0]
    || (blockIdx > 0 ? DEFAULT_BENCHMARK_KEY : '');
  wrap._benchmarkCombo = new SearchCombo(slot, cols, {
    value: preset,
    placeholder: '如 Order ID',
    emptyHint: '搜索列头',
  });
}

function groupConnectorHtml(combineOp = 'add') {
  return `
    <div class="group-connector">
      <span class="group-connector__label">组间</span>
      ${mappingOpCycleHtml(combineOp, 'b-op')}
      <div class="group-connector__benchmark">
        <span class="group-connector__label">基准字段</span>
        <div class="b-benchmark-wrap min-w-[7.5rem] flex-1 max-w-[11rem]"></div>
      </div>
    </div>`;
}

function withinGroupOpSelectHtml(combineOp = 'add') {
  return mappingOpCycleHtml(combineOp, 's-row-op');
}

function rowFilterSectionHtml() {
  return `
    <details class="row-filter-section row-filter-section--per-col">
      <summary class="row-filter-summary">
        <span class="row-filter-summary__label">行筛选</span>
        <span class="row-filter-summary__preview hidden"></span>
        <span class="row-filter-summary__count hidden tabular-nums"></span>
      </summary>
      <div class="row-filter-body">
        <p class="filter-panel-desc">本列取数前先按下列条件筛行（全部 AND）</p>
        <p class="filter-col-hint filter-col-hint--inline hidden"></p>
        <div class="filter-panel-list"></div>
        <button type="button" class="btn-add-filter-row text-link text-xs">+ 添加条件</button>
      </div>
    </details>`;
}

function lineFilterScope(lineEl) {
  return lineEl.closest('.source-line-stack') || lineEl;
}

function buildSourceLine(blockEl, src, srcIdx) {
  const stack = document.createElement('div');
  stack.className = 'source-line-stack';
  const row = document.createElement('div');
  row.className = 'source-cols-row source-line';
  const isFirst = srcIdx === 0;
  row.innerHTML = isFirst
    ? `
    <div class="source-cols-row__field">
      <label class="source-field-label">来源</label>
      <div class="g-block-file"></div>
    </div>
    <div class="source-cols-row__field">
      <label class="source-field-label">Sheet</label>
      <div class="s-sheet-combo"></div>
    </div>
    <div class="source-cols-row__field">
      <label class="source-field-label">列头</label>
      <div class="s-col-combo"></div>
    </div>
    <button type="button" class="btn-rm-src source-cols-row__act" title="删除此列" aria-label="删除此列">×</button>`
    : `
    <div class="source-cols-row__field source-cols-row__field--op">
      <label class="source-field-label source-field-label--ghost">来源</label>
      <div class="source-cols-row__op-wrap">
        ${withinGroupOpSelectHtml(src.combine_op || 'add')}
      </div>
    </div>
    <div class="source-cols-row__field">
      <label class="source-field-label">Sheet</label>
      <div class="s-sheet-combo"></div>
    </div>
    <div class="source-cols-row__field">
      <label class="source-field-label">列头</label>
      <div class="s-col-combo"></div>
    </div>
    <button type="button" class="btn-rm-src source-cols-row__act" title="删除此列" aria-label="删除此列">×</button>`;

  wireMappingOpCycle(row.querySelector('.s-row-op'));
  row.querySelector('.btn-rm-src').onclick = () => {
    const list = blockEl.querySelector('.sources-list');
    if (list.querySelectorAll('.source-line').length <= 1) {
      toast('每组至少保留一列', false);
      return;
    }
    destroyFilterEntries(row);
    stack.remove();
    refreshBlockFilterCols(blockEl).catch(() => {});
    reindexSourcesInBlock(blockEl);
  };
  stack.appendChild(row);
  stack.insertAdjacentHTML('beforeend', rowFilterSectionHtml());
  return stack;
}

function reindexSourcesInBlock(blockEl) {
  blockEl.querySelectorAll('.source-line').forEach((line, srcIdx) => {
    if (srcIdx === 0) return;
    wireMappingOpCycle(line.querySelector('.s-row-op'));
  });
}

function syncGroupConnectors() {
  document.querySelectorAll('.mapping-part-block').forEach((el, i) => {
    let conn = el.querySelector(':scope > .group-connector');
    if (i === 0) {
      conn?.remove();
      return;
    }
    const op = el.dataset.combineOp || readMappingOp(el.querySelector('.b-op')) || 'add';
    if (!conn) {
      el.insertAdjacentHTML('afterbegin', groupConnectorHtml(op));
      conn = el.querySelector(':scope > .group-connector');
    }
    const btn = conn?.querySelector('.b-op');
    if (btn) {
      setMappingOpCycle(btn, op);
      wireMappingOpCycle(btn, { onChange: (v) => { el.dataset.combineOp = v; } });
    }
  });
  syncBenchmarkVisibility();
}

function filterOpLabel(op) {
  return FILTER_OPS.find((o) => o.v === op)?.l || op;
}

function formatFilterPreview(filters) {
  if (!filters?.length) return '';
  return filters.map((f) => {
    const op = filterOpLabel(f.op || 'eq');
    if (f.op === 'nonempty' || f.op === 'empty') return `${f.column} ${op}`;
    const vals = (f.values || []).join(', ');
    return vals ? `${f.column} ${op} ${vals}` : `${f.column} ${op}`;
  }).join(' · ');
}

function collectRowFilters(lineEl) {
  return (lineEl._filterEntries || []).map((e) => e.get()).filter((f) => f.column);
}

function updateFilterColHint(lineEl, blockEl) {
  const scope = lineFilterScope(lineEl);
  const hint = scope.querySelector('.filter-col-hint--inline');
  if (!hint) return;
  const block = blockEl || lineEl.closest('.mapping-part-block');
  const hasFile = !!block?._sourceState?.file;
  const hasCols = (lineEl._filterCols || []).length > 0;
  hint.classList.toggle('hidden', hasFile && hasCols);
  hint.textContent = !hasFile
    ? '请先选择上方来源文件，再配置筛选列头。'
    : '请先选择 Sheet，再配置筛选列头。';
}

function updateFilterSummary(lineEl, filters) {
  const scope = lineFilterScope(lineEl);
  const preview = scope.querySelector('.row-filter-summary__preview');
  const countEl = scope.querySelector('.row-filter-summary__count');
  const n = filters?.length || 0;
  if (preview) {
    preview.textContent = formatFilterPreview(filters);
    preview.classList.toggle('hidden', !n);
  }
  if (countEl) {
    countEl.textContent = n ? `${n} 条` : '';
    countEl.classList.toggle('hidden', !n);
  }
}

function commitFilterEntries(lineEl) {
  const filters = collectRowFilters(lineEl);
  lineEl._rowFilters = filters;
  updateFilterSummary(lineEl, filters);
}

function destroyFilterEntries(lineEl) {
  (lineEl._filterEntries || []).forEach((e) => e.colC?.destroy?.());
  lineEl._filterEntries = [];
}

function renderFilterRows(lineEl) {
  const scope = lineFilterScope(lineEl);
  const list = scope.querySelector('.filter-panel-list');
  if (!list) return;
  destroyFilterEntries(lineEl);
  list.innerHTML = '';
  const filters = lineEl._rowFilters || [];
  if (filters.length === 0) addFilterRow(lineEl);
  else filters.forEach((f) => addFilterRow(lineEl, f));
  commitFilterEntries(lineEl);
}

function bindFilterRowEvents(lineEl, entry) {
  const sync = () => commitFilterEntries(lineEl);
  entry.el.querySelector('.flt-op')?.addEventListener('change', sync);
  entry.el.querySelector('.flt-val')?.addEventListener('input', sync);
  entry.colC.input?.addEventListener('change', sync);
  const prevPick = entry.colC.onPick;
  entry.colC.onPick = (v) => {
    if (prevPick) prevPick(v);
    sync();
  };
}

function addFilterRow(lineEl, f = {}) {
  const scope = lineFilterScope(lineEl);
  const list = scope.querySelector('.filter-panel-list');
  if (!list) return;
  const cols = lineEl._filterCols || [];
  const row = document.createElement('div');
  row.className = 'filter-row';
  row.innerHTML = `
    <div class="filter-row__head">
      <label class="filter-row__label">列头</label>
      <div class="filter-row__col"></div>
    </div>
    <div class="filter-row__foot">
      <div class="filter-row__field">
        <label class="filter-row__label">条件</label>
        <select class="filter-row__op flt-op form-control">
          ${FILTER_OPS.map((o) => `<option value="${o.v}" ${(f.op || 'eq') === o.v ? 'selected' : ''}>${o.l}</option>`).join('')}
        </select>
      </div>
      <div class="filter-row__field filter-row__field--val">
        <label class="filter-row__label">值</label>
        <input class="filter-row__val flt-val form-control" placeholder="多个用逗号；介于填 小,大" value="${(f.values || []).join(', ')}">
      </div>
      <button type="button" class="flt-rm btn-rm-src" aria-label="删除条件">×</button>
    </div>`;
  const colC = new SearchCombo(row.querySelector('.filter-row__col'), cols, {
    value: f.column || '',
    placeholder: '搜索列头',
    emptyHint: cols.length ? '无匹配列头' : '请先选择来源文件',
    size: 'md',
    inputClass: 'form-control filter-row__col-input font-mono',
    portal: true,
  });
  const entry = {
    el: row,
    colC,
    get: () => ({
      column: colC.val(),
      op: row.querySelector('.flt-op').value,
      values: row.querySelector('.flt-val').value.split(',').map((s) => s.trim()).filter(Boolean),
    }),
  };
  bindFilterRowEvents(lineEl, entry);
  row.querySelector('.flt-rm').onclick = () => {
    const entries = lineEl._filterEntries || [];
    if (entries.length <= 1) {
      colC.set('');
      row.querySelector('.flt-val').value = '';
      row.querySelector('.flt-op').value = 'eq';
      commitFilterEntries(lineEl);
      return;
    }
    const i = entries.indexOf(entry);
    if (i >= 0) entries.splice(i, 1);
    entry.colC?.destroy?.();
    row.remove();
    commitFilterEntries(lineEl);
  };
  if (!lineEl._filterEntries) lineEl._filterEntries = [];
  lineEl._filterEntries.push(entry);
  list.appendChild(row);
}

function initRowFilterSection(lineEl, blockEl) {
  if (lineEl._filterSectionWired) return;
  lineEl._filterSectionWired = true;
  const scope = lineFilterScope(lineEl);
  const section = scope.querySelector('.row-filter-section');
  if (!section) return;
  const btnAdd = scope.querySelector('.btn-add-filter-row');
  lineEl._filterEntries = [];

  const ensureColsAndRender = () => refreshLineFilterCols(lineEl, blockEl).then(() => {
    if (!lineEl._filterEntries?.length) renderFilterRows(lineEl);
    else (lineEl._filterEntries || []).forEach((e) => e.colC?.setOpts(lineEl._filterCols || []));
  });

  section.addEventListener('toggle', () => {
    if (section.open) ensureColsAndRender();
  });

  btnAdd?.addEventListener('click', () => {
    refreshLineFilterCols(lineEl, blockEl).then(() => {
      addFilterRow(lineEl);
      commitFilterEntries(lineEl);
    });
  });

  updateFilterSummary(lineEl, lineEl._rowFilters || []);
  if ((lineEl._rowFilters || []).length > 0) {
    section.open = true;
    ensureColsAndRender();
  }
}

function partTemplate(part, idx) {
  const dedupCol = (part.dedup_keys || [])[0] || '';
  const useDedup = partUsesDedup(part);
  const joinKeys = (part.join_keys && part.join_keys.length) ? part.join_keys : ['Order ID'];

  const wrap = document.createElement('div');
  wrap.className = 'part-row mapping-part-block';
  wrap.dataset.idx = idx;
  wrap.dataset.combineOp = part.combine_op || 'add';
  wrap.dataset.benchmarkPreset = (part.benchmark_keys || [])[0] || '';
  wrap._dateMeta = partDateMeta(part);
  wrap.innerHTML = `
    ${idx > 0 ? groupConnectorHtml(part.combine_op || 'add') : ''}
    <div class="mapping-part-block__head">
      <span class="mapping-part-block__title">来源组 <span class="group-title-num">${idx + 1}</span></span>
    </div>
    <input type="hidden" class="p-agg-stored" value="${part.aggregation || 'sum'}">
    <div class="sources-list"></div>
    <button type="button" class="btn-add-src mt-1 text-xs text-link">+ 添加列</button>
    <div class="mb-2 dedup-section mt-2">
      <label class="inline-flex items-center gap-1.5 text-xs text-slate-600 cursor-pointer select-none">
        <input type="checkbox" class="p-enable-dedup" ${useDedup ? 'checked' : ''}>
        <span>去重</span>
      </label>
      <div class="dedup-fields mt-1.5 ${useDedup ? '' : 'hidden'}">
        <div class="dedup-line dedup-line--compact">
          <label class="source-field-label">去重键列头</label>
          <div class="p-dedup-col-combo"></div>
        </div>
      </div>
    </div>
    <details class="mt-1" ${hasAdvanced(part) ? 'open' : ''}>
      <summary class="text-xs text-link cursor-pointer select-none">高级规则</summary>
      <div class="mt-2 space-y-3 border-t border-slate-200 pt-2">
        <div class="flex flex-wrap gap-4 text-xs text-slate-600">
          <label class="inline-flex items-center gap-1"><input type="checkbox" class="p-exsample" ${part.exclude_sample ? 'checked' : ''}> 排除样品单</label>
          <label class="inline-flex items-center gap-1"><input type="checkbox" class="p-exreview" ${part.exclude_review ? 'checked' : ''}> 排除刷单单</label>
          <label class="inline-flex items-center gap-1" title="当日下单且当日退款的订单不计入本组取数">
            <input type="checkbox" class="p-exsame-day-refund" ${part.exclude_same_day_refund ? 'checked' : ''}> 排除当日退单
          </label>
          <label class="inline-flex items-center gap-1"><input type="checkbox" class="p-join" ${part.join_to_orders ? 'checked' : ''}> 关联数据主表有效行</label>
        </div>
        <div class="join-keys-section ${part.join_to_orders ? '' : 'hidden'}">
          <label class="source-field-label"><span class="field-required-mark" aria-hidden="true">*</span>关联匹配键</label>
          <div class="join-keys-list"></div>
        </div>
      </div>
    </details>
    <div class="mt-2 flex justify-end">
      <button type="button" class="btn-rm-block text-xs text-red-600 hover:underline">删除本组</button>
    </div>`;

  const sources = partToSources(part);
  wrap._filterCols = [];

  const list = wrap.querySelector('.sources-list');
  sources.forEach((src, si) => list.appendChild(buildSourceLine(wrap, src, si)));
  bootstrapBlockSource(wrap, sources, { blockIdx: idx });

  const bOp = wrap.querySelector('.b-op');
  if (bOp) wireMappingOpCycle(bOp, { onChange: (v) => { wrap.dataset.combineOp = v; } });

  wrap.querySelector('.btn-add-src').onclick = () => {
    const st = wrap._sourceState || {};
    const firstRow = wrap.querySelector('.source-line');
    const defaultSheet = firstRow?._sheetSelect?.val() || st.sheets?.[0] || '';
    const stack = buildSourceLine(wrap, { sheet_name: defaultSheet, column_header: '' }, list.querySelectorAll('.source-line').length);
    list.appendChild(stack);
    const row = stack.querySelector('.source-line');
    wireSourceLine(wrap, row, { sheet_name: defaultSheet, column_header: '', row_filters: [] });
    reindexSourcesInBlock(wrap);
  };

  const dedupCb = wrap.querySelector('.p-enable-dedup');
  const dedupFields = wrap.querySelector('.dedup-fields');
  dedupCb.addEventListener('change', () => {
    dedupFields.classList.toggle('hidden', !dedupCb.checked);
  });

  wrap._dedupColCombo = new SearchCombo(wrap.querySelector('.p-dedup-col-combo'), wrap._filterCols || [], {
    value: dedupCol,
    placeholder: '搜索去重键列头',
    emptyHint: '请先在上行选择 Sheet',
  });

  const joinCb = wrap.querySelector('.p-join');
  const joinSection = wrap.querySelector('.join-keys-section');
  const joinList = wrap.querySelector('.join-keys-list');
  wrap._joinKeyCombos = [];

  function renderJoinKeys(keys) {
    const normalized = keys.length ? [...keys] : [''];
    joinList.innerHTML = '';
    wrap._joinKeyCombos = [];
    normalized.forEach((keyVal, ki) => {
      const isFirst = ki === 0;
      const isLast = ki === normalized.length - 1;
      const line = document.createElement('div');
      line.className = 'join-key-row';
      line.innerHTML = `
        <div class="join-key-row__field">
          <div class="jk-col"></div>
        </div>
        <div class="join-key-row__actions">
          ${!isFirst ? '<button type="button" class="btn-join-key-rm" aria-label="删除匹配键">×</button>' : ''}
          ${isLast ? '<button type="button" class="btn-join-key-add" aria-label="添加匹配键">+</button>' : ''}
        </div>`;
      const combo = new SearchCombo(line.querySelector('.jk-col'), wrap._filterCols || [], {
        value: keyVal,
        placeholder: '如 Order ID',
        emptyHint: '请先选择来源',
      });
      line.querySelector('.btn-join-key-rm')?.addEventListener('click', () => {
        if (normalized.length <= 1) return;
        normalized.splice(ki, 1);
        renderJoinKeys(normalized);
      });
      line.querySelector('.btn-join-key-add')?.addEventListener('click', () => {
        normalized.push('');
        renderJoinKeys(normalized);
      });
      wrap._joinKeyCombos.push(combo);
      joinList.appendChild(line);
    });
  }
  renderJoinKeys(part.join_to_orders ? [...joinKeys] : ['Order ID']);
  joinCb.addEventListener('change', () => {
    const on = joinCb.checked;
    joinSection.classList.toggle('hidden', !on);
    if (on && wrap._joinKeyCombos.every((c) => !c.val())) {
      renderJoinKeys(['Order ID']);
    }
  });

  wrap.querySelector('.btn-rm-block').onclick = () => {
    if (document.querySelectorAll('.mapping-part-block').length <= 1) {
      toast('至少保留一项取数规则', false);
      return;
    }
    wrap.remove();
    reindexParts();
  };

  if (idx > 0) {
    const adv = wrap.querySelector('details');
    if (adv && !hasAdvanced(part)) adv.removeAttribute('open');
  }

  wrap._getData = () => {
    const enableDedup = wrap.querySelector('.p-enable-dedup').checked;
    const dedupCol = enableDedup ? wrap._dedupColCombo?.val() : '';
    const dedup_keys = dedupCol ? [dedupCol] : [];
    const stored = wrap.querySelector('.p-agg-stored')?.value || 'sum';
    const sources = [...wrap.querySelectorAll('.source-line')].map((line) => line._getSource());
    const first = sources[0] || {};
    const blockIdx = parseInt(wrap.dataset.idx, 10);
    const joinOn = wrap.querySelector('.p-join').checked;
    const join_keys = joinOn
      ? wrap._joinKeyCombos.map((c) => (c.val() || '').trim())
      : [];
    return {
      label: null,
      source_file_keyword: first.source_file_keyword || null,
      sheet_name: first.sheet_name || '',
      column_header: first.column_header || '',
      sources,
      aliases: [],
      combine_op: blockIdx === 0 ? 'add' : readMappingOp(wrap.querySelector('.b-op')) || wrap.dataset.combineOp || 'add',
      aggregation: enableDedup ? inferAggregation(stored, dedup_keys) : 'sum',
      dedup_keys,
      date_filter_column: wrap._dateMeta?.date_filter_column || null,
      date_format: wrap._dateMeta?.date_format || null,
      exclude_sample: wrap.querySelector('.p-exsample').checked,
      exclude_review: wrap.querySelector('.p-exreview').checked,
      exclude_same_day_refund: wrap.querySelector('.p-exsame-day-refund')?.checked || false,
      join_to_orders: joinOn,
      join_keys: joinOn ? join_keys : [],
      benchmark_keys: readBenchmarkKeys(wrap),
      row_filters: [],
    };
  };

  return wrap;
}

function hasAdvanced(part) {
  return !!(part.exclude_sample || part.exclude_review || part.exclude_same_day_refund || part.join_to_orders);
}

function reindexParts() {
  document.querySelectorAll('.mapping-part-block').forEach((el, i) => {
    el.dataset.idx = i;
    const num = el.querySelector('.group-title-num');
    if (num) num.textContent = String(i + 1);
    if (el.classList.contains('part-row')) reindexSourcesInBlock(el);
  });
  syncGroupConnectors();
}

function addPartRow() {
  const container = document.getElementById('partsContainer');
  if (!container) return;
  const idx = container.querySelectorAll('.mapping-part-block').length;
  const card = partTemplate({ type: 'source', combine_op: 'add', aggregation: 'sum', dedup_keys: [], aliases: [], sources: [] }, idx);
  container.appendChild(card);
  reindexParts();
}

async function addFieldRefRow() {
  const container = document.getElementById('partsContainer');
  if (!container) return;
  await refreshReuseFields();
  const options = getReuseFieldOptions();
  if (!options.length) {
    toast('暂无其他已配置字段可复用（请先保存其他字段的映射）', false);
    return;
  }
  const idx = container.querySelectorAll('.mapping-part-block').length;
  container.appendChild(fieldRefPartTemplate({
    type: 'field_ref',
    ref_field_code: options[0].code,
    combine_op: 'add',
  }, idx));
  reindexParts();
}

function renderParts() {
  const c = document.getElementById('partsContainer');
  if (!c) {
    throw new Error('取数弹窗未加载，请刷新页面后重试');
  }
  c.innerHTML = '';
  if (!parts.length) parts = [{ type: 'source', combine_op: 'add', aggregation: 'sum', dedup_keys: [], aliases: [] }];
  parts.forEach((p, i) => c.appendChild(renderPartBlock(p, i)));
  syncGroupConnectors();
}

async function openModal(mode, mappingId = null, opts = {}) {
  const session = ++modalSession;
  currentMappingId = mappingId;
  const modal = document.getElementById('mappingModal');
  const alreadyOpen = window.AppModal?.isOpen(modal);
  document.getElementById('newMappingFields').classList.toggle('hidden', mode !== 'create');
  document.getElementById('btnDeleteMapping').classList.toggle('hidden', mode !== 'edit');

  if (!alreadyOpen) {
    openWithTransition(modal);
  } else if (opts.stacked) {
    const panel = document.getElementById('mappingPanel');
    panel?.classList.add('is-nested-enter');
    setTimeout(() => panel?.classList.remove('is-nested-enter'), 240);
  }
  const partsContainer = document.getElementById('partsContainer');
  if (partsContainer) {
    partsContainer.innerHTML = `
      <div class="modal-loading" aria-busy="true">
        <div class="modal-loading__bar"></div>
        <div class="modal-loading__bar modal-loading__bar--short"></div>
        <p class="text-xs text-slate-500 mt-4">加载配置中…</p>
      </div>`;
  }

  try {
    if (mode === 'create') {
      const dsSelect = document.getElementById('newDataSource');
      if (dsSelect && window.CURRENT_STORE_DS_ID) {
        dsSelect.value = String(window.CURRENT_STORE_DS_ID);
      }
      currentDataSourceId = parseInt(dsSelect?.value || '0', 10);
      currentLogicalFieldCode = '';
      document.getElementById('modalTitle').textContent = '新增日报字段';
      document.getElementById('modalSubtitle').textContent = '配置多条取数规则，支持跨文件加减组合';
      document.getElementById('mappingLabel').value = '';
      document.getElementById('mappingGroup').value = '';
      document.getElementById('mappingSort').value = '0';
      const perOrderInputNew = document.getElementById('perOrderAmount');
      if (perOrderInputNew) perOrderInputNew.value = '1';
      const perOrderBasisNew = document.getElementById('perOrderBasis');
      if (perOrderBasisNew) perOrderBasisNew.value = 'valid_orders';
      const ratioPercentNew = document.getElementById('ratioPercent');
      if (ratioPercentNew) ratioPercentNew.value = '100';
      parts = [{ type: 'source', combine_op: 'add', aggregation: 'sum', dedup_keys: [], aliases: [] }];
      await ensureFiles(currentDataSourceId);
      await refreshReuseFields();
      if (session !== modalSession) return;
      ensureRatioBaseSelect('');
      setActiveTab('placeholder');
    } else {
      const res = await fetch(`/api/mappings/${mappingId}`);
      if (!res.ok) throw new Error('加载映射失败');
      const data = await res.json();
      if (session !== modalSession) return;
      currentDataSourceId = data.data_source_id;
      currentLogicalFieldCode = data.logical_field_code || '';
      document.getElementById('modalTitle').textContent = data.label || data.logical_field_name || '配置日报字段';
      document.getElementById('modalSubtitle').textContent = '';
      document.getElementById('mappingLabel').value = data.label || data.logical_field_name || '';
      document.getElementById('mappingGroup').value = data.report_group || '';
      document.getElementById('mappingSort').value = String(data.sort_order || 0);
      const perOrderInputEdit = document.getElementById('perOrderAmount');
      if (perOrderInputEdit) {
        perOrderInputEdit.value = data.per_order_amount != null ? String(data.per_order_amount) : '1';
      }
      const perOrderBasisEdit = document.getElementById('perOrderBasis');
      if (perOrderBasisEdit) perOrderBasisEdit.value = data.per_order_basis || 'valid_orders';
      const ratioPercentEdit = document.getElementById('ratioPercent');
      if (ratioPercentEdit) ratioPercentEdit.value = data.ratio_percent != null ? String(data.ratio_percent) : '100';
      const lineType = (data.line_type || '').toLowerCase();
      const hasParts = data.parts.length > 0;
      const allRef = hasParts && data.parts.every((p) => p.ref_field_code);
      let editTab = 'placeholder';
      if (lineType === 'per_order') editTab = 'per_order';
      else if (lineType === 'ratio') editTab = 'ratio';
      else if (lineType === 'manual') editTab = 'placeholder';
      else if (allRef) editTab = 'reuse';
      else if (hasParts) editTab = 'fetch';
      parts = flatPartsToBlocks(data.parts.length ? data.parts : [{ combine_op: 'add', aggregation: 'sum', dedup_keys: [] }]);
      await ensureFiles(currentDataSourceId);
      await refreshReuseFields();
      if (session !== modalSession) return;
      ensureRatioBaseSelect(data.ratio_base_code || '');
      setActiveTab(editTab);
    }
    if (session !== modalSession) return;
    renderParts();
    updateNestedChrome();
    if (!alreadyOpen || opts.stacked) focusMappingModal();
  } catch (err) {
    if (session !== modalSession) return;
    toast(err.message || '打开配置失败', false);
    if (opts.stacked && mappingContextStack.length) {
      restoreMappingFormState(mappingContextStack.pop()).catch(() => {});
    } else if (!mappingContextStack.length) {
      closeModal();
    }
  }
}

function openWithTransition(modal) {
  window.AppModal?.open(modal);
}

function closeModal() {
  if (mappingContextStack.length) {
    modalSession += 1;
    const state = mappingContextStack.pop();
    restoreMappingFormState(state).catch(() => {});
    return;
  }
  modalSession += 1;
  mappingContextStack.length = 0;
  const modal = document.getElementById('mappingModal');
  modal?.classList.remove('mapping-modal--stacked');
  window.AppModal?.close(modal);
}

function bindMappingModal(modal) {
  modal.querySelectorAll('[data-modal-close]').forEach((el) => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      closeModal();
    });
  });
  modal.querySelector('.app-modal__backdrop')?.addEventListener('click', () => closeModal());
}

function collectParts() {
  return [...document.querySelectorAll('.mapping-part-block')].map((el) => el._getData());
}

async function saveMapping() {
  const lineTypeByTab = {
    placeholder: 'manual',
    per_order: 'per_order',
    ratio: 'ratio',
    fetch: 'fetch',
    reuse: 'fetch',
  };
  const body = {
    label: document.getElementById('mappingLabel')?.value.trim() || null,
    report_group: document.getElementById('mappingGroup')?.value.trim() || null,
    sort_order: parseInt(document.getElementById('mappingSort')?.value, 10) || 0,
    line_type: lineTypeByTab[activeTab] || 'fetch',
    parts: [],
  };

  if (activeTab === 'per_order') {
    const amt = parseFloat(document.getElementById('perOrderAmount')?.value);
    if (!(amt >= 0)) {
      toast('请填写每单金额（≥ 0）', false);
      return;
    }
    body.per_order_amount = amt;
    body.per_order_basis = document.getElementById('perOrderBasis')?.value || 'valid_orders';
  } else if (activeTab === 'ratio') {
    const base = ratioBaseSelect?.val() || '';
    const pct = parseFloat(document.getElementById('ratioPercent')?.value);
    if (!base) {
      toast('请选择按比例的基准字段', false);
      return;
    }
    if (!(pct >= 0)) {
      toast('请填写比例（≥ 0）', false);
      return;
    }
    body.ratio_base_code = base;
    body.ratio_percent = pct;
  } else if (activeTab === 'placeholder') {
    // 占位无其它配置
  } else {
    body.parts = collectParts();
    if (!body.parts.length || body.parts.some((p) => {
      if (p.ref_field_code) return !p.ref_field_code;
      const srcs = p.sources?.length ? p.sources : [{ sheet_name: p.sheet_name, column_header: p.column_header }];
      if (srcs.some((s) => !s.sheet_name || !s.column_header)) return true;
      if (p.join_to_orders && (!p.join_keys?.length || p.join_keys.some((k) => !k))) return true;
      return false;
    })) {
      toast('请完整配置取数规则（含关联匹配键），或选择要复用的字段', false);
      return;
    }
  }

  let url = '/api/mappings';
  let method = 'POST';
  if (currentMappingId) {
    url = `/api/mappings/${currentMappingId}`;
    method = 'PUT';
  } else {
    body.data_source_id = parseInt(document.getElementById('newDataSource').value, 10);
    const lfVal = document.getElementById('newLogicalField').value;
    if (lfVal) body.logical_field_id = parseInt(lfVal, 10);
  }

  const res = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const data = await res.json();
  if (!res.ok) return toast(data.detail || '保存失败', false);
  await refreshReuseFields();
  if (mappingContextStack.length) {
    const state = mappingContextStack.pop();
    await restoreMappingFormState(state);
    toast('保存成功');
    return;
  }
  closeModal();
  toast('保存成功');
  setTimeout(() => location.reload(), 600);
}

document.addEventListener('DOMContentLoaded', () => {
  const mappingModal = document.getElementById('mappingModal');
  if (mappingModal) bindMappingModal(mappingModal);
  document.getElementById('modalBackLink')?.addEventListener('click', () => closeModal());
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    const modal = document.getElementById('mappingModal');
    if (!window.AppModal?.isOpen(modal) || !mappingContextStack.length) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    closeModal();
  }, true);
  document.getElementById('btnNewMapping')?.addEventListener('click', () => {
    openModal('create').catch(() => {});
  });
  document.body.addEventListener('click', (e) => {
    const btn = e.target.closest('.btn-edit');
    if (!btn || btn.closest('#formulaModal')) return;
    openModal('edit', parseInt(btn.dataset.id, 10)).catch(() => {});
  });
  document.querySelectorAll('.mapping-tab').forEach((btn) => {
    btn.addEventListener('click', () => setActiveTab(btn.dataset.tab));
  });
  document.getElementById('btnAddPart')?.addEventListener('click', addPartRow);
  document.getElementById('btnAddFieldRef')?.addEventListener('click', () => {
    addFieldRefRow().catch(() => {});
  });
  document.getElementById('btnSaveMapping')?.addEventListener('click', saveMapping);
  document.getElementById('btnDeleteMapping')?.addEventListener('click', async () => {
    if (!confirm('确定删除？')) return;
    const res = await fetch(`/api/mappings/${currentMappingId}`, { method: 'DELETE' });
    if (!res.ok) return;
    toast('已删除');
    await refreshReuseFields();
    if (mappingContextStack.length) {
      const state = mappingContextStack.pop();
      await restoreMappingFormState(state);
      return;
    }
    closeModal();
    setTimeout(() => location.reload(), 600);
  });
  document.getElementById('newDataSource')?.addEventListener('change', (e) => {
    currentDataSourceId = parseInt(e.target.value, 10);
    refreshReuseFields()
      .then(() => ensureFiles(currentDataSourceId))
      .then(renderParts);
  });

  const pendingId = sessionStorage.getItem('openMappingId');
  if (pendingId) {
    sessionStorage.removeItem('openMappingId');
    setTimeout(() => openModal('edit', parseInt(pendingId, 10)).catch(() => {}), 200);
  }
});

window.openMappingModal = (mappingId) => {
  openModal('edit', mappingId).catch(() => {});
};
