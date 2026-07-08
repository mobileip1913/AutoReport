/** 共享表单控件：来源文件 / Sheet 下拉 + 列头模糊搜索 */

class SelectField {
  constructor(container, { placeholder = '请选择', options = [], value = '', onChange = null, size = 'sm' } = {}) {
    this.container = container;
    this.placeholder = placeholder;
    this.onChange = onChange;
    this.size = size;
    if (!container) {
      this.select = null;
      return;
    }
    this.container.innerHTML = '';
    this.container.className = 'relative';
    this.select = document.createElement('select');
    this.select.className = this._selectClass();
    this.setOpts(options, placeholder);
    this.set(value);
    this.select.addEventListener('change', () => {
      if (this.onChange) this.onChange(this.val());
    });
    this.container.appendChild(this.select);
  }

  _selectClass() {
    const size = this.size === 'md' ? 'form-control--md' : '';
    return `form-control ${size} font-mono`.trim();
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
  constructor(container, options, {
    value = '',
    placeholder = '搜索...',
    onPick = null,
    emptyHint = '无可选项',
    noMatchHint = '无匹配项',
    size = 'sm',
    maxItems = 80,
    inputClass = '',
    portal = null,
  } = {}) {
    this.container = container;
    this.options = options || [];
    this.onPick = onPick;
    this.emptyHint = emptyHint;
    this.noMatchHint = noMatchHint;
    this.maxItems = maxItems;
    this.size = size;
    this.portal = portal !== null ? portal : !!container?.closest('.app-modal');
    this._repositionBound = false;
    this._onReposition = () => {
      if (this.dropdown && !this.dropdown.classList.contains('hidden')) this._positionDropdown();
    };
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
    const sizeCls = size === 'md' ? 'form-control--md' : '';
    this.input.className = inputClass || `form-control ${sizeCls} font-mono`.trim();
    this.input.autocomplete = 'off';
    this.dropdown = document.createElement('div');
    if (this.portal) {
      this.dropdown.className = 'search-combo-dropdown search-combo-dropdown--portal hidden';
      document.body.appendChild(this.dropdown);
      this.container.appendChild(this.input);
    } else {
      this.dropdown.className = 'search-combo-dropdown absolute z-50 left-0 right-0 mt-1 max-h-48 overflow-y-auto bg-white border rounded-lg shadow-lg hidden';
      this.container.append(this.input, this.dropdown);
    }
    this.input.addEventListener('focus', () => this.show(this.input.value));
    this.input.addEventListener('input', () => this.show(this.input.value));
    this.input.addEventListener('blur', () => setTimeout(() => this.hide(), 150));
  }

  _positionDropdown() {
    if (!this.portal || !this.input || !this.dropdown) return;
    const rect = this.input.getBoundingClientRect();
    const margin = 10;
    const spaceBelow = window.innerHeight - rect.bottom - margin;
    const spaceAbove = rect.top - margin;
    const openDown = spaceBelow >= 140 || spaceBelow >= spaceAbove;
    const maxH = Math.min(360, Math.max(160, openDown ? spaceBelow : spaceAbove));

    const maxW = window.innerWidth - margin * 2;
    const width = Math.min(rect.width, maxW);
    const left = Math.max(margin, Math.min(rect.left, window.innerWidth - width - margin));

    this.dropdown.style.left = `${left}px`;
    this.dropdown.style.width = `${width}px`;
    if (openDown) {
      this.dropdown.style.top = `${rect.bottom + 4}px`;
      this.dropdown.style.bottom = 'auto';
    } else {
      this.dropdown.style.top = 'auto';
      this.dropdown.style.bottom = `${window.innerHeight - rect.top + 4}px`;
    }
    this.dropdown.style.maxHeight = `${maxH}px`;
  }

  _bindReposition() {
    if (this._repositionBound) return;
    this._repositionBound = true;
    window.addEventListener('scroll', this._onReposition, true);
    window.addEventListener('resize', this._onReposition);
  }

  _unbindReposition() {
    if (!this._repositionBound) return;
    this._repositionBound = false;
    window.removeEventListener('scroll', this._onReposition, true);
    window.removeEventListener('resize', this._onReposition);
  }

  hide() {
    if (!this.dropdown) return;
    this.dropdown.classList.add('hidden');
    this._unbindReposition();
  }

  show(q) {
    if (!this.dropdown) return;
    const kw = (q || '').toLowerCase();
    const matched = kw
      ? this.options.filter((o) => o.toLowerCase().includes(kw))
      : this.options;
    this.dropdown.innerHTML = '';
    if (!matched.length) {
      const empty = document.createElement('div');
      empty.className = 'search-combo-dropdown__empty';
      empty.textContent = kw ? this.noMatchHint : this.emptyHint;
      this.dropdown.appendChild(empty);
    } else {
      matched.slice(0, this.maxItems).forEach((opt) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'search-combo-dropdown__item';
        btn.textContent = opt;
        btn.onmousedown = (e) => {
          e.preventDefault();
          this.input.value = opt;
          this.hide();
          if (this.onPick) this.onPick(opt);
        };
        this.dropdown.appendChild(btn);
      });
    }
    if (this.portal) {
      this._positionDropdown();
      this._bindReposition();
    }
    this.dropdown.classList.remove('hidden');
  }

