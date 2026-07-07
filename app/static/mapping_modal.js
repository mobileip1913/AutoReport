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

const DEFAULT_JOIN_KEYS = ['Order ID', 'SKU ID'];
const DEFAULT_BENCHMARK_KEY = 'Order ID';

let openFilterPartWrap = null;
const allColumnsCache = {};

let currentMappingId = null;
let currentDataSourceId = null;
let currentLogicalFieldCode = '';
let parts = [];
let modalSession = 0;

function findReuseField(code) {
  if (!code) return null;
  const list = window.REUSE_FIELDS_BY_DS?.[currentDataSourceId]
    || window.REUSE_FIELDS_BY_DS?.[String(currentDataSourceId)]
    || [];
  return list.find((f) => f.code === code) || null;
}

function goAuxFieldOnPage(mappingId) {
  closeModal();
  setTimeout(() => {
    const row = document.getElementById(`aux-field-${mappingId}`);
    if (!row) {
      toast('请在本页「基础取数字段」区配置', false);
      return;
    }
    row.scrollIntoView({ behavior: 'smooth', block: 'center' });
    row.classList.add('ring-2', 'ring-sky-400', 'ring-offset-1');
    setTimeout(() => row.classList.remove('ring-2', 'ring-sky-400', 'ring-offset-1'), 2200);
  }, 220);
}

function toast(msg, ok = true) {
  const el = document.getElementById('toast') || document.getElementById('dailyToast');
  if (!el) return;
  el.textContent = msg;
  el.className = `fixed bottom-6 right-6 z-50 px-4 py-3 rounded-lg shadow-lg text-sm text-white ${ok ? 'bg-green-600' : 'bg-red-600'}`;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 2500);
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

function shortFileName(name) {
  if (!name) return '';
  const base = name.replace(/\.xlsx?$/i, '');
  return base.length > 28 ? `${base.slice(0, 28)}…` : base;
}

function fileSelectOptions(files) {
  return (files || []).map((f) => ({
    value: f.keyword,
    label: `${f.keyword}（${shortFileName(f.file_name)}）`,
  }));
}

class SelectField {
  constructor(container, { placeholder = '请选择', options = [], value = '', onChange = null } = {}) {
    this.container = container;
    this.placeholder = placeholder;
    this.onChange = onChange;
    if (!container) {
      this.select = null;
      return;
    }
    this.container.innerHTML = '';
    this.container.className = 'relative';
    this.select = document.createElement('select');
    this.select.className = 'w-full border rounded px-2 py-1.5 text-xs font-mono focus:ring-2 focus:ring-sky-200 outline-none bg-white';
    this.setOpts(options, placeholder);
    this.set(value);
    this.select.addEventListener('change', () => {
      if (this.onChange) this.onChange(this.val());
    });
    this.container.appendChild(this.select);
  }
  setOpts(options, placeholder) {
    if (!this.select) return;
    const ph = placeholder || this.placeholder;
    this.select.innerHTML = '';
    const empty = document.createElement('option');
    empty.value = '';
    empty.textContent = ph;
    this.select.appendChild(empty);
    (options || []).forEach((o) => {
      const opt = document.createElement('option');
      if (typeof o === 'string') {
        opt.value = o;
        opt.textContent = o;
      } else {
        opt.value = o.value;
        opt.textContent = o.label;
      }
      this.select.appendChild(opt);
    });
  }
  val() { return this.select?.value || ''; }
  set(v) { if (this.select) this.select.value = v || ''; }
  setDisabled(dis) {
    if (!this.select) return;
    this.select.disabled = !!dis;
    this.select.classList.toggle('opacity-50', !!dis);
  }
}

