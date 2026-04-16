/**
 * history.js — 我的学习页
 */
const HistoryPage = (() => {

  async function load() {
    try {
      const stats = await Api.getStats();
      document.getElementById('stat-total-cards').textContent = stats.total || 0;
      document.getElementById('stat-known').textContent = stats.know || 0;
      const accuracy = stats.accuracy != null ? stats.accuracy : 0;
      document.getElementById('stat-accuracy').textContent = accuracy + '%';

      const records = await Api.getStudyRecords(30);
      renderHistory(records);
    } catch (err) {
      console.error('[History] Failed to load:', err);
      document.getElementById('learning-history-list').innerHTML =
        '<p class="p-6 text-red-400 text-center">加载失败，请确认后端已启动</p>';
    }
  }

  function renderHistory(records) {
    const list = document.getElementById('learning-history-list');

    if (!records || records.length === 0) {
      list.innerHTML = '<p class="p-6 text-gray-400 text-center">暂无学习记录，快去学习吧！</p>';
      return;
    }

    // 按日期分组（使用 studied_at 字段）
    const grouped = {};
    records.forEach(r => {
      const raw = r.studied_at || r.created_at;
      let date = '未知日期';
      if (raw) {
        const d = new Date(raw);
        if (!isNaN(d.getTime())) {
          date = d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' });
        }
      }
      if (!grouped[date]) grouped[date] = [];
      grouped[date].push(r);
    });

    // 收集每条记录对应的 card_id，后续可用于跳转
    list.innerHTML = Object.entries(grouped).map(([date, items]) => {
      const know = items.filter(i => i.rating === 'know').length;
      const fuzzy = items.filter(i => i.rating === 'fuzzy').length;
      const unknown = items.filter(i => i.rating === 'unknown').length;
      const total = items.length;
      const pct = total > 0 ? Math.round((know / total) * 100) : 0;

      return `
        <div class="p-6 hover:bg-gray-50 transition-colors cursor-pointer history-item" data-date="${date}">
          <div class="flex flex-col md:flex-row md:items-center justify-between">
            <div class="mb-4 md:mb-0">
              <h4 class="font-bold text-lg">${date}</h4>
              <p class="text-gray-500 mt-1">共学习 ${total} 张卡片</p>
            </div>
            <div class="flex items-center gap-6">
              <div class="text-center">
                <p class="text-sm text-gray-500">认识</p>
                <p class="font-bold text-green-600">${know}</p>
              </div>
              <div class="text-center">
                <p class="text-sm text-gray-500">模糊</p>
                <p class="font-bold text-yellow-600">${fuzzy}</p>
              </div>
              <div class="text-center">
                <p class="text-sm text-gray-500">不认识</p>
                <p class="font-bold text-red-600">${unknown}</p>
              </div>
              <div class="w-24">
                <p class="text-sm text-gray-500 mb-1">正确率</p>
                <div class="w-full bg-gray-200 rounded-full h-2">
                  <div class="bg-green-500 h-2 rounded-full" style="width:${pct}%"></div>
                </div>
                <p class="text-xs text-right mt-1">${pct}%</p>
              </div>
              <button class="px-3 py-1.5 bg-primary/10 text-primary rounded-lg hover:bg-primary/20 transition-colors text-sm">
                <i class="fas fa-redo mr-1"></i>继续学习
              </button>
            </div>
          </div>
        </div>`;
    }).join('');

    // 点击历史卡片 → 回到首页学习包
    list.querySelectorAll('.history-item').forEach(item => {
      item.addEventListener('click', () => {
        Router.showPage('pack-list');
        PacksPage.load();
      });
    });
  }

  return { load };
})();

/* ============================================
   应用启动入口
   ============================================ */
document.addEventListener('DOMContentLoaded', () => {
  Router.init();
  FlashcardPage.init();
  PacksPage.load();
});
