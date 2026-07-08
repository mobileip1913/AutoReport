function toastFormula(msg, ok = true) {
  window.showAppToast?.(msg, ok);
}

function renderFieldPicker(dsId) {
  const box = document.getElementById('formulaFieldPicker');
  if (!box) return;
  box.innerHTML = '';
  const fields = (window.REUSE_FIELDS_BY_DS && window.REUSE_FIELDS_BY_DS[dsId]) || [];
  fields.forEach((f) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'text-xs px-2 py-0.5 rounded bg-slate-100 hover:bg-teal-100 text-slate-600 font-mono';
    btn.textContent = `{field:${f.code}}`;
    btn.title = f.name;
    btn.onclick = () => {
      const ta = document.getElementById('formulaExpression');
      const token = `{field:${f.code}}`;
      const start = ta.selectionStart || ta.value.length;
      const end = ta.selectionEnd || start;
      ta.value = ta.value.slice(0, start) + token + ta.value.slice(end);
      ta.focus();
    };
    box.appendChild(btn);
  });
}

function openFormulaModal(mode, mappingId, dsId) {
  const modal = document.getElementById('formulaModal');
  document.getElementById('formulaMappingId').value = mappingId || '';
  document.getElementById('formulaDataSourceId').value = dsId || '';
  document.getElementById('btnDeleteFormula').classList.toggle('hidden', mode !== 'edit');
  document.getElementById('formulaModalTitle').textContent = mode === 'edit' ? '编辑公式行' : '新增公式行';

  if (mode === 'create') {
    document.getElementById('formulaLabel').value = '';
    document.getElementById('formulaGroup').value = '';
    document.getElementById('formulaSort').value = '0';
    document.getElementById('formulaExpression').value = '=';
    document.getElementById('formulaFormat').value = 'usd';
    document.getElementById('formulaHighlight').checked = false;
    renderFieldPicker(parseInt(dsId, 10));
  } else {
    fetch(`/api/mappings/${mappingId}`)
      .then((r) => r.json())
      .then((data) => {
        document.getElementById('formulaLabel').value = data.label || '';
        document.getElementById('formulaGroup').value = data.report_group || '';
        document.getElementById('formulaSort').value = String(data.sort_order || 0);
        document.getElementById('formulaExpression').value = data.expression || '';
        document.getElementById('formulaFormat').value = data.format_type || 'usd';
        document.getElementById('formulaHighlight').checked = !!data.is_highlight;
        renderFieldPicker(data.data_source_id);
      });
  }

  modal.classList.remove('hidden');
  requestAnimationFrame(() => modal.classList.remove('opacity-0'));
}

function closeFormulaModal() {
  const modal = document.getElementById('formulaModal');
  modal.classList.add('opacity-0');
  setTimeout(() => modal.classList.add('hidden'), 200);
}

async function saveFormula() {
  const id = document.getElementById('formulaMappingId').value;
  const dsId = parseInt(document.getElementById('formulaDataSourceId').value, 10);
  const body = {
    label: document.getElementById('formulaLabel').value.trim(),
    report_group: document.getElementById('formulaGroup').value.trim() || null,
    sort_order: parseInt(document.getElementById('formulaSort').value, 10) || 0,
    expression: document.getElementById('formulaExpression').value.trim(),
    format_type: document.getElementById('formulaFormat').value,
    is_highlight: document.getElementById('formulaHighlight').checked,
  };
  if (!body.label || !body.expression) {
    toastFormula('请填写名称与表达式', false);
    return;
  }

  const url = id ? `/api/formula-lines/${id}` : '/api/formula-lines';
  const method = id ? 'PUT' : 'POST';
  if (!id) body.data_source_id = dsId;

  const res = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) return toastFormula(data.detail || '保存失败', false);
  toastFormula('保存成功');
  closeFormulaModal();
  setTimeout(() => location.reload(), 500);
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-formula-close]').forEach((el) => {
    el.addEventListener('click', closeFormulaModal);
  });
  document.getElementById('btnNewFormula')?.addEventListener('click', () => {
    const dsSelect = document.getElementById('newDataSource');
    const dsId = dsSelect ? dsSelect.value : '1';
    openFormulaModal('create', null, dsId);
  });
  document.querySelectorAll('.btn-edit-formula').forEach((btn) => {
    btn.addEventListener('click', () => {
      openFormulaModal('edit', parseInt(btn.dataset.id, 10), parseInt(btn.dataset.ds, 10));
    });
  });
  document.getElementById('btnSaveFormula')?.addEventListener('click', saveFormula);
  document.getElementById('btnDeleteFormula')?.addEventListener('click', async () => {
    const id = document.getElementById('formulaMappingId').value;
    if (!id || !confirm('确定删除此公式行？')) return;
    const res = await fetch(`/api/mappings/${id}`, { method: 'DELETE' });
    if (res.ok) {
      toastFormula('已删除');
      closeFormulaModal();
      setTimeout(() => location.reload(), 500);
    }
  });
});
