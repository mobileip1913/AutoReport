/** 报表配置页：日期主表 + 每日自动生成时间 */

function settingsToast(msg, ok = true) {
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = msg;
  el.className = `fixed bottom-6 right-6 z-50 px-4 py-3 rounded-lg shadow-lg text-sm text-white ${ok ? 'bg-emerald-600' : 'bg-red-600'}`;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 2800);
}

async function apiJson(url, opts = {}) {
  const res = await fetch(url, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || data.message || '请求失败');
  return data;
}

function initTimePicker(card) {
  const wrap = card.querySelector('.ds-time-picker');
  const hidden = card.querySelector('.ds-daily-time');
  if (!wrap || !hidden) return null;

  const trigger = wrap.querySelector('.ds-time-trigger');
  const valueEl = wrap.querySelector('.ds-time-value');
  const popover = wrap.querySelector('.ds-time-popover');
  const hourGrid = wrap.querySelector('.ds-time-hour-grid');
  const minGrid = wrap.querySelector('.ds-time-min-grid');
  const clearBtn = wrap.querySelector('.ds-time-clear');
  if (!trigger || !valueEl || !popover || !hourGrid || !minGrid) return null;

  const pad = (n) => String(n).padStart(2, '0');
  let selectedHour = '';
  let selectedMin = '';
  const popoverWidth = 320;

  const positionPopover = () => {
    const rect = trigger.getBoundingClientRect();
    const width = popover.offsetWidth || popoverWidth;
    const height = popover.offsetHeight || 280;
    let left = rect.right - width;
    left = Math.max(8, Math.min(left, window.innerWidth - width - 8));
    let top = rect.bottom + 8;
    if (top + height > window.innerHeight - 8) {
      top = Math.max(8, rect.top - height - 8);
    }
    popover.style.left = `${left}px`;
    popover.style.top = `${top}px`;
  };

  const setOpen = (open) => {
    if (open) {
      popover.classList.remove('hidden');
      document.body.appendChild(popover);
      popover.classList.add('is-floating');
      positionPopover();
    } else {
      popover.classList.add('hidden');
      popover.classList.remove('is-floating');
      popover.style.left = '';
      popover.style.top = '';
      wrap.appendChild(popover);
    }
    wrap.classList.toggle('is-open', open);
    trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
  };

  const renderActive = () => {
    hourGrid.querySelectorAll('.ds-time-option').forEach((btn) => {
      btn.classList.toggle('is-active', btn.dataset.value === selectedHour);
    });
    minGrid.querySelectorAll('.ds-time-option').forEach((btn) => {
      btn.classList.toggle('is-active', btn.dataset.value === selectedMin);
    });
  };

  const syncHidden = () => {
    if (selectedHour !== '' && selectedMin !== '') {
      hidden.value = `${selectedHour}:${selectedMin}`;
      valueEl.textContent = hidden.value;
      trigger.classList.add('has-value');
    } else {
      hidden.value = '';
      valueEl.textContent = '未设置';
      trigger.classList.remove('has-value');
    }
    renderActive();
  };

  const makeOption = (value, label, onClick) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'ds-time-option';
    btn.dataset.value = value;
    btn.textContent = label;
    btn.addEventListener('click', onClick);
    return btn;
  };

  for (let i = 0; i < 24; i += 1) {
    const value = pad(i);
    hourGrid.appendChild(makeOption(value, value, () => {
      selectedHour = value;
      syncHidden();
    }));
  }

  for (let i = 0; i < 60; i += 5) {
    const value = pad(i);
    minGrid.appendChild(makeOption(value, value, () => {
      selectedMin = value;
      syncHidden();
      if (selectedHour !== '') setOpen(false);
    }));
  }

  const applyValue = (val) => {
    if (val && /^\d{1,2}:\d{1,2}/.test(val)) {
      const [h, m] = val.split(':');
      selectedHour = pad(parseInt(h, 10));
      selectedMin = pad(parseInt(m, 10));
      if (!minGrid.querySelector(`[data-value="${selectedMin}"]`)) {
        const customMin = selectedMin;
        minGrid.appendChild(makeOption(customMin, customMin, () => {
          selectedMin = customMin;
          syncHidden();
          if (selectedHour !== '') setOpen(false);
        }));
      }
    } else {
      selectedHour = '';
      selectedMin = '';
    }
    syncHidden();
  };

  trigger.addEventListener('click', (event) => {
    event.stopPropagation();
    setOpen(popover.classList.contains('hidden'));
  });
  popover.addEventListener('click', (event) => event.stopPropagation());
  clearBtn?.addEventListener('click', () => {
    applyValue('');
    setOpen(false);
  });
  document.addEventListener('click', () => setOpen(false));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') setOpen(false);
  });
  window.addEventListener('resize', () => {
    if (popover.classList.contains('is-floating') && !popover.classList.contains('hidden')) {
      positionPopover();
    }
  });
  window.addEventListener('scroll', () => {
    if (popover.classList.contains('is-floating') && !popover.classList.contains('hidden')) {
      setOpen(false);
    }
  }, true);

  applyValue(wrap.dataset.value || hidden.value || '');

  return { applyValue };
}

