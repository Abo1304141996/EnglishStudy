/**
 * modal.js — 通用 Modal 工具
 *
 * Modal.open({ title, body, footer, size, onClose }) -> { close, setBody, setFooter, root }
 * Modal.confirm({ title, message, okText, danger }) -> Promise<boolean>
 * Modal.prompt({ title, label, defaultValue, placeholder }) -> Promise<string|null>
 */
const Modal = (() => {
  function open({ title = '', body = '', footer = '', size = '', onClose } = {}) {
    const root = document.getElementById('modal-root');
    const wrapper = document.createElement('div');
    wrapper.className = 'modal-mask';
    wrapper.innerHTML = `
      <div class="modal-panel ${size}">
        <div class="modal-header">
          <span class="modal-title"></span>
          <span class="modal-close" role="button" aria-label="关闭"><i class="fas fa-times"></i></span>
        </div>
        <div class="modal-body"></div>
        <div class="modal-footer"></div>
      </div>`;
    root.appendChild(wrapper);

    const titleEl = wrapper.querySelector('.modal-title');
    const bodyEl = wrapper.querySelector('.modal-body');
    const footerEl = wrapper.querySelector('.modal-footer');
    const closeEl = wrapper.querySelector('.modal-close');

    titleEl.textContent = title;
    setBody(body);
    setFooter(footer);

    function setBody(content) {
      if (typeof content === 'string') bodyEl.innerHTML = content;
      else if (content instanceof Node) { bodyEl.innerHTML = ''; bodyEl.appendChild(content); }
    }
    function setFooter(content) {
      if (typeof content === 'string') footerEl.innerHTML = content;
      else if (content instanceof Node) { footerEl.innerHTML = ''; footerEl.appendChild(content); }
      footerEl.style.display = footerEl.children.length || footerEl.innerHTML.trim() ? '' : 'none';
    }
    function close() {
      if (!wrapper.parentNode) return;
      wrapper.remove();
      if (typeof onClose === 'function') onClose();
    }

    closeEl.addEventListener('click', close);
    wrapper.addEventListener('click', (e) => { if (e.target === wrapper) close(); });

    return { close, setBody, setFooter, root: wrapper, body: bodyEl, footer: footerEl };
  }

  function confirm({ title = '请确认', message = '', okText = '确认', cancelText = '取消', danger = false } = {}) {
    return new Promise((resolve) => {
      let settled = false;
      const done = (v) => { if (!settled) { settled = true; resolve(v); } };

      const okBtn = document.createElement('button');
      okBtn.className = `px-4 py-2 ${danger ? 'bg-red-500 hover:bg-red-600' : 'bg-primary hover:bg-primary/90'} text-white rounded-lg`;
      okBtn.textContent = okText;
      const cancelBtn = document.createElement('button');
      cancelBtn.className = 'px-4 py-2 bg-white border border-gray-300 text-gray-600 rounded-lg hover:bg-gray-50';
      cancelBtn.textContent = cancelText;

      const footer = document.createElement('div');
      footer.style.display = 'contents';
      footer.appendChild(cancelBtn);
      footer.appendChild(okBtn);

      const m = open({
        title,
        body: `<p class="text-gray-700">${message}</p>`,
        footer,
        onClose: () => done(false),
      });
      okBtn.addEventListener('click', () => { done(true); m.close(); });
      cancelBtn.addEventListener('click', () => { done(false); m.close(); });
    });
  }

  function prompt({ title = '输入', label = '', defaultValue = '', placeholder = '', okText = '确定' } = {}) {
    return new Promise((resolve) => {
      let settled = false;
      const done = (v) => { if (!settled) { settled = true; resolve(v); } };

      const wrapper = document.createElement('div');
      wrapper.innerHTML = `
        ${label ? `<label class="form-label">${label}</label>` : ''}
        <input type="text" class="form-input" placeholder="${placeholder}" value="${(defaultValue || '').replace(/"/g, '&quot;')}">
      `;
      const input = wrapper.querySelector('input');

      const okBtn = document.createElement('button');
      okBtn.className = 'px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90';
      okBtn.textContent = okText;
      const cancelBtn = document.createElement('button');
      cancelBtn.className = 'px-4 py-2 bg-white border border-gray-300 text-gray-600 rounded-lg hover:bg-gray-50';
      cancelBtn.textContent = '取消';

      const footer = document.createElement('div');
      footer.style.display = 'contents';
      footer.appendChild(cancelBtn);
      footer.appendChild(okBtn);

      const m = open({ title, body: wrapper, footer, onClose: () => done(null) });
      setTimeout(() => input.focus(), 50);
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); okBtn.click(); }
      });
      okBtn.addEventListener('click', () => {
        const v = input.value.trim();
        if (!v) { input.focus(); return; }
        done(v);
        m.close();
      });
      cancelBtn.addEventListener('click', () => { done(null); m.close(); });
    });
  }

  /**
   * 需输入指定文本才能确认的强校验弹窗（用于危险删除等）
   * @returns Promise<boolean>
   */
  function confirmType({ title = '危险操作', message = '', requiredText = '', placeholder = '', okText = '确认删除' } = {}) {
    return new Promise((resolve) => {
      let settled = false;
      const done = (v) => { if (!settled) { settled = true; resolve(v); } };

      const wrap = document.createElement('div');
      wrap.innerHTML = `
        <p class="text-gray-700 mb-3">${message}</p>
        <p class="text-sm text-gray-500 mb-2">请输入 <code class="px-1.5 py-0.5 bg-gray-100 rounded text-red-600 font-bold">${escapeHtml(requiredText)}</code> 以确认：</p>
        <input type="text" class="form-input" placeholder="${escapeHtml(placeholder || requiredText)}">
      `;
      const input = wrap.querySelector('input');

      const okBtn = document.createElement('button');
      okBtn.className = 'px-4 py-2 bg-red-500 text-white rounded-lg opacity-50 cursor-not-allowed';
      okBtn.disabled = true;
      okBtn.textContent = okText;
      const cancelBtn = document.createElement('button');
      cancelBtn.className = 'px-4 py-2 bg-white border border-gray-300 text-gray-600 rounded-lg hover:bg-gray-50';
      cancelBtn.textContent = '取消';

      const footer = document.createElement('div');
      footer.style.display = 'contents';
      footer.appendChild(cancelBtn);
      footer.appendChild(okBtn);

      const m = open({ title, body: wrap, footer, onClose: () => done(false) });
      setTimeout(() => input.focus(), 50);

      input.addEventListener('input', () => {
        const match = input.value === requiredText;
        okBtn.disabled = !match;
        okBtn.classList.toggle('opacity-50', !match);
        okBtn.classList.toggle('cursor-not-allowed', !match);
        okBtn.classList.toggle('hover:bg-red-600', match);
      });
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !okBtn.disabled) { e.preventDefault(); okBtn.click(); }
      });
      okBtn.addEventListener('click', () => {
        if (okBtn.disabled) return;
        done(true); m.close();
      });
      cancelBtn.addEventListener('click', () => { done(false); m.close(); });
    });
  }

  function escapeHtml(str) {
    return (str || '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
  }

  function toast(message, type = 'info', timeout = 2200) {
    const el = document.createElement('div');
    const colors = {
      info: 'bg-slate-800',
      success: 'bg-green-600',
      error: 'bg-red-600',
      warn: 'bg-yellow-500',
    };
    el.className = `fixed left-1/2 -translate-x-1/2 bottom-8 z-[200] px-4 py-2 rounded-lg text-white shadow-lg ${colors[type] || colors.info}`;
    el.style.maxWidth = '90vw';
    el.textContent = message;
    document.body.appendChild(el);
    setTimeout(() => { el.style.transition = 'opacity 0.3s'; el.style.opacity = '0'; }, timeout - 300);
    setTimeout(() => el.remove(), timeout);
  }

  return { open, confirm, confirmType, prompt, toast };
})();
