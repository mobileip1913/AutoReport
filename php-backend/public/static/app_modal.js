/** 统一弹窗：滚动锁、Esc 栈、进出场过渡 */
const AppModal = (() => {
  const stack = [];
  let scrollLockCount = 0;

  function lockScroll() {
    scrollLockCount += 1;
    if (scrollLockCount === 1) {
      // 补偿滚动条宽度，避免锁定滚动后页面变宽跳动
      const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;
      if (scrollbarWidth > 0) document.body.style.paddingRight = `${scrollbarWidth}px`;
      document.body.classList.add('overflow-hidden');
    }
  }

  function unlockScroll() {
    scrollLockCount = Math.max(0, scrollLockCount - 1);
    if (scrollLockCount === 0) {
      document.body.classList.remove('overflow-hidden');
      document.body.style.paddingRight = '';
    }
  }

  function getPanel(modal) {
    return modal.querySelector('.app-modal__panel');
  }

  function open(modal, opts = {}) {
    if (!modal) return;
    const wasHidden = modal.classList.contains('hidden');
    if (!wasHidden && !opts.force) return;

    if (wasHidden) {
      stack.push({ modal, onClose: opts.onClose || null });
      modal.classList.remove('hidden');
      modal.setAttribute('aria-hidden', 'false');
      lockScroll();
    }

    requestAnimationFrame(() => {
      modal.classList.remove('opacity-0');
      getPanel(modal)?.classList.add('is-open');
      opts.onOpen?.();
      if (opts.focus !== false) {
        const panel = getPanel(modal);
        const focusable = panel?.querySelector(
          'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        );
        focusable?.focus({ preventScroll: true });
      }
    });
  }

  function close(modal) {
    if (!modal || modal.classList.contains('hidden')) return;
    const idx = stack.findIndex((s) => s.modal === modal);
    const entry = idx >= 0 ? stack.splice(idx, 1)[0] : null;

    modal.classList.add('opacity-0');
    getPanel(modal)?.classList.remove('is-open');
    modal.setAttribute('aria-hidden', 'true');
    unlockScroll();

    setTimeout(() => {
      modal.classList.add('hidden');
      entry?.onClose?.();
    }, 200);
  }

  function closeTop() {
    const top = stack[stack.length - 1];
    if (top) close(top.modal);
  }

  function isOpen(modal) {
    return modal && !modal.classList.contains('hidden');
  }

  function bind(modal, opts = {}) {
    const closeAttr = opts.closeAttr || 'data-modal-close';
    modal.querySelectorAll(`[${closeAttr}]`).forEach((el) => {
      el.addEventListener('click', () => close(modal));
    });
    const backdrop = modal.querySelector('.app-modal__backdrop');
    backdrop?.addEventListener('click', () => close(modal));
  }

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || !stack.length) return;
    event.preventDefault();
    closeTop();
  });

  return { open, close, closeTop, bind, isOpen, lockScroll, unlockScroll };
})();

/** 项目风格确认框，替代 window.confirm */
const AppConfirm = (() => {
  let resolveFn = null;
  let bound = false;

  function ensureModal() {
    let modal = document.getElementById('appConfirmModal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'appConfirmModal';
      modal.className = 'app-modal app-confirm hidden opacity-0';
      modal.setAttribute('aria-hidden', 'true');
      modal.setAttribute('role', 'alertdialog');
      modal.setAttribute('aria-modal', 'true');
      modal.setAttribute('aria-labelledby', 'appConfirmTitle');
      modal.setAttribute('aria-describedby', 'appConfirmDesc');
      modal.innerHTML = `
        <div class="app-modal__backdrop" data-confirm-close></div>
        <div class="app-modal__panel app-confirm__panel" role="document">
          <div class="app-confirm__icon" id="appConfirmIcon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/>
            </svg>
          </div>
          <h2 id="appConfirmTitle" class="app-confirm__title">确认操作</h2>
          <p id="appConfirmDesc" class="app-confirm__desc"></p>
          <div class="app-confirm__actions">
            <button type="button" class="btn-modal-cancel" id="appConfirmCancel" data-confirm-close>取消</button>
            <button type="button" class="btn-primary" id="appConfirmOk">确定</button>
          </div>
        </div>`;
      document.body.appendChild(modal);
    }
    if (!bound) {
      bound = true;
      AppModal.bind(modal, { closeAttr: 'data-confirm-close' });
      modal.querySelector('#appConfirmOk')?.addEventListener('click', () => finish(true));
    }
    return modal;
  }

  function finish(ok) {
    const fn = resolveFn;
    resolveFn = null;
    const modal = document.getElementById('appConfirmModal');
    if (modal && AppModal.isOpen(modal)) AppModal.close(modal);
    fn?.(!!ok);
  }

  function confirm(opts = {}) {
    const {
      title = '确认操作',
      message = '',
      confirmText = '确定',
      cancelText = '取消',
      danger = false,
    } = typeof opts === 'string' ? { message: opts } : opts;

    return new Promise((resolve) => {
      if (resolveFn) finish(false);
      resolveFn = resolve;
      const modal = ensureModal();
      const titleEl = modal.querySelector('#appConfirmTitle');
      const descEl = modal.querySelector('#appConfirmDesc');
      const okBtn = modal.querySelector('#appConfirmOk');
      const cancelBtn = modal.querySelector('#appConfirmCancel');
      const icon = modal.querySelector('#appConfirmIcon');
      if (titleEl) titleEl.textContent = title;
      if (descEl) {
        descEl.textContent = message;
        descEl.hidden = !message;
      }
      if (okBtn) {
        okBtn.textContent = confirmText;
        okBtn.className = danger ? 'btn-modal-danger app-confirm__ok' : 'btn-primary app-confirm__ok';
      }
      if (cancelBtn) cancelBtn.textContent = cancelText;
      modal.classList.toggle('app-confirm--danger', !!danger);
      icon?.classList.toggle('app-confirm__icon--danger', !!danger);
      AppModal.open(modal, {
        focus: false,
        onClose: () => {
          if (!resolveFn) return;
          const fn = resolveFn;
          resolveFn = null;
          fn(false);
        },
      });
      requestAnimationFrame(() => {
        (danger ? cancelBtn : okBtn)?.focus?.({ preventScroll: true });
      });
    });
  }

  return { confirm };
})();

window.AppModal = AppModal;
window.AppConfirm = AppConfirm;
window.appConfirm = (opts) => AppConfirm.confirm(opts);
