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
    const pad = this.size === 'md' ? 'px-2 py-1.5 text-sm' : 'px-2 py-1.5 text-xs';
    return `w-full border rounded-lg ${pad} font-mono focus:ring-2 focus:ring-sky-200 outline-none bg-white`;
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
  } = {}) {
    this.container = container;
    this.options = options || [];
    this.onPick = onPick;
    this.emptyHint = emptyHint;
    this.noMatchHint = noMatchHint;
    this.maxItems = maxItems;
    this.size = size;
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
    const pad = size === 'md' ? 'px-2 py-1.5 text-sm' : 'px-2 py-1.5 text-xs';
    this.input.className = `w-full border rounded-lg ${pad} font-mono focus:ring-2 focus:ring-sky-200 outline-none bg-white`;
    this.input.autocomplete = 'off';
    this.dropdown = document.createElement('div');
    this.dropdown.className = 'absolute z-50 left-0 right-0 mt-1 max-h-48 overflow-y-auto bg-white border rounded-lg shadow-lg hidden';
    this.container.append(this.input, this.dropdown);
    this.input.addEventListener('focus', () => this.show(this.input.value));
    this.input.addEventListener('input', () => this.show(this.input.value));
    this.input.addEventListener('blur', () => setTimeout(() => this.dropdown.classList.add('hidden'), 150));
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
      empty.className = 'px-2 py-1.5 text-xs text-slate-400';
      empty.textContent = kw ? this.noMatchHint : this.emptyHint;
      this.dropdown.appendChild(empty);
    } else {
      matched.slice(0, this.maxItems).forEach((opt) => {
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

window.SelectField = SelectField;
window.SearchCombo = SearchCombo;
window.catalogFileLabel = catalogFileLabel;
window.fileSelectOptions = fileSelectOptions;
