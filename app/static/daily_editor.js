(function () {
  const root = document.getElementById('dailyEditor');
  if (!root) return;

  const runId = root.dataset.runId || null;
  const tbody = document.getElementById('dailyFieldBody');
  let saveTimer = null;
  let activeRow = null;
  let dragSrc = null;

  function resolveDsId() {
    const fromRoot = root.dataset.dsId;
    if (fromRoot) return fromRoot;
    const fromSelect = document.querySelector('select[name="data_source_id"]')?.value;
    if (fromSelect) return fromSelect;
    return null;
  }

  function requireDsId() {
    const id = resolveDsId();
    if (!id) {
      toast('未识别店铺数据源，请重新生成日报后再试', false);
      return null;
    }
    return id;
  }

  function toast(msg, ok = true) {
    const toastEl = document.getElementById('dailyToast');
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.className = `fixed bottom-6 right-6 z-50 px-4 py-3 rounded-lg shadow-lg text-sm text-white transition-all duration-300 ${ok ? 'bg-emerald-600' : 'bg-red-600'}`;
    toastEl.classList.remove('hidden', 'opacity-0', 'translate-y-2');
    clearTimeout(toast._t);
    toast._t = setTimeout(() => {
      toastEl.classList.add('opacity-0', 'translate-y-2');
      setTimeout(() => toastEl.classList.add('hidden'), 280);
    }, 2200);
  }

  function setStatus(text, tone = 'muted') {
    const statusEl = document.getElementById('saveStatus');
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.className = `text-xs transition-opacity ${tone === 'ok' ? 'text-emerald-600' : tone === 'busy' ? 'text-sky-600' : 'text-slate-400'}`;
  }

  function colLetter(index) {
    let n = 6 + index; // F = 6
    let s = '';
    while (n > 0) {
      const rem = (n - 1) % 26;
      s = String.fromCharCode(65 + rem) + s;
      n = Math.floor((n - 1) / 26);
    }
    return s;
  }

  function refreshColLetters() {
    tbody.querySelectorAll('.daily-row').forEach((row, i) => {
      const el = row.querySelector('.col-letter');
      if (el) el.textContent = colLetter(i);
    });
  }

  async function saveOrder() {
    const dsId = requireDsId();
    if (!dsId) return;
    const ids = [...tbody.querySelectorAll('.daily-row')].map((r) => parseInt(r.dataset.mappingId, 10));
    const res = await fetch(`/api/data-sources/${dsId}/report-fields/order`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mapping_ids: ids }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '排序保存失败');
    refreshColLetters();
    toast('顺序已保存');
  }

  function initDragDrop() {
    tbody.querySelectorAll('.daily-row').forEach((row) => {
      row.addEventListener('dragstart', (e) => {
        dragSrc = row;
        row.classList.add('opacity-50', 'daily-row--dragging');
        e.dataTransfer.effectAllowed = 'move';
      });
      row.addEventListener('dragend', () => {
        row.classList.remove('opacity-50', 'daily-row--dragging');
        dragSrc = null;
      });
      row.addEventListener('dragover', (e) => {
        e.preventDefault();
        if (!dragSrc || dragSrc === row) return;
        const rect = row.getBoundingClientRect();
        const after = e.clientY > rect.top + rect.height / 2;
        tbody.insertBefore(dragSrc, after ? row.nextSibling : row);
      });
      row.addEventListener('drop', (e) => {
        e.preventDefault();
        if (!dragSrc) return;
        saveOrder().catch((err) => toast(err.message, false));
      });
    });
  }

  async function saveLabel(row, label) {
    const mappingId = row.dataset.mappingId;
    const res = await fetch(`/api/mappings/${mappingId}/label`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label, run_id: runId ? parseInt(runId, 10) : null }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '改名失败');
    row.querySelector('.field-label').value = data.label;
    toast('名称已保存');
  }

  document.getElementById('btnAddField')?.addEventListener('click', async () => {
    const dsId = requireDsId();
    if (!dsId) return;
    const name = prompt('新字段名称', '新指标');
    if (!name?.trim()) return;
    setStatus('添加中…', 'busy');
    try {
      const res = await fetch(`/api/data-sources/${dsId}/report-fields`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          label: name.trim(),
          run_id: runId ? parseInt(runId, 10) : null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || '添加失败');
      toast('字段已添加，请配置取数规则');
      sessionStorage.setItem('openMappingId', String(data.id));
      location.reload();
    } catch (err) {
      toast(err.message, false);
    } finally {
      setStatus('已同步', 'ok');
    }
  });

  tbody.querySelectorAll('.field-label').forEach((input) => {
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') input.blur();
    });
    input.addEventListener('blur', () => {
      const row = input.closest('.daily-row');
      const prev = input.dataset.lastLabel || input.defaultValue;
      const val = input.value.trim();
      if (!val) {
        input.value = prev;
        return;
      }
      if (val === prev) return;
      saveLabel(row, val).catch((err) => {
        input.value = prev;
        toast(err.message, false);
      });
      input.dataset.lastLabel = val;
    });
    input.dataset.lastLabel = input.value;
  });

  function parseNumber(raw) {
    const s = String(raw ?? '').trim().replace(/[$,¥,\s]/g, '');
    if (!s) return null;
    const n = Number(s);
    return Number.isFinite(n) ? n : NaN;
  }

  function updateRowUI(row, data) {
    const displayBtn = row.querySelector('.value-display');
    const statusTag = row.querySelector('.status-tag');
    const isManual = row.dataset.manual === '1';
    if (displayBtn) {
      displayBtn.textContent = data.display_value || (isManual ? '点击填写' : '—');
    }
    row.classList.toggle('daily-row--overridden', !!data.is_overridden);
    if (statusTag && isManual) {
      statusTag.textContent = data.display_value ? '已填写' : '待填写';
    } else if (statusTag && data.is_overridden) {
      statusTag.textContent = '已调整';
    }
  }

  async function saveValue(row, payload) {
    const valueId = row.dataset.valueId;
    if (!valueId) return;
    setStatus('保存中…', 'busy');
    const res = await fetch(`/api/report-runs/${runId}/values/${valueId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '保存失败');
    updateRowUI(row, data);
    setStatus('已同步', 'ok');
  }

  if (runId) {
    tbody.querySelectorAll('.daily-row').forEach((row) => {
      const displayBtn = row.querySelector('.value-display');
      const input = row.querySelector('.value-input');
      if (!displayBtn || !input) return;

      displayBtn.addEventListener('click', () => {
        if (activeRow && activeRow !== row) {
          activeRow.querySelector('.value-input')?.classList.add('hidden');
          activeRow.querySelector('.value-display')?.classList.remove('hidden');
        }
        displayBtn.classList.add('hidden');
        input.classList.remove('hidden');
        input.focus();
        input.select();
        activeRow = row;
      });

      input.addEventListener('blur', () => {
        if (activeRow !== row) return;
        input.classList.add('hidden');
        displayBtn.classList.remove('hidden');
        activeRow = null;
        const num = parseNumber(input.value);
        if (Number.isNaN(num)) return;
        clearTimeout(saveTimer);
        saveTimer = setTimeout(() => {
          saveValue(row, num === null ? { raw_value: null } : { raw_value: num }).catch((e) => toast(e.message, false));
        }, 120);
      });

      row.querySelector('.computed-cell')?.addEventListener('dblclick', () => {
        saveValue(row, { clear_override: true }).catch((e) => toast(e.message, false));
      });
    });
  }

  initDragDrop();
  refreshColLetters();
})();