class SearchCombo {
  constructor(container, options, { value = '', placeholder = '搜索...', onPick = null, emptyHint = '无可选项' } = {}) {
    this.container = container;
    this.options = options;
    this.onPick = onPick;
    this.emptyHint = emptyHint;
    if (!container) {
      this.input = { value: '', addEventListener: () => {}, focus: () => {} };
      this.dropdown = null;
      return;
    }
    this.container.innerHTML = '';
    this.container.className = 'relative';
    this.input = document.createElement('input');
    this.input.type = 'text';
    this.input.value = value;
    this.input.placeholder = placeholder;
    this.input.className = 'w-full border rounded px-2 py-1.5 text-xs font-mono focus:ring-2 focus:ring-sky-200 outline-none';
    this.input.autocomplete = 'off';
    this.dropdown = document.createElement('div');
    this.dropdown.className = 'absolute z-50 left-0 right-0 mt-1 max-h-36 overflow-y-auto bg-white border rounded shadow-lg hidden';
    this.container.append(this.input, this.dropdown);
    this.input.addEventListener('focus', () => this.show(this.input.value));
    this.input.addEventListener('input', () => this.show(this.input.value));
    this.input.addEventListener('blur', () => setTimeout(() => this.dropdown.classList.add('hidden'), 150));
  }
  show(q) {
    if (!this.dropdown) return;
    const kw = (q || '').toLowerCase();
    const matched = this.options.filter((o) => o.toLowerCase().includes(kw));
    const list = matched.length ? matched : this.options;
    this.dropdown.innerHTML = '';
    if (!list.length) {
      const empty = document.createElement('div');
      empty.className = 'px-2 py-1.5 text-xs text-slate-400';
      empty.textContent = this.emptyHint;
      this.dropdown.appendChild(empty);
    } else {
      list.slice(0, 50).forEach((opt) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'block w-full text-left px-2 py-1.5 text-xs hover:bg-sky-50 font-mono';
        btn.textContent = opt;
        btn.onmousedown = (e) => {
          e.preventDefault();
          this.input.value = opt;
          this.dropdown.classList.add('hidden');
          if (this.onPick) this.onPick(opt);
        };
        this.dropdown.appendChild(btn);
      });
    }
    this.dropdown.classList.remove('hidden');
  }
  val() { return (this.input?.value || '').trim(); }
  set(val) { if (this.input) this.input.value = val || ''; }
  setOpts(opts) {
    this.options = opts || [];
    if (this.input && this.input === document.activeElement) this.show(this.input.value);
  }
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
  (blockEl._filterEntries || []).forEach((e) => e.colC?.setOpts(cols));
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
}

function wireSourceLine(blockEl, row, { sheet_name: sheetName = '', column_header: col = '' } = {}) {
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

  row._getSource = () => ({
    source_file_keyword: st.file || null,
    sheet_name: sheetSelect.val(),
    column_header: colCombo.val(),
    combine_op: row.querySelector('.s-row-op')?.value || 'add',
  });

  if (st.file && sheetName) {
    loadRowColumns(blockEl, row, sheetName, col);
  }
}

