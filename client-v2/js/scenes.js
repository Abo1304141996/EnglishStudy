/**
 * scenes.js — 场景列表页（含场景/学习包 管理）
 */
const ScenesPage = (() => {
  let currentPack = null;
  let inited = false;

  function open(pack) {
    currentPack = pack;
    document.getElementById('current-pack-name').textContent = pack.name;
    document.getElementById('pack-progress-info').innerHTML =
      `<i class="fas fa-layer-group text-primary"></i> 共 ${pack.scene_count} 个场景 · ${pack.total_cards} 张闪卡`;

    renderScenes(pack.scenes || []);
    Router.showPage('scene-list');
    if (!inited) bindHeaderActions();
  }

  function renderScenes(scenes) {
    const grid = document.getElementById('scene-grid');
    if (!scenes.length) {
      grid.innerHTML = `
        <div class="text-center text-gray-400 py-12 col-span-full">
          <i class="fas fa-folder-open text-3xl mb-3"></i>
          <p>该学习包下还没有场景，点击右上"新建场景"或"新增积累"添加</p>
        </div>`;
      return;
    }
    grid.innerHTML = scenes.map(scene => `
      <div class="scene-card bg-white rounded-xl shadow-sm overflow-hidden hover:shadow-md border border-gray-100"
           data-scene-id="${escapeHtml(scene.id)}" data-scene-name="${escapeHtml(scene.name)}">
        <div class="p-5">
          <div class="flex items-start justify-between gap-2 mb-3">
            <h4 class="text-lg font-bold break-words flex-1">${escapeHtml(scene.name)}</h4>
            <div class="relative scene-menu-wrap">
              <button class="scene-menu-btn text-gray-400 hover:text-gray-700 p-1" aria-label="更多">
                <i class="fas fa-ellipsis-v"></i>
              </button>
            </div>
          </div>
          <div class="flex items-center justify-between">
            <div class="text-sm text-gray-500">
              <i class="fas fa-clone mr-1"></i>${scene.card_count} 张闪卡
            </div>
            <button class="px-4 py-2 bg-secondary text-white rounded-lg hover:bg-secondary/90 transition-colors start-learn-btn text-sm">
              开始学习
            </button>
          </div>
        </div>
      </div>
    `).join('');

    grid.querySelectorAll('.scene-card').forEach(card => {
      const sceneName = card.dataset.sceneName;
      const sceneId = card.dataset.sceneId;
      // 启动学习
      card.querySelector('.start-learn-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        FlashcardPage.open(currentPack.name, sceneName);
      });
      // 整卡点击也启动学习
      card.addEventListener('click', (e) => {
        if (e.target.closest('.scene-menu-btn') || e.target.closest('.scene-menu-popover')) return;
        FlashcardPage.open(currentPack.name, sceneName);
      });
      // 三点菜单
      card.querySelector('.scene-menu-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        showSceneMenu(card, sceneId, sceneName);
      });
    });
  }

  function showSceneMenu(anchor, sceneId, sceneName) {
    // 简单：弹一个 Modal 选择操作
    const wrap = document.createElement('div');
    wrap.innerHTML = `
      <div class="space-y-2">
        <button class="w-full text-left px-3 py-2 hover:bg-gray-50 rounded" data-act="rename">
          <i class="fas fa-pen mr-2 text-gray-500"></i>重命名场景
        </button>
        <button class="w-full text-left px-3 py-2 hover:bg-red-50 text-red-600 rounded" data-act="delete">
          <i class="fas fa-trash mr-2"></i>删除场景
        </button>
      </div>`;
    const m = Modal.open({ title: `场景：${sceneName}`, body: wrap, footer: '' });
    wrap.addEventListener('click', async (e) => {
      const btn = e.target.closest('button[data-act]');
      if (!btn) return;
      const act = btn.dataset.act;
      m.close();
      if (act === 'rename') {
        const newName = await Modal.prompt({ title: '重命名场景', defaultValue: sceneName });
        if (!newName || newName === sceneName) return;
        try {
          await Api.updateScene(currentPack.id, sceneId, newName);
          Modal.toast('已重命名', 'success');
          await reloadCurrentPack();
        } catch (err) { Modal.toast(err.message, 'error', 3000); }
      } else if (act === 'delete') {
        const ok = await Modal.confirm({
          title: '删除场景',
          message: `确定删除场景"${sceneName}"？该场景下的所有卡片会一同删除。`,
          okText: '确认删除', danger: true,
        });
        if (!ok) return;
        try {
          await Api.deleteScene(currentPack.id, sceneId, true);
          Modal.toast('已删除', 'success');
          await reloadCurrentPack();
        } catch (err) { Modal.toast(err.message, 'error', 3000); }
      }
    });
  }

  async function reloadCurrentPack() {
    await PacksPage.load();
    const fresh = PacksPage.getPackById(currentPack.id);
    if (fresh) open(fresh);
    else Router.showPage('pack-list');
  }

  function bindHeaderActions() {
    inited = true;
    document.getElementById('new-scene-btn').addEventListener('click', async () => {
      if (!currentPack) return;
      const name = await Modal.prompt({ title: '新建场景', label: '场景名称', placeholder: '如：第3话 · 酒吧吐槽' });
      if (!name) return;
      try {
        await Api.createScene(currentPack.id, name);
        Modal.toast('已创建场景', 'success');
        await reloadCurrentPack();
      } catch (err) { Modal.toast(err.message, 'error', 3000); }
    });

    document.getElementById('rename-pack-btn').addEventListener('click', async () => {
      if (!currentPack) return;
      const name = await Modal.prompt({ title: '重命名学习包', defaultValue: currentPack.name });
      if (!name || name === currentPack.name) return;
      try {
        await Api.updatePack(currentPack.id, { name });
        Modal.toast('已重命名', 'success');
        await reloadCurrentPack();
      } catch (err) { Modal.toast(err.message, 'error', 3000); }
    });

    document.getElementById('delete-pack-btn').addEventListener('click', async () => {
      if (!currentPack) return;
      const hasContent = (currentPack.scene_count || 0) > 0 || (currentPack.total_cards || 0) > 0;
      const msg = hasContent
        ? `学习包"<b>${currentPack.name}</b>"包含 <b>${currentPack.scene_count}</b> 个场景、<b>${currentPack.total_cards}</b> 张卡片，删除后<span class="text-red-600">不可恢复</span>！`
        : `确定删除空学习包"<b>${currentPack.name}</b>"？`;
      const ok = await Modal.confirmType({
        title: '删除学习包',
        message: msg,
        requiredText: currentPack.name,
        placeholder: '在此输入学习包名称以确认',
        okText: '确认删除',
      });
      if (!ok) return;
      try {
        await Api.deletePack(currentPack.id, true);
        Modal.toast('已删除学习包', 'success');
        Router.showPage('pack-list');
        await PacksPage.load();
      } catch (err) { Modal.toast(err.message, 'error', 3000); }
    });
  }

  function getCurrentPack() {
    return currentPack;
  }

  function escapeHtml(str) {
    return (str || '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
  }

  return { open, getCurrentPack };
})();