function bindSettingsCard(card) {
  const dsId = parseInt(card.dataset.dsId, 10);
  const meta = (window.DATA_SOURCE_META || {})[dsId] || {};
  const files = meta.files || [];

  const fileSel = card.querySelector('.ds-order-file');
  const sheetSel = card.querySelector('.ds-order-sheet');
  const dateColSel = card.querySelector('.ds-order-date-col');
  const timeInput = card.querySelector('.ds-daily-time');
  const timePicker = initTimePicker(card);
  const reviewCount = card.querySelector('.ds-review-count');

  const fillSelect = (sel, items, value) => {
    sel.innerHTML = '';
    const empty = document.createElement('option');
    empty.value = '';
    empty.textContent = '请选择';
    sel.appendChild(empty);
    items.forEach((it) => {
      const o = document.createElement('option');
      o.value = typeof it === 'string' ? it : it.keyword || it;
      o.textContent = typeof it === 'string' ? it : (it.label || it.keyword || it);
      sel.appendChild(o);
    });
    if (value) sel.value = value;
  };

  const loadSheets = async (fileKw) => {
    if (!fileKw) {
      fillSelect(sheetSel, []);
      fillSelect(dateColSel, []);
      return;
    }
    const data = await apiJson(`/api/data-sources/${dsId}/schema?file=${encodeURIComponent(fileKw)}`);
    fillSelect(sheetSel, data.sheets || []);
  };

  const loadCols = async (fileKw, sheet) => {
    if (!fileKw || !sheet) {
      fillSelect(dateColSel, []);
      return;
    }
    const q = `file=${encodeURIComponent(fileKw)}&sheet=${encodeURIComponent(sheet)}`;
    const data = await apiJson(`/api/data-sources/${dsId}/schema?${q}`);
    fillSelect(dateColSel, data.columns || []);
  };

  fillSelect(fileSel, files.map((f) => ({ keyword: f.keyword, label: f.file_name || f.keyword })));

  const initial = (window.DS_SETTINGS || {})[dsId] || {};
  const tplSel = card.querySelector('.ds-excel-template');
  if (initial.excel_template_file && tplSel) tplSel.value = initial.excel_template_file;
  if (initial.order_file) fileSel.value = initial.order_file;
  loadSheets(initial.order_file).then(() => {
    if (initial.order_sheet) sheetSel.value = initial.order_sheet;
    return loadCols(initial.order_file, initial.order_sheet);
  }).then(() => {
    if (initial.order_date_col) dateColSel.value = initial.order_date_col;
    if (initial.daily_generate_at && timePicker) timePicker.applyValue(initial.daily_generate_at);
    if (reviewCount) reviewCount.textContent = String(initial.review_order_count || 0);
  }).catch(() => {});

  fileSel.addEventListener('change', () => {
    loadSheets(fileSel.value).then(() => loadCols(fileSel.value, sheetSel.value));
  });
  sheetSel.addEventListener('change', () => loadCols(fileSel.value, sheetSel.value));

  card.querySelector('.btn-save-ds-settings')?.addEventListener('click', async () => {
    try {
      const body = {
        order_file: fileSel.value || null,
        order_sheet: sheetSel.value || null,
        order_date_col: dateColSel.value || null,
        daily_generate_at: timeInput.value || null,
        excel_template_file: card.querySelector('.ds-excel-template')?.value || null,
      };
      const data = await apiJson(`/api/data-sources/${dsId}/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      settingsToast('店铺设置已保存');
      const summary = card.querySelector('.ds-date-summary');
      if (summary) summary.textContent = data.date_master_summary || '未配置';
    } catch (e) {
      settingsToast(e.message, false);
    }
  });
}

async function downloadConfigExport(dsId) {
  const res = await fetch(`/api/data-sources/${dsId}/config/export`);
  if (!res.ok) {
    let detail = '导出失败';
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) {
      const data = await res.json().catch(() => ({}));
      detail = data.detail || detail;
    } else {
      const text = await res.text().catch(() => '');
      if (text && text.length < 200) detail = text;
      if (res.status === 404) detail = '导出接口未就绪，请重启服务后重试';
    }
    throw new Error(detail);
  }
  const blob = await res.blob();
  let filename = 'autoreport-config.json';
  const disp = res.headers.get('Content-Disposition') || '';
  const match = /filename="([^"]+)"/.exec(disp);
  if (match) filename = match[1];
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function bindExportButtons() {
  document.querySelectorAll('.btn-export-config').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const dsId = btn.dataset.dsId;
      if (!dsId) return;
      try {
        await downloadConfigExport(dsId);
        settingsToast('配置已导出');
      } catch (e) {
        settingsToast(e.message, false);
      }
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.ds-settings-card').forEach(bindSettingsCard);
  bindExportButtons();
});
