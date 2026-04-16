/**
 * scenes.js — 场景列表页
 */
const ScenesPage = (() => {
  let currentPack = null;

  function open(pack) {
    currentPack = pack;
    document.getElementById('current-pack-name').textContent = pack.name;
    document.getElementById('pack-progress-info').innerHTML =
      `<i class="fas fa-layer-group text-primary"></i> 共 ${pack.scene_count} 个场景 · ${pack.total_cards} 张闪卡`;

    renderScenes(pack.scenes);
    Router.showPage('scene-list');
  }

  function renderScenes(scenes) {
    const grid = document.getElementById('scene-grid');
    grid.innerHTML = scenes.map(scene => `
      <div class="scene-card bg-white rounded-xl shadow-sm overflow-hidden hover:shadow-md border border-gray-100 cursor-pointer"
           data-scene-name="${scene.name}">
        <div class="p-5">
          <h4 class="text-lg font-bold mb-3">${scene.name}</h4>
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
      card.addEventListener('click', () => {
        const sceneName = card.dataset.sceneName;
        FlashcardPage.open(currentPack.name, sceneName);
      });
    });
  }

  function getCurrentPack() {
    return currentPack;
  }

  return { open, getCurrentPack };
})();
