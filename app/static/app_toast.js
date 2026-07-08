/** 全局居中轻提示 */
(function () {
  const ICON_SUCCESS = `<svg class="app-toast__icon" viewBox="0 0 20 20" fill="none" aria-hidden="true">
    <path d="M6.5 10.2 8.8 12.5 13.5 7.8" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>`;

  const ICON_ERROR = `<svg class="app-toast__icon" viewBox="0 0 20 20" fill="none" aria-hidden="true">
    <path d="M7.2 7.2 12.8 12.8M12.8 7.2 7.2 12.8" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"/>
  </svg>`;

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function renderToast(el, msg, ok) {
    el.classList.remove('app-toast--success', 'app-toast--error', 'is-visible');
    el.classList.add(ok ? 'app-toast--success' : 'app-toast--error');
    el.innerHTML = `
      <div class="app-toast__card">
        <span class="app-toast__icon-wrap">${ok ? ICON_SUCCESS : ICON_ERROR}</span>
        <span class="app-toast__message">${escapeHtml(msg)}</span>
      </div>
    `;
  }

  function showAppToast(msg, ok = true, duration = 2200) {
    const el = document.getElementById('toast') || document.getElementById('dailyToast');
    if (!el) return;

    renderToast(el, msg, ok);
    el.classList.remove('hidden');
    clearTimeout(showAppToast._hideTimer);
    clearTimeout(showAppToast._removeTimer);

    requestAnimationFrame(() => {
      requestAnimationFrame(() => el.classList.add('is-visible'));
    });

    showAppToast._hideTimer = setTimeout(() => {
      el.classList.remove('is-visible');
      showAppToast._removeTimer = setTimeout(() => el.classList.add('hidden'), 300);
    }, duration);
  }

  window.showAppToast = showAppToast;
})();