function refreshAllRowSheets(blockEl, { keepCols = true } = {}) {
  const st = blockEl._sourceState;
  blockEl.querySelectorAll('.source-line').forEach((row) => {
    const prevSheet = keepCols ? row._sheetSelect?.val() : '';
    const prevCol = keepCols ? row._colCombo?.val() : '';
    if (!row._sheetSelect) {
      wireSourceLine(blockEl, row, { sheet_name: prevSheet, column_header: prevCol });
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
    if (!sheets.length) toast(`「${resolved}」未找到 Sheet`, false);
  }

  blockEl.querySelectorAll('.source-line').forEach((row, i) => {
    const src = sources[i] || {};
    wireSourceLine(blockEl, row, {
      sheet_name: src.sheet_name || '',
      column_header: src.column_header || '',
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
  if (part.sources?.length) {
    return part.sources.map((s) => ({
      source_file_keyword: s.source_file_keyword || null,
      sheet_name: s.sheet_name || '',
      column_header: s.column_header || '',
      combine_op: s.combine_op || 'add',
    }));
  }
  return [{
    source_file_keyword: part.source_file_keyword || null,
    sheet_name: part.sheet_name || '',
    column_header: part.column_header || '',
    combine_op: 'add',
  }];
}

function fieldRefPartTemplate(part, idx) {
  const options = getReuseFieldOptions();
  const wrap = document.createElement('div');
  wrap.className = 'field-ref-part mapping-part-block border border-teal-200 rounded-xl p-3 bg-teal-50/40';
  wrap.dataset.idx = idx;
  wrap.dataset.partType = 'field_ref';
  wrap.dataset.combineOp = part.combine_op || 'add';
  wrap._dateMeta = partDateMeta(part);
  wrap.innerHTML = `
    ${idx > 0 ? groupConnectorHtml(part.combine_op || 'add') : ''}
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[11px] font-semibold aux-text shrink-0">复用字段</span>
      <div class="ref-field-select flex-1 min-w-[12rem]"></div>
      <code class="ref-field-code text-[10px] text-slate-500 font-mono shrink-0"></code>
      <span class="ref-field-hint text-[10px] text-slate-400 shrink-0">规则在本页「基础取数字段」</span>
      <button type="button" class="btn-goto-aux text-[11px] text-link shrink-0 hidden">定位 →</button>
      <button type="button" class="btn-rm-block text-[11px] text-red-500 hover:underline shrink-0 ml-auto">删除</button>
    </div>`;

  const gotoBtn = wrap.querySelector('.btn-goto-aux');
  const fieldSelect = new SelectField(wrap.querySelector('.ref-field-select'), {
    placeholder: options.length ? '选择已配置的字段' : '暂无其他已配字段',
    options: options.map((f) => ({
      value: f.code,
      label: `${f.name}（{field:${f.code}}）`,
    })),
    value: part.ref_field_code || '',
    onChange: (code) => {
      wrap.querySelector('.ref-field-code').textContent = code ? `{field:${code}}` : '';
      syncGotoAuxButton(gotoBtn, code);
    },
  });

  const syncGotoAuxButton = (btn, code) => {
    const meta = findReuseField(code);
    if (meta?.mapping_id) {
      btn.classList.remove('hidden');
      btn.title = meta.configured ? '在本页定位到该字段' : '在本页定位并配置该字段';
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
  if (bOp) bOp.onchange = () => { wrap.dataset.combineOp = bOp.value; };

  wrap.querySelector('.btn-rm-block').onclick = () => {
    wrap.remove();
    reindexParts();
  };

  if (idx > 0) wireBenchmarkCombo(wrap, part).catch(() => {});

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
      combine_op: blockIdx === 0 ? 'add' : (wrap.querySelector('.b-op')?.value || wrap.dataset.combineOp || 'add'),
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
  const key = wrap._benchmarkCombo?.val()?.trim();
  return key ? [key] : [];
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
  const isSub = combineOp === 'subtract';
  return `
    <div class="group-connector flex flex-wrap items-center gap-x-2 gap-y-1.5 mb-2 pb-2 border-b border-dashed border-amber-200/80">
      <span class="text-[10px] text-amber-700/80 whitespace-nowrap">组间</span>
      <select class="b-op shrink-0 w-12 border-2 border-amber-300 bg-amber-50 rounded px-1 py-1.5 text-sm font-bold text-amber-800 text-center cursor-pointer" title="与上一项之间的运算">
        <option value="add" ${!isSub ? 'selected' : ''}>＋</option>
        <option value="subtract" ${isSub ? 'selected' : ''}>−</option>
      </select>
      <span class="text-[10px] text-slate-500 whitespace-nowrap">基准字段</span>
      <div class="b-benchmark-wrap min-w-[7.5rem] flex-1 max-w-[11rem]"></div>
      <span class="text-[10px] text-slate-400 whitespace-nowrap">上一项 ⊕ 本项</span>
    </div>`;
}

function withinGroupOpSelectHtml(combineOp = 'add') {
  const isSub = combineOp === 'subtract';
  return `<select class="s-row-op w-full border border-emerald-200 bg-emerald-50 rounded px-0.5 py-1.5 text-xs font-bold text-emerald-800 text-center cursor-pointer" title="与本组前面各列如何合并（组内优先计算）">
    <option value="add" ${!isSub ? 'selected' : ''}>＋</option>
    <option value="subtract" ${isSub ? 'selected' : ''}>−</option>
  </select>`;
}

function buildSourceLine(blockEl, src, srcIdx) {
  const row = document.createElement('div');
  row.className = `source-line flex items-center gap-2 mb-1.5${srcIdx > 0 ? ' pl-1 border-l-2 border-emerald-200 ml-1' : ''}`;
  row.innerHTML = `
    <div class="s-op-wrap shrink-0 w-14 flex items-center justify-center">
      ${srcIdx === 0
    ? '<span class="text-[10px] text-slate-400">列</span>'
    : withinGroupOpSelectHtml(src.combine_op || 'add')}
    </div>
    <div class="flex-1 min-w-0">
      <label class="text-[10px] text-slate-500 block mb-0.5">Sheet</label>
      <div class="s-sheet-combo"></div>
    </div>
    <div class="flex-[1.2] min-w-0">
      <label class="text-[10px] text-slate-500 block mb-0.5">列头</label>
      <div class="s-col-combo"></div>
    </div>
    <button type="button" class="btn-rm-src shrink-0 self-end mb-0.5 w-8 h-8 rounded border border-slate-200 text-slate-400 hover:text-red-500 hover:border-red-200 text-sm" title="删除此列">×</button>`;

  row.querySelector('.btn-rm-src').onclick = () => {
    const list = blockEl.querySelector('.sources-list');
    if (list.querySelectorAll('.source-line').length <= 1) {
      toast('每组至少保留一列', false);
      return;
    }
    row.remove();
    refreshBlockFilterCols(blockEl).catch(() => {});
    reindexSourcesInBlock(blockEl);
  };
  return row;
}

function reindexSourcesInBlock(blockEl) {
    blockEl.querySelectorAll('.source-line').forEach((line, srcIdx) => {
    const opWrap = line.querySelector('.s-op-wrap');
    if (!opWrap) return;
    if (!opWrap) return;
    const isFirst = srcIdx === 0;
    const savedOp = line.querySelector('.s-row-op')?.value || 'add';
    line.classList.toggle('pl-1', !isFirst);
    line.classList.toggle('border-l-2', !isFirst);
    line.classList.toggle('border-emerald-200', !isFirst);
    line.classList.toggle('ml-1', !isFirst);
    opWrap.innerHTML = isFirst
      ? '<span class="text-[10px] text-slate-400">列</span>'
      : withinGroupOpSelectHtml(savedOp);
  });
}

function syncGroupConnectors() {
  document.querySelectorAll('.mapping-part-block').forEach((el, i) => {
    let conn = el.querySelector(':scope > .group-connector');
    if (i === 0) {
      conn?.remove();
      return;
    }
    const op = el.dataset.combineOp || el.querySelector('.b-op')?.value || 'add';
    if (!conn) {
      el.insertAdjacentHTML('afterbegin', groupConnectorHtml(op));
      conn = el.querySelector(':scope > .group-connector');
    }
    const sel = conn?.querySelector('.b-op');
    if (sel) {
      sel.value = op;
      sel.onchange = () => { el.dataset.combineOp = sel.value; };
    }
  });
}

function updateFilterBtnLabel(btn, count) {
  if (!btn) return;
  btn.textContent = count > 0 ? `筛选(${count})` : '筛选';
  btn.classList.toggle('text-sky-700', count > 0);
  btn.classList.toggle('font-medium', count > 0);
}

function closeAllFilterPanels() {
  document.querySelectorAll('.part-row .filter-panel').forEach((panel) => {
    panel.classList.add('hidden');
    const wrap = panel.closest('.part-row');
    wrap?.querySelector('.btn-open-filter')?.classList.remove('is-active');
  });
  openFilterPartWrap = null;
}

function closeFilterPanel(partWrap) {
  const panel = partWrap?.querySelector('.filter-panel');
  panel?.classList.add('hidden');
  partWrap?.querySelector('.btn-open-filter')?.classList.remove('is-active');
  if (openFilterPartWrap === partWrap) openFilterPartWrap = null;
}

function renderFilterPanel(partWrap) {
  const list = partWrap.querySelector('.filter-list');
  if (!list) return;
  list.innerHTML = '';
  partWrap._filterEntries = [];
  const filters = partWrap._rowFilters || [];
  if (filters.length === 0) addFilterRow(partWrap);
  else filters.forEach((f) => addFilterRow(partWrap, f));
}

function addFilterRow(partWrap, f = {}) {
  const list = partWrap.querySelector('.filter-list');
  if (!list) return;
  const cols = partWrap._filterCols || [];
  const row = document.createElement('div');
  row.className = 'flex gap-1 items-center';
  row.innerHTML = `
    <div class="flt-col flex-1"></div>
    <select class="flt-op border rounded px-1 py-1 text-[11px]">
      ${FILTER_OPS.map((o) => `<option value="${o.v}" ${(f.op || 'eq') === o.v ? 'selected' : ''}>${o.l}</option>`).join('')}
    </select>
    <input class="flt-val flex-1 border rounded px-2 py-1 text-[11px]" placeholder="值，多个用逗号；介于填 小,大" value="${(f.values || []).join(', ')}">
    <button type="button" class="flt-rm text-red-400 text-xs px-1">×</button>`;
  const colC = new SearchCombo(row.querySelector('.flt-col'), cols, {
    value: f.column || '',
    placeholder: '搜索列头',
    emptyHint: cols.length ? '无匹配列头' : '请先选择来源文件',
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
  row.querySelector('.flt-rm').onclick = () => {
    const i = (partWrap._filterEntries || []).indexOf(entry);
    if (i >= 0) partWrap._filterEntries.splice(i, 1);
    row.remove();
  };
  if (!partWrap._filterEntries) partWrap._filterEntries = [];
  partWrap._filterEntries.push(entry);
  list.appendChild(row);
}

function applyFilterPanel(partWrap) {
  const filters = (partWrap._filterEntries || []).map((e) => e.get()).filter((f) => f.column);
  partWrap._rowFilters = filters;
  updateFilterBtnLabel(partWrap.querySelector('.btn-open-filter'), filters.length);
  closeFilterPanel(partWrap);
}

function toggleFilterPanel(partWrap) {
  const panel = partWrap.querySelector('.filter-panel');
  if (!panel) return;
  const isOpen = !panel.classList.contains('hidden');
  if (isOpen) {
    closeFilterPanel(partWrap);
    return;
  }
  closeAllFilterPanels();
  refreshBlockFilterCols(partWrap).then(() => {
    const hint = partWrap.querySelector('.filter-col-hint');
    const hasFile = !!partWrap._sourceState?.file;
    const hasCols = (partWrap._filterCols || []).length > 0;
    if (hint) {
      hint.classList.toggle('hidden', hasFile && hasCols);
      hint.textContent = !hasFile ? '请先选择上方来源文件，再配置筛选列头。' : '该来源文件暂无可选列头。';
    }
    renderFilterPanel(partWrap);
    panel.classList.remove('hidden');
    partWrap.querySelector('.btn-open-filter')?.classList.add('is-active');
    openFilterPartWrap = partWrap;
  }).catch(() => {
    renderFilterPanel(partWrap);
    panel.classList.remove('hidden');
    partWrap.querySelector('.btn-open-filter')?.classList.add('is-active');
    openFilterPartWrap = partWrap;
  });
}

function partTemplate(part, idx) {
  const dedupCol = (part.dedup_keys || [])[0] || '';
  const useDedup = partUsesDedup(part);
  const filterCount = (part.row_filters || []).length;
  const joinKeys = (part.join_keys && part.join_keys.length) ? part.join_keys : [...DEFAULT_JOIN_KEYS];

  const wrap = document.createElement('div');
  wrap.className = 'part-row mapping-part-block border border-slate-200 rounded-xl p-3 bg-slate-50/50';
  wrap.dataset.idx = idx;
  wrap.dataset.combineOp = part.combine_op || 'add';
  wrap._dateMeta = partDateMeta(part);
  wrap.innerHTML = `
    ${idx > 0 ? groupConnectorHtml(part.combine_op || 'add') : ''}
    <div class="flex items-baseline gap-2 mb-2">
      <span class="text-[11px] font-semibold text-slate-600">来源组 <span class="group-title-num">${idx + 1}</span></span>
      <span class="text-[10px] text-emerald-600/90">① 组内多列按 ＋/− 先合并（同文件各行可选不同 Sheet）</span>
      <button type="button" class="btn-open-filter ml-auto text-[11px] text-link shrink-0">${filterCount > 0 ? `筛选(${filterCount})` : '筛选'}</button>
    </div>
    <div class="group-file-row flex items-center gap-2 mb-2 px-0.5">
      <label class="text-[10px] text-slate-500 shrink-0 w-20">来源文件</label>
      <div class="g-block-file flex-1 min-w-0"></div>
    </div>
    <input type="hidden" class="p-agg-stored" value="${part.aggregation || 'sum'}">
    <div class="sources-list space-y-0"></div>
    <button type="button" class="btn-add-src mt-1 mb-2 text-[11px] text-link">+ 添加列（组内 ＋/−，可选不同 Sheet）</button>
    <div class="filter-panel hidden">
      <div class="filter-panel-head">
        <span class="filter-panel-title">行筛选条件</span>
        <button type="button" class="btn-close-filter">收起</button>
      </div>
      <p class="filter-panel-desc">全部条件同时满足（AND）才计入本来源组。</p>
      <p class="filter-col-hint hidden"></p>
      <div class="filter-list"></div>
      <div class="filter-panel-foot">
        <button type="button" class="btn-add-filter text-[11px] text-link">+ 添加条件</button>
        <button type="button" class="btn-apply-filter text-[11px] btn-primary px-2.5 py-1">确定</button>
      </div>
    </div>
    <div class="mb-2 dedup-section">
      <label class="inline-flex items-center gap-1.5 text-[11px] text-slate-600 cursor-pointer select-none">
        <input type="checkbox" class="p-enable-dedup" ${useDedup ? 'checked' : ''}>
        <span>去重（按 ID 列去重后求和）</span>
      </label>
      <div class="dedup-fields mt-1.5 ${useDedup ? '' : 'hidden'}">
        <div class="flex items-center gap-2 dedup-line">
          <div class="flex-[1.2] min-w-0">
            <span class="text-[10px] text-slate-400">去重键列头（与上行同表）</span>
            <div class="p-dedup-col-combo"></div>
          </div>
        </div>
      </div>
    </div>
    <details class="mt-1" ${hasAdvanced(part) ? 'open' : ''}>
      <summary class="text-[11px] text-link cursor-pointer select-none">高级规则（样品·刷单·当日退单 / 跨表关联）</summary>
      <div class="mt-2 space-y-2 border-t border-slate-200 pt-2">
        <div class="flex flex-wrap gap-4 text-[11px] text-slate-600">
          <label class="inline-flex items-center gap-1"><input type="checkbox" class="p-exsample" ${part.exclude_sample ? 'checked' : ''}> 排除样品单</label>
          <label class="inline-flex items-center gap-1"><input type="checkbox" class="p-exreview" ${part.exclude_review ? 'checked' : ''}> 排除刷单单</label>
          <label class="inline-flex items-center gap-1" title="当日下单且当日退款的订单不计入本组取数">
            <input type="checkbox" class="p-exsame-day-refund" ${part.exclude_same_day_refund ? 'checked' : ''}> 排除当日退单
          </label>
          <label class="inline-flex items-center gap-1"><input type="checkbox" class="p-join" ${part.join_to_orders ? 'checked' : ''}> 关联数据主表有效行</label>
        </div>
        <div class="join-keys-section ${part.join_to_orders ? '' : 'hidden'}">
          <div class="flex items-center justify-between mb-1">
            <span class="text-[10px] text-slate-500">关联匹配键（列头，须与主表对应）</span>
            <button type="button" class="btn-add-join-key text-[11px] text-link">+ 匹配键</button>
          </div>
          <div class="join-keys-list space-y-1"></div>
        </div>
      </div>
    </details>
    <div class="mt-2 flex justify-end">
      <button type="button" class="btn-rm-block text-[11px] text-red-500 hover:underline">删除本组</button>
    </div>`;

  const sources = partToSources(part);
  wrap._rowFilters = [...(part.row_filters || [])];
  wrap._filterCols = [];

  const list = wrap.querySelector('.sources-list');
  sources.forEach((src, si) => list.appendChild(buildSourceLine(wrap, src, si)));
  bootstrapBlockSource(wrap, sources, { blockIdx: idx });

  const bOp = wrap.querySelector('.b-op');
  if (bOp) {
    bOp.onchange = () => { wrap.dataset.combineOp = bOp.value; };
  }

  wrap.querySelector('.btn-open-filter').onclick = () => toggleFilterPanel(wrap);
  wrap.querySelector('.btn-close-filter').onclick = () => closeFilterPanel(wrap);
  wrap.querySelector('.btn-add-filter').onclick = () => addFilterRow(wrap);
  wrap.querySelector('.btn-apply-filter').onclick = () => applyFilterPanel(wrap);

  wrap.querySelector('.btn-add-src').onclick = () => {
    const st = wrap._sourceState || {};
    const firstRow = wrap.querySelector('.source-line');
    const defaultSheet = firstRow?._sheetSelect?.val() || st.sheets?.[0] || '';
    const row = buildSourceLine(wrap, { sheet_name: defaultSheet, column_header: '' }, list.querySelectorAll('.source-line').length);
    list.appendChild(row);
    wireSourceLine(wrap, row, { sheet_name: defaultSheet, column_header: '' });
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
    joinList.innerHTML = '';
    wrap._joinKeyCombos = [];
    keys.forEach((keyVal, ki) => {
      const line = document.createElement('div');
      line.className = 'flex gap-1 items-center';
      line.innerHTML = `<div class="jk-col flex-1"></div><button type="button" class="jk-rm text-red-400 text-xs px-1">×</button>`;
      const combo = new SearchCombo(line.querySelector('.jk-col'), wrap._filterCols || [], {
        value: keyVal, placeholder: '匹配键列头',
      });
      line.querySelector('.jk-rm').onclick = () => {
        keys.splice(ki, 1);
        renderJoinKeys(keys);
      };
      wrap._joinKeyCombos.push(combo);
      joinList.appendChild(line);
    });
  }
  renderJoinKeys([...joinKeys]);
  joinCb.addEventListener('change', () => joinSection.classList.toggle('hidden', !joinCb.checked));
  wrap.querySelector('.btn-add-join-key').onclick = () => {
    const keys = wrap._joinKeyCombos.map((c) => c.val()).filter(Boolean);
    keys.push('');
    renderJoinKeys(keys);
  };

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

  if (idx > 0) wireBenchmarkCombo(wrap, part).catch(() => {});

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
      ? wrap._joinKeyCombos.map((c) => c.val()).filter(Boolean)
      : [];
    return {
      label: null,
      source_file_keyword: first.source_file_keyword || null,
      sheet_name: first.sheet_name || '',
      column_header: first.column_header || '',
      sources,
      aliases: [],
      combine_op: blockIdx === 0 ? 'add' : (wrap.querySelector('.b-op')?.value || wrap.dataset.combineOp || 'add'),
      aggregation: enableDedup ? inferAggregation(stored, dedup_keys) : 'sum',
      dedup_keys,
      date_filter_column: wrap._dateMeta?.date_filter_column || null,
      date_format: wrap._dateMeta?.date_format || null,
      exclude_sample: wrap.querySelector('.p-exsample').checked,
      exclude_review: wrap.querySelector('.p-exreview').checked,
      exclude_same_day_refund: wrap.querySelector('.p-exsame-day-refund')?.checked || false,
      join_to_orders: joinOn,
      join_keys: join_keys.length ? join_keys : (joinOn ? [...DEFAULT_JOIN_KEYS] : []),
      benchmark_keys: readBenchmarkKeys(wrap),
      row_filters: (wrap._rowFilters || []).filter((f) => f.column),
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

async function openModal(mode, mappingId = null) {
  const session = ++modalSession;
  currentMappingId = mappingId;
  const modal = document.getElementById('mappingModal');
  document.getElementById('newMappingFields').classList.toggle('hidden', mode !== 'create');
  document.getElementById('btnDeleteMapping').classList.toggle('hidden', mode !== 'edit');

  // 先弹出壳子，数据异步加载，避免长时间无反馈
  openWithTransition(modal);
  const partsContainer = document.getElementById('partsContainer');
  if (partsContainer) {
    partsContainer.innerHTML = '<p class="text-sm text-slate-500 py-8 text-center">加载配置中…</p>';
  }

  try {
    if (mode === 'create') {
      const dsSelect = document.getElementById('newDataSource');
      if (dsSelect && window.CURRENT_STORE_DS_ID) {
        dsSelect.value = String(window.CURRENT_STORE_DS_ID);
      }
      currentDataSourceId = parseInt(dsSelect?.value || '0', 10);
      currentLogicalFieldCode = '';
      document.getElementById('modalTitle').textContent = '新增取数行';
      document.getElementById('modalSubtitle').textContent = '配置多条取数规则，支持跨文件加减组合';
      document.getElementById('mappingLabel').value = '';
      document.getElementById('mappingGroup').value = '';
      document.getElementById('mappingSort').value = '0';
      document.getElementById('mappingDesc').value = '';
      parts = [{ type: 'source', combine_op: 'add', aggregation: 'sum', dedup_keys: [], aliases: [] }];
      await ensureFiles(currentDataSourceId);
      await refreshReuseFields();
    } else {
      const res = await fetch(`/api/mappings/${mappingId}`);
      if (!res.ok) throw new Error('加载映射失败');
      const data = await res.json();
      if (session !== modalSession) return;
      currentDataSourceId = data.data_source_id;
      currentLogicalFieldCode = data.logical_field_code || '';
      document.getElementById('modalTitle').textContent = data.label || data.logical_field_name || '配置取数行';
      document.getElementById('modalSubtitle').textContent = `{field:${data.line_code || data.logical_field_code}}`;
      document.getElementById('mappingLabel').value = data.label || data.logical_field_name || '';
      document.getElementById('mappingGroup').value = data.report_group || '';
      document.getElementById('mappingSort').value = String(data.sort_order || 0);
      document.getElementById('mappingDesc').value = data.description || '';
      parts = flatPartsToBlocks(data.parts.length ? data.parts : [{ combine_op: 'add', aggregation: 'sum', dedup_keys: [] }]);
      await ensureFiles(currentDataSourceId);
      await refreshReuseFields();
    }
    if (session !== modalSession) return;
    renderParts();
  } catch (err) {
    if (session !== modalSession) return;
    toast(err.message || '打开配置失败', false);
    closeModal();
  }
}

function openWithTransition(modal) {
  const panel = document.getElementById('mappingPanel');
  modal.classList.remove('hidden');
  requestAnimationFrame(() => {
    modal.classList.remove('opacity-0');
    if (panel) panel.classList.remove('scale-95');
  });
}

function closeModal() {
  modalSession += 1;
  closeAllFilterPanels();
  const modal = document.getElementById('mappingModal');
  const panel = document.getElementById('mappingPanel');
  modal.classList.add('opacity-0');
  if (panel) panel.classList.add('scale-95');
  setTimeout(() => modal.classList.add('hidden'), 200);
}

function collectParts() {
  return [...document.querySelectorAll('.mapping-part-block')].map((el) => el._getData());
}

async function saveMapping() {
  const body = {
    label: document.getElementById('mappingLabel')?.value.trim() || null,
    report_group: document.getElementById('mappingGroup')?.value.trim() || null,
    sort_order: parseInt(document.getElementById('mappingSort')?.value, 10) || 0,
    line_type: 'fetch',
    description: document.getElementById('mappingDesc').value.trim() || null,
    parts: collectParts(),
  };
  if (!body.parts.length || body.parts.some((p) => {
    if (p.ref_field_code) return !p.ref_field_code;
    const srcs = p.sources?.length ? p.sources : [{ sheet_name: p.sheet_name, column_header: p.column_header }];
    return srcs.some((s) => !s.sheet_name || !s.column_header);
  })) {
    toast('请完整配置取数规则，或选择要复用的字段', false);
    return;
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
  closeModal();
  toast('保存成功');
  setTimeout(() => location.reload(), 600);
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-close]').forEach((el) => el.addEventListener('click', closeModal));
  document.getElementById('btnNewMapping')?.addEventListener('click', () => {
    openModal('create').catch(() => {});
  });
  document.body.addEventListener('click', (e) => {
    const btn = e.target.closest('.btn-edit');
    if (!btn || btn.closest('#formulaModal')) return;
    openModal('edit', parseInt(btn.dataset.id, 10)).catch(() => {});
  });
  document.getElementById('btnAddPart')?.addEventListener('click', addPartRow);
  document.getElementById('btnAddFieldRef')?.addEventListener('click', () => {
    addFieldRefRow().catch(() => {});
  });
  document.getElementById('btnSaveMapping')?.addEventListener('click', saveMapping);
  document.getElementById('btnDeleteMapping')?.addEventListener('click', async () => {
    if (!confirm('确定删除？')) return;
    const res = await fetch(`/api/mappings/${currentMappingId}`, { method: 'DELETE' });
    if (res.ok) { toast('已删除'); closeModal(); setTimeout(() => location.reload(), 600); }
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
