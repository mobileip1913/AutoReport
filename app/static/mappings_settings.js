/** 报表配置页：日期主表 + 每日自动生成时间 */

function settingsToast(msg, ok = true) {
  const el = document.getElementById('toast') || document.getElementById('dailyToast');
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

function updateReviewSidebarCounts(dsId, data) {
  const card = document.querySelector(`.ds-settings-card[data-ds-id="${dsId}"]`);
  if (!card || !data) return;
  const orderCountEl = card.querySelector('.ds-review-order-count');
  if (orderCountEl && data.review_order_distinct != null) {
    orderCountEl.textContent = String(data.review_order_distinct);
  }
  const rowCount = card.querySelector('.ds-review-count');
  if (rowCount && data.review_order_count != null) {
    rowCount.textContent = String(data.review_order_count);
  }
}

function updateReviewLogisticsSummary(dsId, data) {
  const summary = data?.review_logistics_rule_summary;
  if (!summary) return;
  document.querySelectorAll(`.review-logistics-rule-summary[data-ds-id="${dsId}"]`).forEach((el) => {
    el.textContent = `店铺刷单规则 · ${summary}`;
  });
  const modalSummary = document.querySelector('#reviewSettingsModal .review-logistics-modal-summary');
  if (modalSummary) modalSummary.textContent = summary;
}

function updateReviewModalStats(modal, data) {
  if (!modal || !data) return;
  const rowsEl = modal.querySelector('.review-stat-rows');
  const ordersEl = modal.querySelector('.review-stat-orders');
  if (rowsEl && data.review_order_count != null) rowsEl.textContent = String(data.review_order_count);
  if (ordersEl && data.review_order_distinct != null) ordersEl.textContent = String(data.review_order_distinct);
}

function bindReviewSettingsModal() {
  const modal = document.getElementById('reviewSettingsModal');
  if (!modal) return;

  const panel = document.getElementById('reviewSettingsPanel');
  const templateLink = modal.querySelector('.review-template-link');
  const importInput = modal.querySelector('.review-import-input');
  const importHint = modal.querySelector('.review-import-hint');
  const perOrderInput = modal.querySelector('.review-logistics-per-order');
  const excludeSameDayRefund = modal.querySelector('.review-logistics-exclude-same-day-refund');
  const saveBtn = modal.querySelector('.btn-save-review-settings');
  let activeDsId = null;

  const setOpen = (open) => {
    modal.classList.toggle('hidden', !open);
    requestAnimationFrame(() => {
      modal.classList.toggle('opacity-0', !open);
      if (panel) panel.classList.toggle('scale-95', !open);
    });
    document.body.classList.toggle('overflow-hidden', open);
  };

  const showImportHint = (text, ok = true) => {
    if (!importHint) return;
    importHint.textContent = text;
    importHint.classList.remove('hidden', 'text-red-500', 'text-emerald-600', 'text-slate-400');
    importHint.classList.add(ok ? 'text-emerald-600' : 'text-red-500');
  };

  const fillFromSettings = (dsId) => {
    const st = (window.DS_SETTINGS || {})[dsId] || {};
    if (templateLink) templateLink.href = `/daily/review-template?data_source_id=${dsId}`;
    if (perOrderInput) perOrderInput.value = String(st.review_logistics_per_order ?? 1);
    if (excludeSameDayRefund) {
      excludeSameDayRefund.checked = st.review_logistics_exclude_same_day_refund !== false;
    }
    updateReviewModalStats(modal, st);
    updateReviewLogisticsSummary(dsId, st);
    if (importHint) {
      importHint.textContent = '';
      importHint.classList.add('hidden');
    }
    if (importInput) importInput.value = '';
  };

  const applySettingsData = (dsId, data) => {
    if (window.DS_SETTINGS) window.DS_SETTINGS[dsId] = { ...(window.DS_SETTINGS[dsId] || {}), ...data };
    updateReviewModalStats(modal, data);
    updateReviewLogisticsSummary(dsId, data);
    updateReviewSidebarCounts(dsId, data);
  };

  document.querySelectorAll('.btn-review-settings').forEach((btn) => {
    btn.addEventListener('click', () => {
      activeDsId = parseInt(btn.dataset.dsId, 10);
      if (!activeDsId) return;
      fillFromSettings(activeDsId);
      setOpen(true);
    });
  });

  modal.querySelectorAll('[data-close-review-settings]').forEach((el) => {
    el.addEventListener('click', () => setOpen(false));
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !modal.classList.contains('hidden')) setOpen(false);
  });

  importInput?.addEventListener('change', async () => {
    const file = importInput.files?.[0];
    if (!file || !activeDsId) return;
    showImportHint('导入中…', true);
    importHint?.classList.remove('text-emerald-600');
    importHint?.classList.add('text-slate-400');
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await fetch(`/api/data-sources/${activeDsId}/review-orders/import`, { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) {
        const msg = typeof data.detail === 'string'
          ? data.detail
          : (Array.isArray(data.detail) ? data.detail.join('；') : (data.errors?.join('；') || data.detail?.errors?.join('；') || '导入失败'));
        showImportHint(msg, false);
        return;
      }
      const merged = {
        ...(window.DS_SETTINGS?.[activeDsId] || {}),
        review_order_count: data.review_order_count ?? data.imported,
        review_order_distinct: data.review_order_distinct ?? data.imported,
        review_logistics_rule_summary: data.review_logistics_summary,
      };
      applySettingsData(activeDsId, merged);
      const orders = data.review_order_distinct ?? data.imported;
      let msg = `已导入 ${data.imported} 行 · ${orders} 个刷单订单`;
      if (data.review_logistics_total != null) {
        msg += ` · 物流费将计 $${Number(data.review_logistics_total).toFixed(2)}`;
      }
      showImportHint(msg, true);
    } catch (e) {
      showImportHint(e.message || '导入失败', false);
    }
    importInput.value = '';
  });

  saveBtn?.addEventListener('click', async () => {
    if (!activeDsId) return;
    try {
      const data = await apiJson(`/api/data-sources/${activeDsId}/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          review_logistics_mode: 'per_order_fixed',
          review_logistics_per_order: perOrderInput?.value || null,
          review_logistics_exclude_same_day_refund: !!excludeSameDayRefund?.checked,
        }),
      });
      applySettingsData(activeDsId, data);
      settingsToast('刷单设置已保存');
      setOpen(false);
    } catch (e) {
      settingsToast(e.message, false);
    }
  });
}

function bindSettingsCard(card) {
  const dsId = parseInt(card.dataset.dsId, 10);
  const meta = (window.DATA_SOURCE_META || {})[dsId] || {};
  const files = meta.files || [];

  const fileHost = card.querySelector('.ds-order-file-host');
  const sheetHost = card.querySelector('.ds-order-sheet-host');
  const dateColHost = card.querySelector('.ds-order-date-col-host');
  const timeInput = card.querySelector('.ds-daily-time');
  const timePicker = initTimePicker(card);
  const reviewCount = card.querySelector('.ds-review-count');

  let sheetSelect;
  const fileSelect = new SelectField(fileHost, {
    placeholder: '请选择来源文件',
    options: fileSelectOptions(files),
    size: 'md',
    onChange: (fileKw) => {
      loadSheets(fileKw, '').then(() => loadCols(fileKw, sheetSelect.val(), ''));
    },
  });
  sheetSelect = new SelectField(sheetHost, {
    placeholder: '请先选择来源文件',
    options: [],
    size: 'md',
    onChange: (sheet) => loadCols(fileSelect.val(), sheet, ''),
  });
  const dateColCombo = new SearchCombo(dateColHost, [], {
    placeholder: '搜索列头，如 Time',
    emptyHint: '请先选择 Sheet',
    noMatchHint: '无匹配列头',
    size: 'md',
  });

  const loadSheets = async (fileKw, keepSheet) => {
    if (!fileKw) {
      sheetSelect.setOpts([], '请先选择来源文件');
      sheetSelect.setDisabled(true);
      dateColCombo.setOpts([]);
      dateColCombo.set('');
      return;
    }
    const data = await apiJson(`/api/data-sources/${dsId}/schema?file=${encodeURIComponent(fileKw)}`);
    const sheets = data.sheets || [];
    sheetSelect.setOpts(sheets, sheets.length ? '请选择 Sheet' : '该文件无 Sheet');
    sheetSelect.setDisabled(!sheets.length);
    if (keepSheet !== undefined) {
      const sheet = keepSheet && sheets.includes(keepSheet) ? keepSheet : '';
      sheetSelect.set(sheet);
    }
  };

  const loadCols = async (fileKw, sheet, keepCol) => {
    if (!fileKw || !sheet) {
      dateColCombo.setOpts([]);
      dateColCombo.set('');
      return;
    }
    const q = `file=${encodeURIComponent(fileKw)}&sheet=${encodeURIComponent(sheet)}`;
    const data = await apiJson(`/api/data-sources/${dsId}/schema?${q}`);
    const cols = data.columns || [];
    dateColCombo.setOpts(cols);
    if (keepCol !== undefined) {
      dateColCombo.set(keepCol && cols.includes(keepCol) ? keepCol : '');
    }
  };

  const initial = (window.DS_SETTINGS || {})[dsId] || {};
  const tplSel = card.querySelector('.ds-excel-template');
  if (initial.excel_template_file && tplSel) tplSel.value = initial.excel_template_file;
  if (initial.order_file) fileSelect.set(initial.order_file);
  loadSheets(initial.order_file, initial.order_sheet).then(() => {
    return loadCols(initial.order_file, initial.order_sheet, initial.order_date_col);
  }).then(() => {
    if (initial.daily_generate_at && timePicker) timePicker.applyValue(initial.daily_generate_at);
    if (reviewCount) reviewCount.textContent = String(initial.review_order_count || 0);
    const orderCountEl = card.querySelector('.ds-review-order-count');
    if (orderCountEl) orderCountEl.textContent = String(initial.review_order_distinct || 0);
    updateReviewLogisticsSummary(dsId, initial);
  }).catch(() => {});

  card.querySelector('.btn-save-ds-settings')?.addEventListener('click', async () => {
    try {
      const body = {
        order_file: fileSelect.val() || null,
        order_sheet: sheetSelect.val() || null,
        order_date_col: dateColCombo.val() || null,
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
      if (window.DS_SETTINGS) window.DS_SETTINGS[dsId] = { ...(window.DS_SETTINGS[dsId] || {}), ...data };
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
  bindReviewSettingsModal();
  bindExportButtons();
});
