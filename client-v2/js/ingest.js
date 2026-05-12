/**
 * ingest.js — 上传积累 → AI 解析卡片 → 审阅/编辑 → 入库 完整向导
 *
 * 步骤：
 *   1. 粘贴文本
 *   2. AI 解析中（loading）
 *   3. 审阅 / 单张编辑 / 让 AI 重写 / 删除
 *   4. 选择目标学习包 + 场景（可新建）
 */
const IngestWizard = (() => {
  let state = null;

  function open() {
    state = {
      rawText: '',
      cards: [],          // [{front, back, included: true, refining: false}]
      packs: [],
      step: 1,
    };
    renderModal();
  }

  let modalCtx = null;

  function renderModal() {
    if (modalCtx) modalCtx.close();
    modalCtx = Modal.open({
      title: '新增积累 · AI 智能拆卡',
      size: 'lg',
      body: buildBody(),
      footer: buildFooter(),
      onClose: () => { modalCtx = null; },
    });
  }

  function buildBody() {
    if (state.step === 1) return stepInputBody();
    if (state.step === 2) return stepLoadingBody();
    if (state.step === 3) return stepReviewBody();
    if (state.step === 4) return stepTargetBody();
    return '';
  }

  function buildFooter() {
    const wrap = document.createElement('div');
    wrap.style.display = 'contents';
    wrap.appendChild(buildStepIndicator());
    wrap.appendChild(buildButtons());
    return wrap;
  }

  function buildStepIndicator() {
    const el = document.createElement('div');
    el.className = 'wizard-steps mr-auto';
    const steps = ['粘贴文本', 'AI 解析', '审阅卡片', '保存到'];
    el.innerHTML = steps.map((s, i) => {
      const idx = i + 1;
      const cls = idx < state.step ? 'done' : idx === state.step ? 'active' : '';
      const icon = idx < state.step ? 'fa-check-circle' : 'fa-circle';
      return `<span class="step ${cls}"><i class="fas ${icon}"></i>${s}</span>`;
    }).join('');
    return el;
  }

  function buildButtons() {
    const wrap = document.createElement('div');
    wrap.style.display = 'flex';
    wrap.style.gap = '0.5rem';

    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'px-4 py-2 bg-white border border-gray-300 text-gray-600 rounded-lg hover:bg-gray-50';
    cancelBtn.textContent = state.step === 4 ? '上一步' : '取消';
    cancelBtn.addEventListener('click', () => {
      if (state.step === 4) { state.step = 3; renderModal(); }
      else if (state.step === 3) { state.step = 1; renderModal(); }
      else { modalCtx && modalCtx.close(); }
    });

    const okBtn = document.createElement('button');
    okBtn.className = 'px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90';
    if (state.step === 1) okBtn.textContent = 'AI 解析';
    else if (state.step === 2) { okBtn.textContent = '解析中...'; okBtn.disabled = true; okBtn.classList.add('opacity-60', 'cursor-not-allowed'); }
    else if (state.step === 3) okBtn.textContent = '下一步：选择保存位置';
    else okBtn.textContent = '保存到学习包';

    okBtn.addEventListener('click', onPrimaryClick);

    wrap.appendChild(cancelBtn);
    wrap.appendChild(okBtn);
    return wrap;
  }

  // ---------- Step 1: 输入 ----------
  function stepInputBody() {
    const wrap = document.createElement('div');
    wrap.innerHTML = `
      <p class="text-sm text-gray-600 mb-3">
        粘贴你最近积累的英语句子（可一行一句、或带中文翻译、或一整段）。AI 会基于"情境化记忆"原则拆成抽认卡。
      </p>
      <textarea id="ingest-raw" class="form-textarea" placeholder="例如：&#10;My life couldn't get any fucking worse.&#10;just lean all in and go for it.&#10;I am walking outside."></textarea>
      <p class="text-xs text-gray-400 mt-2">提示：内容越具体（含语境/情绪线索）AI 生成的卡片正面越生动。</p>
    `;
    setTimeout(() => {
      const t = wrap.querySelector('#ingest-raw');
      if (t) { t.value = state.rawText || ''; t.focus(); }
    }, 50);
    return wrap;
  }

  // ---------- Step 2: loading ----------
  function stepLoadingBody() {
    const wrap = document.createElement('div');
    wrap.innerHTML = `
      <div class="py-12 text-center text-gray-500">
        <i class="fas fa-spinner fa-spin text-4xl text-primary mb-4"></i>
        <p>AI 正在拆解你的积累，请稍候...</p>
        <p class="text-xs text-gray-400 mt-2">通常需要 5~15 秒</p>
      </div>`;
    return wrap;
  }

  // ---------- Step 3: 审阅 ----------
  function stepReviewBody() {
    const wrap = document.createElement('div');
    if (!state.cards.length) {
      wrap.innerHTML = `
        <div class="py-10 text-center text-gray-500">
          <i class="fas fa-inbox text-3xl mb-3"></i>
          <p>未解析到任何卡片，请返回修改输入。</p>
        </div>`;
      return wrap;
    }

    const tip = document.createElement('p');
    tip.className = 'text-sm text-gray-600 mb-3';
    tip.innerHTML = `共解析 <b>${state.cards.length}</b> 张卡片，请审阅。可对单卡 <i class="fas fa-pen mx-1"></i>编辑、<i class="fas fa-magic mx-1"></i>让 AI 重写，或取消勾选不导入。`;
    wrap.appendChild(tip);

    state.cards.forEach((card, i) => {
      const el = document.createElement('div');
      el.className = `candidate-card ${card.included ? 'selected' : 'dimmed'}`;
      el.innerHTML = `
        <div class="flex items-start gap-2">
          <input type="checkbox" class="mt-1.5" ${card.included ? 'checked' : ''} data-idx="${i}" data-act="toggle">
          <div class="flex-1 min-w-0">
            <div class="candidate-front">${escapeHtml(card.front)}</div>
            <div class="candidate-back">${escapeHtml(card.back)}</div>
            <div class="candidate-actions">
              <button data-idx="${i}" data-act="edit"><i class="fas fa-pen mr-1"></i>编辑</button>
              <button data-idx="${i}" data-act="refine"><i class="fas fa-magic mr-1"></i>让 AI 重写</button>
              <button data-idx="${i}" data-act="remove" class="danger"><i class="fas fa-times mr-1"></i>删除</button>
            </div>
          </div>
        </div>`;
      wrap.appendChild(el);
    });

    wrap.addEventListener('click', onReviewClick);
    wrap.addEventListener('change', onReviewChange);
    return wrap;
  }

  function onReviewChange(e) {
    const t = e.target;
    if (t.dataset && t.dataset.act === 'toggle') {
      const idx = +t.dataset.idx;
      state.cards[idx].included = t.checked;
      renderModal();
    }
  }
  function onReviewClick(e) {
    const btn = e.target.closest('button[data-act]');
    if (!btn) return;
    const idx = +btn.dataset.idx;
    const act = btn.dataset.act;
    if (act === 'edit') return openEditDialog(idx);
    if (act === 'refine') return openRefineDialog(idx);
    if (act === 'remove') {
      state.cards.splice(idx, 1);
      renderModal();
    }
  }

  function openEditDialog(idx) {
    const card = state.cards[idx];
    const wrap = document.createElement('div');
    wrap.innerHTML = `
      <label class="form-label">正面（中文情境提示）</label>
      <textarea class="form-textarea" id="edit-front" style="min-height:90px;">${escapeHtml(card.front)}</textarea>
      <label class="form-label mt-3">背面（英文原句）</label>
      <textarea class="form-textarea" id="edit-back" style="min-height:60px;">${escapeHtml(card.back)}</textarea>
    `;
    const ok = document.createElement('button');
    ok.className = 'px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90';
    ok.textContent = '保存';
    const cancel = document.createElement('button');
    cancel.className = 'px-4 py-2 bg-white border border-gray-300 text-gray-600 rounded-lg hover:bg-gray-50';
    cancel.textContent = '取消';
    const footer = document.createElement('div');
    footer.style.display = 'contents';
    footer.appendChild(cancel); footer.appendChild(ok);

    const m = Modal.open({ title: '手动编辑卡片', body: wrap, footer });
    cancel.addEventListener('click', () => m.close());
    ok.addEventListener('click', () => {
      const f = wrap.querySelector('#edit-front').value.trim();
      const b = wrap.querySelector('#edit-back').value.trim();
      if (!f || !b) { Modal.toast('正反面不能为空', 'warn'); return; }
      state.cards[idx].front = f;
      state.cards[idx].back = b;
      m.close();
      renderModal();
    });
  }

  function openRefineDialog(idx) {
    const card = state.cards[idx];
    const wrap = document.createElement('div');
    wrap.innerHTML = `
      <div class="text-sm text-gray-600 mb-3">
        <p class="mb-1"><b>当前正面：</b>${escapeHtml(card.front)}</p>
        <p><b>当前背面：</b>${escapeHtml(card.back)}</p>
      </div>
      <label class="form-label">告诉 AI 怎么改：</label>
      <textarea class="form-textarea" id="refine-instr" placeholder="例如：场景描述更聚焦在和朋友吐槽时；中文翻译再口语化一些"></textarea>
    `;
    const ok = document.createElement('button');
    ok.className = 'px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90';
    ok.textContent = '让 AI 重写';
    const cancel = document.createElement('button');
    cancel.className = 'px-4 py-2 bg-white border border-gray-300 text-gray-600 rounded-lg hover:bg-gray-50';
    cancel.textContent = '取消';
    const footer = document.createElement('div');
    footer.style.display = 'contents';
    footer.appendChild(cancel); footer.appendChild(ok);

    const m = Modal.open({ title: 'AI 重写卡片', body: wrap, footer });
    cancel.addEventListener('click', () => m.close());
    ok.addEventListener('click', async () => {
      const instr = wrap.querySelector('#refine-instr').value.trim();
      if (!instr) { Modal.toast('请告诉 AI 修改方向', 'warn'); return; }
      ok.disabled = true; ok.textContent = '生成中...';
      try {
        const newCard = await Api.aiRefineCard(card.front, card.back, instr, state.rawText);
        state.cards[idx].front = newCard.front;
        state.cards[idx].back = newCard.back;
        m.close();
        renderModal();
      } catch (err) {
        Modal.toast('AI 重写失败：' + err.message, 'error', 3500);
        ok.disabled = false; ok.textContent = '让 AI 重写';
      }
    });
  }

  // ---------- Step 4: 选择目标 ----------
  function stepTargetBody() {
    const wrap = document.createElement('div');
    const includedCount = state.cards.filter(c => c.included).length;
    wrap.innerHTML = `
      <p class="text-sm text-gray-600 mb-4">将保存 <b>${includedCount}</b> 张卡片到：</p>

      <label class="form-label">学习包</label>
      <div class="flex gap-2 items-center mb-3">
        <select id="ingest-pack" class="form-select" style="flex:1;">
          <option value="__new__">+ 新建学习包</option>
          ${state.packs.map(p => `<option value="${p.id}">${escapeHtml(p.name)}（${p.total_cards} 卡）</option>`).join('')}
        </select>
      </div>
      <div id="ingest-new-pack-fields" class="mb-3 hidden">
        <input type="text" id="ingest-new-pack-name" class="form-input" placeholder="新学习包名称（如：Shameless-S03）">
      </div>

      <label class="form-label">场景</label>
      <select id="ingest-scene" class="form-select mb-2">
        <option value="__new__">+ 新建场景</option>
      </select>
      <input type="text" id="ingest-new-scene-name" class="form-input hidden" placeholder="新场景名称（如：第3话 · 酒吧吐槽）">
    `;

    setTimeout(() => bindTargetForm(wrap), 30);
    return wrap;
  }

  function bindTargetForm(wrap) {
    const packSel = wrap.querySelector('#ingest-pack');
    const newPackFields = wrap.querySelector('#ingest-new-pack-fields');
    const sceneSel = wrap.querySelector('#ingest-scene');
    const newSceneInput = wrap.querySelector('#ingest-new-scene-name');

    function refreshScenes() {
      const v = packSel.value;
      sceneSel.innerHTML = '<option value="__new__">+ 新建场景</option>';
      if (v && v !== '__new__') {
        const pack = state.packs.find(p => p.id === v);
        if (pack && pack.scenes) {
          pack.scenes.forEach(s => {
            const o = document.createElement('option');
            o.value = s.id; o.textContent = `${s.name}（${s.card_count} 卡）`;
            sceneSel.appendChild(o);
          });
        }
      }
    }
    function refreshNewSceneVisibility() {
      const isNew = sceneSel.value === '__new__';
      newSceneInput.classList.toggle('hidden', !isNew);
    }
    function refreshNewPackVisibility() {
      const isNew = packSel.value === '__new__';
      newPackFields.classList.toggle('hidden', !isNew);
      refreshScenes();
      // 新建 pack 下，强制走"新建场景"
      if (isNew) {
        sceneSel.innerHTML = '<option value="__new__">+ 新建场景</option>';
        sceneSel.disabled = true;
      } else {
        sceneSel.disabled = false;
      }
      refreshNewSceneVisibility();
    }
    packSel.addEventListener('change', refreshNewPackVisibility);
    sceneSel.addEventListener('change', refreshNewSceneVisibility);
    refreshNewPackVisibility();
  }

  // ---------- 主按钮 ----------
  async function onPrimaryClick() {
    if (state.step === 1) {
      const t = (document.getElementById('ingest-raw') || {}).value || '';
      if (!t.trim()) { Modal.toast('请粘贴一些英语积累', 'warn'); return; }
      state.rawText = t.trim();
      state.step = 2;
      renderModal();
      try {
        const cards = await Api.aiParseCards(state.rawText);
        state.cards = cards.map(c => ({ ...c, included: true }));
        state.step = 3;
        renderModal();
      } catch (err) {
        Modal.toast('AI 解析失败：' + err.message, 'error', 4000);
        state.step = 1;
        renderModal();
      }
    } else if (state.step === 3) {
      const included = state.cards.filter(c => c.included);
      if (!included.length) { Modal.toast('至少保留一张卡片', 'warn'); return; }
      // 加载学习包列表
      try {
        state.packs = await Api.getPacks();
      } catch (err) {
        Modal.toast('加载学习包失败：' + err.message, 'error');
        return;
      }
      state.step = 4;
      renderModal();
    } else if (state.step === 4) {
      await commitAll();
    }
  }

  async function commitAll() {
    const root = modalCtx.body;
    const packSel = root.querySelector('#ingest-pack');
    const sceneSel = root.querySelector('#ingest-scene');
    const newPackName = (root.querySelector('#ingest-new-pack-name') || {}).value || '';
    const newSceneName = (root.querySelector('#ingest-new-scene-name') || {}).value || '';

    const payload = {
      cards: state.cards.filter(c => c.included).map(c => ({ front: c.front, back: c.back })),
    };
    if (packSel.value === '__new__') {
      if (!newPackName.trim()) { Modal.toast('请填写新学习包名称', 'warn'); return; }
      payload.pack_name = newPackName.trim();
    } else {
      payload.pack_id = packSel.value;
    }
    if (packSel.value === '__new__' || sceneSel.value === '__new__') {
      if (!newSceneName.trim()) { Modal.toast('请填写新场景名称', 'warn'); return; }
      payload.scene_name = newSceneName.trim();
    } else {
      payload.scene_id = sceneSel.value;
    }

    try {
      const res = await Api.commitCards(payload);
      Modal.toast(`已保存 ${res.added} 张卡片 🎉`, 'success', 2500);
      modalCtx.close();
      // 刷新首页
      if (typeof PacksPage !== 'undefined') PacksPage.load();
    } catch (err) {
      Modal.toast('保存失败：' + err.message, 'error', 3500);
    }
  }

  function escapeHtml(str) {
    return (str || '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
  }

  return { open };
})();
