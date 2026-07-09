/** 共享表单控件：来源文件 / Sheet 下拉 + 列头模糊搜索 */

const SELECT_CHEVRON = `<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="m6 8 4 4 4-4"/></svg>`;

function normalizeSelectOptions(options) {
  return (options || []).map((o) => (
    typeof o === 'string' ? { value: o, label: o } : { value: String(o.value ?? ''), label: String(o.label ?? o.value ?? '') }
  ));
}

class SelectField {
  constructor(container, {
    placeholder = '请选择',
    options = [],
    value = '',
    onChange = null,
    size = 'sm',
    variant = 'default',
    triggerClass = '',
  } = {}) {
    this.container = container;
    this.placeholder = placeholder;
    this.onChange = onChange;
    this.size = size;
    this.variant = variant;
    this.triggerClass = triggerClass;
    this._allowEmpty = true;
    this._open = false;
    this._options = [];
    this._value = '';
    this._disabled = false;
    this._outsideClick = (e) => {
      if (!this._open) return;
      if (this.container?.contains(e.target) || this.menu?.contains(e.target)) return;
      this.close();
    };
    this._onKeydown = (e) => {
      if (e.key === 'Escape' && this._open) this.close();
    };
    this._onReposition = () => {
      if (this._open) this._positionMenu();
    };
    if (!container) {
      this.select = null;
      return;
    }

    container.innerHTML = '';
    container.className = `custom-select custom-select--${variant} relative`;

    this.trigger = document.createElement('button');
    this.trigger.type = 'button';
    this.trigger.className = this._triggerClass();
    this.trigger.setAttribute('aria-haspopup', 'listbox');
    this.trigger.setAttribute('aria-expanded', 'false');
    this.trigger.innerHTML = `
      <span class="custom-select__label"></span>
      <span class="custom-select__chevron">${SELECT_CHEVRON}</span>
    `;

    this.menu = document.createElement('div');
    this.menu.className = 'custom-select__menu hidden';
    this.menu.setAttribute('role', 'listbox');
    document.body.appendChild(this.menu);

    // 兼容旧调用方访问 .select
    this.select = {
      get value() { return this._owner._value; },
      set value(v) { this._owner.set(v); },
      addEventListener: () => {},
      classList: { toggle: () => {} },
      _owner: this,
    };

    container.appendChild(this.trigger);
    this.trigger.addEventListener('click', () => {
      if (this._disabled) return;
      this._open ? this.close() : this.open();
    });
    document.addEventListener('mousedown', this._outsideClick);
    document.addEventListener('keydown', this._onKeydown);

    this.setOpts(options, placeholder);
    this.set(value);
  }

  _triggerClass() {
    if (this.triggerClass) return `custom-select__trigger ${this.triggerClass}`.trim();
    if (this.variant === 'pill') return 'custom-select__trigger custom-select__trigger--pill';
    const size = this.size === 'md' ? 'form-control--md' : '';
    return `custom-select__trigger form-control ${size} font-mono`.trim();
  }

  setOpts(options, placeholder) {
    this.placeholder = placeholder || this.placeholder;
    this._options = normalizeSelectOptions(options);
    if (this._value && !this._options.some((o) => o.value === this._value)) {
      this._value = '';
    }
    this._syncTrigger();
    if (this._open) this._renderMenu();
  }

  val() { return this._value || ''; }

  set(v) {
    this._value = v == null ? '' : String(v);
    this._syncTrigger();
    if (this._open) this._renderMenu();
  }

  setDisabled(dis) {
    this._disabled = !!dis;
    if (this.trigger) {
      this.trigger.disabled = this._disabled;
      this.trigger.classList.toggle('opacity-50', this._disabled);
    }
    if (this._disabled) this.close();
  }

  open() {
    if (!this.menu || this._disabled) return;
    this._open = true;
    this.trigger?.setAttribute('aria-expanded', 'true');
    this.trigger?.classList.add('is-open');
    this._renderMenu();
    this.menu.classList.remove('hidden');
    this._positionMenu();
    window.addEventListener('resize', this._onReposition);
    window.addEventListener('scroll', this._onReposition, true);
  }

  close() {
    if (!this.menu) return;
    this._open = false;
    this.trigger?.setAttribute('aria-expanded', 'false');
    this.trigger?.classList.remove('is-open');
    this.menu.classList.add('hidden');
    window.removeEventListener('resize', this._onReposition);
    window.removeEventListener('scroll', this._onReposition, true);
  }

  _syncTrigger() {
    const label = this.trigger?.querySelector('.custom-select__label');
    if (!label) return;
    const hit = this._options.find((o) => o.value === this._value);
    if (hit) {
      label.textContent = hit.label;
      label.classList.remove('is-placeholder');
    } else {
      label.textContent = this.placeholder;
      label.classList.add('is-placeholder');
    }
  }

  _positionMenu() {
    if (!this.menu || !this.trigger) return;
    const rect = this.trigger.getBoundingClientRect();
    const width = Math.max(rect.width, 12 * 16);
    const maxH = Math.min(280, Math.max(120, window.innerHeight - rect.bottom - 12));
    const spaceBelow = window.innerHeight - rect.bottom;
    this.menu.style.width = `${width}px`;
    this.menu.style.left = `${Math.min(rect.left, window.innerWidth - width - 8)}px`;
    this.menu.style.maxHeight = `${maxH}px`;
    if (spaceBelow < 160 && rect.top > spaceBelow) {
      this.menu.style.top = 'auto';
      this.menu.style.bottom = `${window.innerHeight - rect.top + 6}px`;
    } else {
      this.menu.style.top = `${rect.bottom + 6}px`;
      this.menu.style.bottom = 'auto';
    }
  }

