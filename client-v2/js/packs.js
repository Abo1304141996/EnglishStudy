/**
 * packs.js — 学习包列表页（首页）
 */
const PacksPage = (() => {
  const COVER_ICONS = {
    '影视剧': 'fa-film',
    '日常生活': 'fa-coffee',
    '商务英语': 'fa-briefcase',
    '旅游出行': 'fa-plane',
    '考试词汇': 'fa-graduation-cap',
  };

  let allPacks = [];
  let activeTag = '全部';

  async function load() {
    try {
      allPacks = await Api.getPacks();
      renderTagFilters();
      renderPacks();
    } catch (err) {
      console.error('[Packs] Failed to load:', err);
      document.getElementById('pack-grid').innerHTML =
        '<p class="text-center text-red-400 py-16 col-span-full">加载失败，请确认后端服务已启动</p>';
    }
  }

  function renderTagFilters() {
    const container = document.getElementById('tag-filters');
    const tags = ['全部', ...new Set(allPacks.map(p => p.tag).filter(Boolean))];
    container.innerHTML = tags.map(tag =>
      `<button class="tag-btn ${tag === activeTag ? 'active' : ''}" data-tag="${escapeHtml(tag)}">${escapeHtml(tag)}</button>`
    ).join('');

    container.querySelectorAll('.tag-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        activeTag = btn.dataset.tag;
        container.querySelectorAll('.tag-btn').forEach(b => b.classList.toggle('active', b.dataset.tag === activeTag));
        renderPacks();
      });
    });
  }

  function renderPacks() {
    const grid = document.getElementById('pack-grid');
    const filtered = activeTag === '全部' ? allPacks : allPacks.filter(p => p.tag === activeTag);

    if (filtered.length === 0) {
      grid.innerHTML = `
        <div class="text-center text-gray-400 py-16 col-span-full">
          <i class="fas fa-folder-open text-4xl mb-3"></i>
          <p>暂无学习包，点击右上角"新增积累"开始</p>
        </div>`;
      return;
    }

    grid.innerHTML = filtered.map((pack, idx) => {
      const icon = COVER_ICONS[pack.tag] || 'fa-book';
      const colorIdx = idx % 6;
      const tagColors = {
        '影视剧': 'bg-blue-100 text-blue-700',
        '日常生活': 'bg-green-100 text-green-700',
        '商务英语': 'bg-purple-100 text-purple-700',
        '旅游出行': 'bg-orange-100 text-orange-700',
        '考试词汇': 'bg-red-100 text-red-700',
      };
      const tagClass = tagColors[pack.tag] || 'bg-gray-100 text-gray-700';

      return `
        <div class="bg-white rounded-xl shadow-sm overflow-hidden hover:shadow-md transition-shadow border border-gray-100 cursor-pointer pack-card"
             data-pack-id="${escapeHtml(pack.id)}">
          <div class="h-40 pack-cover pack-cover-${colorIdx}">
            <i class="fas ${icon}"></i>
          </div>
          <div class="p-5">
            <div class="flex justify-between items-start mb-3 gap-2">
              <h4 class="text-xl font-bold break-words flex-1">${escapeHtml(pack.name)}</h4>
              <span class="px-2 py-1 ${tagClass} text-xs rounded-full whitespace-nowrap">${escapeHtml(pack.tag || '日常生活')}</span>
            </div>
            <p class="text-gray-600 text-sm mb-4">包含 ${pack.total_cards} 张闪卡，${pack.scene_count} 个学习场景</p>
            <div class="flex items-center justify-between">
              <div class="text-sm text-gray-500">
                <i class="fas fa-layer-group mr-1"></i>${pack.scene_count} 个场景
              </div>
              <button class="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors view-pack-btn">
                查看详情
              </button>
            </div>
          </div>
        </div>`;
    }).join('');

    grid.querySelectorAll('.pack-card').forEach(card => {
      card.addEventListener('click', () => {
        const packId = card.dataset.packId;
        const pack = allPacks.find(p => p.id === packId);
        if (pack) ScenesPage.open(pack);
      });
    });
  }

  function getPackById(id) {
    return allPacks.find(p => p.id === id);
  }

  function escapeHtml(str) {
    return (str || '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
  }

  return { load, getPackById };
})();
