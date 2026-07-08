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
    window.showAppToast?.(msg, ok);
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
    const statusTag = row.querySelector('.row-status-tag');
    const isManual = row.dataset.manual === '1';
    if (displayBtn && !isManual) {
      displayBtn.textContent = data.display_value || '—';
      displayBtn.classList.toggle('text-amber-900', !!data.is_overridden);
      displayBtn.classList.toggle('text-slate-800', !!data.display_value && !data.is_overridden);
      displayBtn.classList.toggle('text-slate-300', !data.display_value && !data.is_overridden);
    }
    row.classList.toggle('daily-row--overridden', !!data.is_overridden);
    if (statusTag && !isManual) {
      if (data.is_overridden) {
        statusTag.textContent = '已调整';
        statusTag.className = 'field-type-tag field-type-tag--warn row-status-tag';
      } else if (row.dataset.configured === '0') {
        statusTag.textContent = '未配规则';
        statusTag.className = 'field-type-tag field-type-tag--muted row-status-tag';
      } else {
        statusTag.remove();
      }
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
      if (row.dataset.manual === '1') return;
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
      row.querySelector('.computed-cell')?.setAttribute('title', '双击恢复为系统计算值');
    });
  }

  initDragDrop();
  refreshColLetters();
})();