  val() { return (this.input?.value || '').trim(); }
  set(val) { if (this.input) this.input.value = val || ''; }
  setOpts(opts) {
    this.options = opts || [];
    if (this.input && this.input === document.activeElement) this.show(this.input.value);
  }

  destroy() {
    this.hide();
    if (this.dropdown?.parentNode) this.dropdown.parentNode.removeChild(this.dropdown);
    this.dropdown = null;
  }
}

function catalogFileLabel(f) {
  if (!f) return '';
  return f.label || f.file_label || f.keyword || '';
}

function fileSelectOptions(files) {
  return (files || []).map((f) => ({
    value: f.keyword,
    label: catalogFileLabel(f) || f.keyword,
  }));
}

const DATE_FIELD_WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日'];

function parseIsoDate(str) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(str || '').trim());
  if (!m) return null;
  const d = new Date(+m[1], +m[2] - 1, +m[3]);
  if (d.getFullYear() !== +m[1] || d.getMonth() !== +m[2] - 1 || d.getDate() !== +m[3]) return null;
  return d;
}

function formatIsoDate(d) {
  const y = d.getFullYear();
  const mo = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${mo}-${day}`;
}

function formatDateDisplay(iso) {
  const d = parseIsoDate(iso);
  if (!d) return '选择日期';
  const mo = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()} / ${mo} / ${day}`;
}

function calendarDays(year, month) {
  const first = new Date(year, month, 1);
  const startOffset = (first.getDay() + 6) % 7;
  const start = new Date(year, month, 1 - startOffset);
  return Array.from({ length: 42 }, (_, i) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + i));
}

class DateField {
  constructor(container, { value = '', name = 'report_date', onChange = null, size = 'md' } = {}) {
    this.container = container;
    this.onChange = onChange;
    this.size = size;
    this.name = name;
    this._open = false;
    this._view = parseIsoDate(value) || new Date();
    this._outsideClick = (e) => {
      if (!this._open) return;
      if (this.container?.contains(e.target) || this.panel?.contains(e.target)) return;
      this.close();
    };
    this._onKeydown = (e) => {
      if (e.key === 'Escape' && this._open) this.close();
    };
    if (!container) {
      this.hiddenInput = null;
      return;
    }

    container.innerHTML = '';
    container.className = 'date-field';

    this.hiddenInput = document.createElement('input');
    this.hiddenInput.type = 'hidden';
    this.hiddenInput.name = name;
    this.hiddenInput.value = parseIsoDate(value) ? value : '';

    this.trigger = document.createElement('button');
    this.trigger.type = 'button';
    this.trigger.className = `date-field__trigger form-control ${size === 'md' ? 'form-control--md' : ''}`.trim();
    this.trigger.setAttribute('aria-haspopup', 'dialog');
    this.trigger.setAttribute('aria-expanded', 'false');
    this.trigger.innerHTML = `
      <span class="date-field__value tabular-nums">${formatDateDisplay(this.hiddenInput.value)}</span>
      <span class="date-field__icon" aria-hidden="true">
        <svg viewBox="0 0 20 20" fill="none"><path d="M6 2.5v1.5M14 2.5v1.5M4.25 4.75h11.5M5.5 3.75h9a1.25 1.25 0 0 1 1.25 1.25v10.5A1.25 1.25 0 0 1 14.5 16.75h-9A1.25 1.25 0 0 1 4.25 15.5V5a1.25 1.25 0 0 1 1.25-1.25Z" stroke="currentColor" stroke-width="1.35" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </span>
    `;

    this.panel = document.createElement('div');
    this.panel.className = 'date-field__panel hidden';
    this.panel.setAttribute('role', 'dialog');
    this.panel.setAttribute('aria-label', '选择日期');
    document.body.appendChild(this.panel);

    container.append(this.hiddenInput, this.trigger);
    this.trigger.addEventListener('click', () => (this._open ? this.close() : this.open()));
    document.addEventListener('mousedown', this._outsideClick);
    document.addEventListener('keydown', this._onKeydown);
    this._updateTrigger();
    this._renderPanel();
  }

  val() { return this.hiddenInput?.value || ''; }

  set(v) {
    const d = parseIsoDate(v);
    if (!this.hiddenInput) return;
    this.hiddenInput.value = d ? v : '';
    if (d) this._view = d;
    this._updateTrigger();
    this._renderPanel();
  }

  _updateTrigger() {
    const valueEl = this.trigger?.querySelector('.date-field__value');
    if (valueEl) valueEl.textContent = formatDateDisplay(this.hiddenInput.value);
    this.trigger?.classList.toggle('date-field__trigger--placeholder', !this.hiddenInput.value);
  }