  _renderMenu() {
    if (!this.menu) return;
    this.menu.innerHTML = '';
    const list = this._allowEmpty
      ? [{ value: '', label: this.placeholder }, ...this._options]
      : this._options;
    if (!list.length) {
      const empty = document.createElement('div');
      empty.className = 'custom-select__empty';
      empty.textContent = this.placeholder || '无可选项';
      this.menu.appendChild(empty);
      return;
    }
    list.forEach((o) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'custom-select__option';
      btn.setAttribute('role', 'option');
      btn.setAttribute('aria-selected', o.value === this._value ? 'true' : 'false');
      if (o.value === this._value) btn.classList.add('is-active');
      if (!o.value) btn.classList.add('is-placeholder');
      btn.textContent = o.label;
      btn.addEventListener('click', () => {
        const next = o.value;
        const changed = next !== this._value;
        this.set(next);
        this.close();
        if (changed && this.onChange) this.onChange(this.val());
      });
      this.menu.appendChild(btn);
    });
  }

  destroy() {
    this.close();
    document.removeEventListener('mousedown', this._outsideClick);
    document.removeEventListener('keydown', this._onKeydown);
    if (this.menu?.parentNode) this.menu.parentNode.removeChild(this.menu);
    this.menu = null;
  }
}

/** 将原生 <select> 升级为圆角自定义下拉（保留原 select 用于表单提交） */
function enhanceNativeSelect(select, { variant = 'default', triggerClass = '' } = {}) {
  if (!select || select.dataset.customSelectBound === '1') return null;
  select.dataset.customSelectBound = '1';

  const hasEmpty = [...select.options].some((o) => o.value === '');
  const options = [...select.options]
    .filter((o) => o.value !== '')
    .map((o) => ({ value: o.value, label: o.textContent }));
  const placeholder = hasEmpty
    ? (select.querySelector('option[value=""]')?.textContent || '请选择')
    : (options.find((o) => o.value === select.value)?.label || options[0]?.label || '请选择');

  const wrap = document.createElement('div');
  wrap.className = `custom-select custom-select--${variant === 'pill' ? 'pill' : 'default'} relative`;
  select.parentNode.insertBefore(wrap, select);
  wrap.appendChild(select);
  select.classList.add('custom-select__native');
  select.tabIndex = -1;
  select.setAttribute('aria-hidden', 'true');

  const field = new SelectField(wrap, {
    placeholder,
    options,
    value: select.value,
    size: select.classList.contains('form-control--md') || select.classList.contains('modal-input') ? 'md' : 'sm',
    variant,
    triggerClass,
    onChange: (v) => {
      select.value = v;
      select.dispatchEvent(new Event('change', { bubbles: true }));
      // 内联 onchange（如 switch-store 表单提交）在部分浏览器不会被 dispatchEvent 触发
      const attr = select.getAttribute('onchange');
      if (attr) {
        try {
          // eslint-disable-next-line no-new-func
          Function('event', attr).call(select, new Event('change'));
        } catch (_) { /* ignore */ }
      }
    },
  });
  field._allowEmpty = hasEmpty;

  // SelectField 清空了 wrap，把原生 select 挂回去
  wrap.appendChild(select);
  return field;
}

function enhancePageSelects() {
  document.querySelectorAll('select.daily-hub__store-select').forEach((el) => {
    enhanceNativeSelect(el, { variant: 'pill' });
  });
  document.querySelectorAll('select.store-bind-select:not(.daily-hub__store-select)').forEach((el) => {
    enhanceNativeSelect(el, { variant: 'default', triggerClass: 'custom-select__trigger--store' });
  });
  document.querySelectorAll('select.form-control, select.modal-input').forEach((el) => {
    if (el.closest('.custom-select')) return;
    if (el.dataset.customSelectBound === '1') return;
    enhanceNativeSelect(el, { variant: 'default' });
  });
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
    this._setOptions(options);
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
    this.input.value = this.objectMode ? (this._labelByValue[value] || '') : (value || '');
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
          if (this.onPick) this.onPick(this.objectMode ? (this._valueByLabel[opt] ?? '') : opt);
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

  _setOptions(list) {
    const opts = list || [];
    this.objectMode = opts.some((o) => o && typeof o === 'object');
    this._valueByLabel = {};
    this._labelByValue = {};
    if (this.objectMode) {
      this.options = opts.map((o) => {
        const label = (o && typeof o === 'object') ? String(o.label) : String(o);
        const value = (o && typeof o === 'object') ? o.value : o;
        this._valueByLabel[label] = value;
        this._labelByValue[value] = label;
        return label;
      });
    } else {
      this.options = opts;
    }
  }

  val() {
    const text = (this.input?.value || '').trim();
    if (this.objectMode) return this._valueByLabel[text] ?? '';
    return text;
  }

  set(val) {
    if (!this.input) return;
    this.input.value = this.objectMode ? (this._labelByValue[val] || '') : (val || '');
  }

  setOpts(opts) {
    this._setOptions(opts);
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
window.enhanceNativeSelect = enhanceNativeSelect;
window.enhancePageSelects = enhancePageSelects;
window.catalogFileLabel = catalogFileLabel;
window.fileSelectOptions = fileSelectOptions;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', enhancePageSelects);
} else {
  enhancePageSelects();
}
