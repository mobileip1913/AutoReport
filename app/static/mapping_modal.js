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
  { v: 'nonempty', l: '非空' },
];

let currentMappingId = null;
let currentDataSourceId = null;
let currentLogicalFieldCode = '';
let parts = [];
let globalDatePickers = null;
let globalDateFormatStored = '';
let modalSession = 0;

function toast(msg, ok = true) {
  const el = document.getElementById('toast');
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
    this.container.innerHTML = '';
    this.container.className = 'relative';
    this.select = document.createElement('select');
    this.select.className = 'w-full border rounded px-2 py-1.5 text-xs font-mono focus:ring-2 focus:ring-indigo-200 outline-none bg-white';
    this.setOpts(options, placeholder);
    this.set(value);
    this.select.addEventListener('change', () => {
      if (this.onChange) this.onChange(this.val());
    });
    this.container.appendChild(this.select);
  }
  setOpts(options, placeholder) {
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
  val() { return this.select.value; }
  set(v) { this.select.value = v || ''; }
  setDisabled(dis) {
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
    this.container.innerHTML = '';
    this.container.className = 'relative';
    this.input = document.createElement('input');
    this.input.type = 'text';
    this.input.value = value;
    this.input.placeholder = placeholder;
    this.input.className = 'w-full border rounded px-2 py-1.5 text-xs font-mono focus:ring-2 focus:ring-indigo-200 outline-none';
    this.input.autocomplete = 'off';
    this.dropdown = document.createElement('div');
    this.dropdown.className = 'absolute z-50 left-0 right-0 mt-1 max-h-36 overflow-y-auto bg-white border rounded shadow-lg hidden';
    this.container.append(this.input, this.dropdown);
    this.input.addEventListener('focus', () => this.show(this.input.value));
    this.input.addEventListener('input', () => this.show(this.input.value));
    this.input.addEventListener('blur', () => setTimeout(() => this.dropdown.classList.add('hidden'), 150));
  }
  show(q) {
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
        btn.className = 'block w-full text-left px-2 py-1.5 text-xs hover:bg-indigo-50 font-mono';
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
  val() { return this.input.value.trim(); }
  set(val) { this.input.value = val || ''; }
  setOpts(opts) {
    this.options = opts || [];
    if (this.input === document.activeElement) this.show(this.input.value);
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

function refreshFilterCols(blockEl) {
  const cols = new Set();
  blockEl.querySelectorAll('.source-line').forEach((row) => {
    (row._colCombo?.options || []).forEach((c) => cols.add(c));
  });
  blockEl._filterCols = [...cols];
  if (blockEl._dedupColCombo) blockEl._dedupColCombo.setOpts(blockEl._filterCols);
  (blockEl._filterRows || []).forEach((e) => e.colC?.setOpts(blockEl._filterCols));
}

async function loadRowColumns(blockEl, row, sheet, keepCol) {
  const st = blockEl._sourceState;
  if (!st?.file || !sheet) {
    row._colCombo?.setOpts([]);
    if (keepCol === undefined) row._colCombo?.set('');
    refreshFilterCols(blockEl);
    return;
  }
  const cols = await fetchColumns(currentDataSourceId, st.file, sheet);
  row._colCombo.setOpts(cols);
  if (keepCol !== undefined) {
    row._colCombo.set(keepCol && cols.includes(keepCol) ? keepCol : '');
  }
  refreshFilterCols(blockEl);
}

function wireSourceLine(blockEl, row, { sheet_name: sheetName = '', column_header: col = '' } = {}) {
  const st = blockEl._sourceState;
  const sheetSelect = new SelectField(row.querySelector('.s-sheet-combo'), {
    placeholder: st.file ? '请选择 Sheet' : '请先选本组文件',
    options: st.sheets || [],
    value: sheetName,
    onChange: (sheet) => loadRowColumns(blockEl, row, sheet),
  });
  sheetSelect.setDisabled(!st.file || !st.sheets?.length);

  const colCombo = new SearchCombo(row.querySelector('.s-col-combo'), [], {
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
    if (!sheets.length) toast(`「${resolved}」未找到 Sheet`, false);
    else if (blockIdx === 0 && globalDatePickers?.fileSelect) {
      const df = globalDatePickers.fileSelect.val();
      if (df === st.file) {
        const firstRow = blockEl.querySelector('.source-line');
        const sh = firstRow?._sheetSelect?.val();
        if (sh) {
          globalDatePickers.sheetSelect.set(sh);
          globalDatePickers.setCols(firstRow._colCombo?.options || []);
        }
      }
    }
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

/** 独立三级联动（全局日期过滤等） */
function bindSourceCombos(wrap, selectors, values, { onSheetPick = null, onFilePick = null } = {}) {
  const dsId = currentDataSourceId;
  const st = { file: '', sheet: '', cols: [], files: [] };

  const colCombo = new SearchCombo(wrap.querySelector(selectors.col), [], {
    value: values.col || '',
    placeholder: '搜索列头',
    emptyHint: '请先选择 Sheet',
  });

  const sheetSelect = new SelectField(wrap.querySelector(selectors.sheet), {
    placeholder: '请先选文件',
    options: [],
    value: values.sheet || '',
    onChange: (sheet) => cascadeSheet(sheet),
  });
  sheetSelect.setDisabled(true);

  const fileSelect = new SelectField(wrap.querySelector(selectors.file), {
    placeholder: '请选择来源文件',
    options: [],
    value: values.file || '',
    onChange: (file) => cascadeFile(file),
  });

  async function cascadeFile(file, keepSheet, keepCol) {
    const resolved = resolveFileKey(file, st.files);
    fileSelect.set(resolved);
    st.file = resolved;
    if (!resolved) {
      sheetSelect.setOpts([], '请先选文件');
      sheetSelect.setDisabled(true);
      colCombo.setOpts([]);
      colCombo.set('');
      return;
    }
    sheetSelect.setOpts([], '加载 Sheet…');
    sheetSelect.setDisabled(true);
    const sheets = await fetchSheets(dsId, resolved);
    sheetSelect.setOpts(sheets, sheets.length ? '请选择 Sheet' : '该文件无 Sheet');
    sheetSelect.setDisabled(!sheets.length);
    const sheet = (keepSheet && sheets.includes(keepSheet)) ? keepSheet : (sheets[0] || '');
    sheetSelect.set(sheet);
    await cascadeSheet(sheet, keepCol);
    if (onFilePick) onFilePick(resolved, sheets);
    if (!sheets.length) toast(`「${resolved}」未找到 Sheet`, false);
  }

  async function cascadeSheet(sheet, keepCol) {
    st.sheet = sheet || '';
    if (!st.file || !sheet) {
      colCombo.setOpts([]);
      if (keepCol === undefined) colCombo.set('');
      return;
    }
    const cols = await fetchColumns(dsId, st.file, sheet);
    st.cols = cols;
    colCombo.setOpts(cols);
    if (keepCol !== undefined) colCombo.set(keepCol && cols.includes(keepCol) ? keepCol : '');
    if (onSheetPick) onSheetPick(sheet, cols);
  }

  (async () => {
    st.files = await ensureFiles(dsId);
    fileSelect.setOpts(fileSelectOptions(st.files), '请选择来源文件');
    const initFile = resolveFileKey(values.file || '', st.files);
    if (initFile) await cascadeFile(initFile, values.sheet, values.col);
  })();

  return {
    fileSelect,
    sheetSelect,
    fileCombo: fileSelect,
    sheetCombo: sheetSelect,
    colCombo,
    setCols: (cols) => { st.cols = cols; colCombo.setOpts(cols); },
    loadColumns: async (file, sheet, col) => cascadeFile(file, sheet, col),
  };
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

function inferGlobalDateFormat(partsArray) {
  for (const p of partsArray || []) {
    if (p.date_format) return p.date_format;
  }
  return '';
}

function inferGlobalDateConfig(partsArray) {
  for (const p of partsArray || []) {
    if (p.date_filter_column) {
      return {
        file: p.source_file_keyword || '',
        sheet: p.sheet_name || '',
        col: p.date_filter_column,
      };
    }
  }
  const p0 = partsArray?.[0];
  return {
    file: p0?.source_file_keyword || '',
    sheet: p0?.sheet_name || '',
    col: '',
  };
}

function setupGlobalDatePickers() {
  const wrap = document.getElementById('mappingDateSection');
  if (!wrap) return;
  let values;
  if (globalDatePickers) {
    values = {
      file: globalDatePickers.fileCombo.val(),
      sheet: globalDatePickers.sheetCombo.val(),
      col: globalDatePickers.colCombo.val(),
    };
  } else {
    values = inferGlobalDateConfig(parts);
    globalDateFormatStored = inferGlobalDateFormat(parts);
  }
  globalDatePickers = bindSourceCombos(wrap, {
    file: '.g-date-file-combo', sheet: '.g-date-sheet-combo', col: '.g-date-col-combo',
  }, values);
}

function getGlobalDateFilterColumn() {
  return globalDatePickers?.colCombo.val() || null;
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
  wrap.className = 'field-ref-part mapping-part-block border border-violet-200 rounded-xl p-3 bg-violet-50/40';
  wrap.dataset.idx = idx;
  wrap.dataset.partType = 'field_ref';
  wrap.dataset.combineOp = part.combine_op || 'add';
  wrap.innerHTML = `
    ${idx > 0 ? groupConnectorHtml(part.combine_op || 'add') : ''}
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[11px] font-semibold text-violet-700 shrink-0">复用字段</span>
      <div class="ref-field-select flex-1 min-w-[12rem]"></div>
      <code class="ref-field-code text-[10px] text-slate-500 font-mono shrink-0"></code>
      <button type="button" class="btn-rm-block text-[11px] text-red-500 hover:underline shrink-0 ml-auto">删除</button>
    </div>`;

  const fieldSelect = new SelectField(wrap.querySelector('.ref-field-select'), {
    placeholder: options.length ? '选择已配置的字段' : '暂无其他已配字段',
    options: options.map((f) => ({
      value: f.code,
      label: `${f.name}（{field:${f.code}}）`,
    })),
    value: part.ref_field_code || '',
    onChange: (code) => {
      wrap.querySelector('.ref-field-code').textContent = code ? `{field:${code}}` : '';
    },
  });
  if (part.ref_field_code) {
    wrap.querySelector('.ref-field-code').textContent = `{field:${part.ref_field_code}}`;
  }

  const bOp = wrap.querySelector('.b-op');
  if (bOp) bOp.onchange = () => { wrap.dataset.combineOp = bOp.value; };

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
      combine_op: blockIdx === 0 ? 'add' : (wrap.querySelector('.b-op')?.value || wrap.dataset.combineOp || 'add'),
      aggregation: 'sum',
      dedup_keys: [],
      date_filter_column: null,
      date_format: null,
      exclude_sample: false,
      exclude_review: false,
      join_to_orders: false,
      row_filters: [],
    };
  };

  return wrap;
}

function renderPartBlock(part, idx) {
  if (part.type === 'field_ref') return fieldRefPartTemplate(part, idx);
  return partTemplate(part, idx);
}

function groupConnectorHtml(combineOp = 'add') {
  const isSub = combineOp === 'subtract';
  return `
    <div class="group-connector flex items-center gap-2 mb-2 pb-2 border-b border-dashed border-amber-200/80">
      <div class="flex-1 border-t border-dashed border-amber-200"></div>
      <span class="text-[10px] text-amber-700/80 whitespace-nowrap">组间</span>
      <select class="b-op shrink-0 w-12 border-2 border-amber-300 bg-amber-50 rounded px-1 py-1.5 text-sm font-bold text-amber-800 text-center cursor-pointer" title="与上一项之间的运算">
        <option value="add" ${!isSub ? 'selected' : ''}>＋</option>
        <option value="subtract" ${isSub ? 'selected' : ''}>−</option>
      </select>
      <span class="text-[10px] text-slate-400 whitespace-nowrap">上一项 ⊕ 本项</span>
      <div class="flex-1 border-t border-dashed border-amber-200"></div>
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
    refreshFilterCols(blockEl);
    reindexSourcesInBlock(blockEl);
  };
  return row;
}

function reindexSourcesInBlock(blockEl) {
  blockEl.querySelectorAll('.source-line').forEach((line, srcIdx) => {
    const opWrap = line.querySelector('.s-op-wrap');
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

function partTemplate(part, idx) {
  const dedupCol = (part.dedup_keys || [])[0] || '';
  const useDedup = partUsesDedup(part);

  const wrap = document.createElement('div');
  wrap.className = 'part-row mapping-part-block border border-slate-200 rounded-xl p-3 bg-slate-50/50';
  wrap.dataset.idx = idx;
  wrap.dataset.combineOp = part.combine_op || 'add';
  wrap.innerHTML = `
    ${idx > 0 ? groupConnectorHtml(part.combine_op || 'add') : ''}
    <div class="flex items-baseline gap-2 mb-2">
      <span class="text-[11px] font-semibold text-slate-600">来源组 <span class="group-title-num">${idx + 1}</span></span>
      <span class="text-[10px] text-emerald-600/90">① 组内多列按 ＋/− 先合并（同文件各行可选不同 Sheet）</span>
    </div>
    <div class="group-file-row flex items-center gap-2 mb-2 px-0.5">
      <label class="text-[10px] text-slate-500 shrink-0 w-20">来源文件</label>
      <div class="g-block-file flex-1 min-w-0"></div>
    </div>
    <input type="hidden" class="p-agg-stored" value="${part.aggregation || 'sum'}">
    <div class="sources-list space-y-0"></div>
    <button type="button" class="btn-add-src mt-1 mb-2 text-[11px] text-indigo-600 hover:underline">+ 添加列（组内 ＋/−，可选不同 Sheet）</button>
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
      <summary class="text-[11px] text-indigo-600 cursor-pointer select-none">高级规则（样品·刷单排除 / 行条件）</summary>
      <div class="mt-2 space-y-2 border-t border-slate-200 pt-2">
        <div class="flex flex-wrap gap-4 text-[11px] text-slate-600">
          <label class="inline-flex items-center gap-1"><input type="checkbox" class="p-exsample" ${part.exclude_sample ? 'checked' : ''}> 排除样品单</label>
          <label class="inline-flex items-center gap-1"><input type="checkbox" class="p-exreview" ${part.exclude_review ? 'checked' : ''}> 排除刷单单</label>
          <label class="inline-flex items-center gap-1"><input type="checkbox" class="p-join" ${part.join_to_orders ? 'checked' : ''}> 关联当日有效订单</label>
        </div>
        <div>
          <div class="flex items-center justify-between mb-1">
            <span class="text-[10px] text-slate-500">行过滤条件（全部满足才计入）</span>
            <button type="button" class="p-add-filter text-[11px] text-indigo-600 hover:underline">+ 条件</button>
          </div>
          <div class="p-filters space-y-1"></div>
        </div>
      </div>
    </details>
    <div class="mt-2 flex justify-end">
      <button type="button" class="btn-rm-block text-[11px] text-red-500 hover:underline">删除本组</button>
    </div>`;

  const sources = partToSources(part);
  const filtersBox = wrap.querySelector('.p-filters');
  const filterRows = [];
  wrap._filterRows = filterRows;
  wrap._filterCols = [];

  const list = wrap.querySelector('.sources-list');
  sources.forEach((src, si) => list.appendChild(buildSourceLine(wrap, src, si)));
  bootstrapBlockSource(wrap, sources, { blockIdx: idx });

  const bOp = wrap.querySelector('.b-op');
  if (bOp) {
    bOp.onchange = () => { wrap.dataset.combineOp = bOp.value; };
  }

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

  function addFilterRow(f = {}) {
    const row = document.createElement('div');
    row.className = 'flex gap-1 items-center';
    row.innerHTML = `
      <div class="flt-col flex-1"></div>
      <select class="flt-op border rounded px-1 py-1 text-[11px]">
        ${FILTER_OPS.map((o) => `<option value="${o.v}" ${(f.op || 'eq') === o.v ? 'selected' : ''}>${o.l}</option>`).join('')}
      </select>
      <input class="flt-val flex-1 border rounded px-2 py-1 text-[11px]" placeholder="值，多个用逗号" value="${(f.values || []).join(', ')}">
      <button type="button" class="flt-rm text-red-400 text-xs px-1">×</button>`;
    const colC = new SearchCombo(row.querySelector('.flt-col'), wrap._filterCols || [], { value: f.column || '', placeholder: '列头' });
    row.querySelector('.flt-rm').onclick = () => {
      const i = filterRows.indexOf(entry);
      if (i >= 0) filterRows.splice(i, 1);
      row.remove();
    };
    const entry = {
      el: row,
      colC,
      get: () => ({
        column: colC.val(),
        op: row.querySelector('.flt-op').value,
        values: row.querySelector('.flt-val').value.split(',').map((s) => s.trim()).filter(Boolean),
      }),
    };
    filterRows.push(entry);
    filtersBox.appendChild(row);
  }
  (part.row_filters || []).forEach(addFilterRow);
  wrap.querySelector('.p-add-filter').onclick = () => addFilterRow();

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
      date_filter_column: getGlobalDateFilterColumn(),
      date_format: globalDateFormatStored || null,
      exclude_sample: wrap.querySelector('.p-exsample').checked,
      exclude_review: wrap.querySelector('.p-exreview').checked,
      join_to_orders: wrap.querySelector('.p-join').checked,
      row_filters: filterRows.map((e) => e.get()).filter((f) => f.column),
    };
  };

  return wrap;
}

function hasAdvanced(part) {
  return !!(part.exclude_sample || part.exclude_review ||
    part.join_to_orders || (part.row_filters && part.row_filters.length));
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
  const idx = container.querySelectorAll('.mapping-part-block').length;
  const card = partTemplate({ type: 'source', combine_op: 'add', aggregation: 'sum', dedup_keys: [], aliases: [], sources: [] }, idx);
  container.appendChild(card);
  reindexParts();
}

async function addFieldRefRow() {
  await refreshReuseFields();
  const options = getReuseFieldOptions();
  if (!options.length) {
    toast('暂无其他已配置字段可复用（请先保存其他字段的映射）', false);
    return;
  }
  const container = document.getElementById('partsContainer');
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
  c.innerHTML = '';
  if (!parts.length) parts = [{ type: 'source', combine_op: 'add', aggregation: 'sum', dedup_keys: [], aliases: [] }];
  parts.forEach((p, i) => c.appendChild(renderPartBlock(p, i)));
  syncGroupConnectors();
  setupGlobalDatePickers();
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
      currentDataSourceId = parseInt(document.getElementById('newDataSource').value, 10);
      currentLogicalFieldCode = '';
      document.getElementById('modalTitle').textContent = '新增字段映射';
      document.getElementById('modalSubtitle').textContent = '配置多条取数规则，支持跨文件加减组合';
      document.getElementById('mappingDesc').value = '';
      parts = [{ type: 'source', combine_op: 'add', aggregation: 'sum', sheet_name: 'Order Details', dedup_keys: [], aliases: [] }];
      globalDatePickers = null;
      globalDateFormatStored = '';
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
      globalDatePickers = null;
      globalDateFormatStored = inferGlobalDateFormat(parts);
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
  toast('保存成功');
  closeModal();
  setTimeout(() => location.reload(), 600);
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-close]').forEach((el) => el.addEventListener('click', closeModal));
  document.getElementById('btnNewMapping').onclick = () => {
    openModal('create').catch(() => {});
  };
  document.querySelectorAll('.btn-edit').forEach((btn) => {
    btn.onclick = () => {
      openModal('edit', parseInt(btn.dataset.id, 10)).catch(() => {});
    };
  });
  document.getElementById('btnAddPart').onclick = addPartRow;
  document.getElementById('btnAddFieldRef').onclick = () => {
    addFieldRefRow().catch(() => {});
  };
  document.getElementById('btnSaveMapping').onclick = saveMapping;
  document.getElementById('btnDeleteMapping').onclick = async () => {
    if (!confirm('确定删除？')) return;
    const res = await fetch(`/api/mappings/${currentMappingId}`, { method: 'DELETE' });
    if (res.ok) { toast('已删除'); closeModal(); setTimeout(() => location.reload(), 600); }
  };
  document.getElementById('newDataSource')?.addEventListener('change', (e) => {
    currentDataSourceId = parseInt(e.target.value, 10);
    globalDatePickers = null;
    refreshReuseFields()
      .then(() => ensureFiles(currentDataSourceId))
      .then(renderParts);
  });
});
