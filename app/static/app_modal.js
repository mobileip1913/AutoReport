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

window.AppModal = AppModal;