  _positionPanel() {
    if (!this.panel || !this.trigger) return;
    const rect = this.trigger.getBoundingClientRect();
    const margin = 10;
    const panelW = 280;
    const left = Math.max(margin, Math.min(rect.left, window.innerWidth - panelW - margin));
    const spaceBelow = window.innerHeight - rect.bottom - margin;
    const spaceAbove = rect.top - margin;
    const openDown = spaceBelow >= 300 || spaceBelow >= spaceAbove;
    this.panel.style.width = `${panelW}px`;
    this.panel.style.left = `${left}px`;
    if (openDown) {
      this.panel.style.top = `${rect.bottom + 6}px`;
      this.panel.style.bottom = 'auto';
    } else {
      this.panel.style.top = 'auto';
      this.panel.style.bottom = `${window.innerHeight - rect.top + 6}px`;
    }
  }

  open() {
    const selected = parseIsoDate(this.hiddenInput.value);
    if (selected) this._view = new Date(selected.getFullYear(), selected.getMonth(), selected.getDate());
    this._open = true;
    this.trigger.setAttribute('aria-expanded', 'true');
    this.trigger.classList.add('is-open');
    this.panel.classList.remove('hidden');
    this._renderPanel();
    this._positionPanel();
    requestAnimationFrame(() => this.panel.classList.add('is-open'));
    window.addEventListener('scroll', this._onReposition = () => this._positionPanel(), true);
    window.addEventListener('resize', this._onReposition);
  }

  close() {
    this._open = false;
    this.trigger?.setAttribute('aria-expanded', 'false');
    this.trigger?.classList.remove('is-open');
    this.panel?.classList.remove('is-open');
    setTimeout(() => {
      if (!this._open) this.panel?.classList.add('hidden');
    }, 180);
    if (this._onReposition) {
      window.removeEventListener('scroll', this._onReposition, true);
      window.removeEventListener('resize', this._onReposition);
    }
  }

  _pick(iso) {
    if (!this.hiddenInput) return;
    this.hiddenInput.value = iso || '';
    this._updateTrigger();
    this._renderPanel();
    if (this.onChange) this.onChange(iso);
    this.close();
  }

  _renderPanel() {
    if (!this.panel) return;
    const y = this._view.getFullYear();
    const m = this._view.getMonth();
    const selectedIso = this.hiddenInput.value;
    const todayIso = formatIsoDate(new Date());
    const monthLabel = `${y}年${String(m + 1).padStart(2, '0')}月`;

    this.panel.innerHTML = `
      <header class="date-field__header">
        <button type="button" class="date-field__nav" data-nav="-1" aria-label="上个月">
          <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M12.5 5 7.5 10l5 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
        <span class="date-field__month tabular-nums">${monthLabel}</span>
        <button type="button" class="date-field__nav" data-nav="1" aria-label="下个月">
          <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M7.5 5 12.5 10l-5 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
      </header>
      <div class="date-field__weekdays">
        ${DATE_FIELD_WEEKDAYS.map((w) => `<span>${w}</span>`).join('')}
      </div>
      <div class="date-field__grid" role="grid">
        ${calendarDays(y, m).map((d) => {
          const iso = formatIsoDate(d);
          const outside = d.getMonth() !== m;
          const isSelected = iso === selectedIso;
          const isToday = iso === todayIso;
          const cls = [
            'date-field__day',
            outside ? 'is-outside' : '',
            isSelected ? 'is-selected' : '',
            isToday && !isSelected ? 'is-today' : '',
          ].filter(Boolean).join(' ');
          return `<button type="button" class="${cls}" data-iso="${iso}" role="gridcell">${d.getDate()}</button>`;
        }).join('')}
      </div>
      <footer class="date-field__footer">
        <button type="button" class="date-field__footer-btn" data-action="clear">清除</button>
        <button type="button" class="date-field__footer-btn date-field__footer-btn--primary" data-action="today">今天</button>
      </footer>
    `;

    this.panel.querySelector('[data-nav="-1"]')?.addEventListener('click', () => {
      this._view = new Date(y, m - 1, 1);
      this._renderPanel();
    });
    this.panel.querySelector('[data-nav="1"]')?.addEventListener('click', () => {
      this._view = new Date(y, m + 1, 1);
      this._renderPanel();
    });
    this.panel.querySelectorAll('.date-field__day').forEach((btn) => {
      btn.addEventListener('click', () => this._pick(btn.dataset.iso));
    });
    this.panel.querySelector('[data-action="clear"]')?.addEventListener('click', () => this._pick(''));
    this.panel.querySelector('[data-action="today"]')?.addEventListener('click', () => this._pick(todayIso));
  }

  destroy() {
    this.close();
    document.removeEventListener('mousedown', this._outsideClick);
    document.removeEventListener('keydown', this._onKeydown);
    if (this.panel?.parentNode) this.panel.parentNode.removeChild(this.panel);
    this.panel = null;
  }
}

window.SelectField = SelectField;
window.SearchCombo = SearchCombo;
window.DateField = DateField;
window.catalogFileLabel = catalogFileLabel;
window.fileSelectOptions = fileSelectOptions;
