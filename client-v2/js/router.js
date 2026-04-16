/**
 * router.js — SPA 视图路由管理
 */
const Router = (() => {
  const pages = ['pack-list', 'scene-list', 'flashcard', 'my-learning'];
  let currentPage = 'pack-list';

  function showPage(pageId) {
    pages.forEach(id => {
      const el = document.getElementById(`page-${id}`);
      if (el) el.classList.toggle('hidden', id !== pageId);
    });
    currentPage = pageId;

    // 更新导航栏高亮
    document.querySelectorAll('.nav-link').forEach(link => {
      link.classList.toggle('active', link.dataset.page === pageId);
    });

    // 滚动到顶部
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function getCurrentPage() {
    return currentPage;
  }

  function init() {
    // 导航栏链接
    document.querySelectorAll('.nav-link').forEach(link => {
      link.addEventListener('click', () => {
        const page = link.dataset.page;
        if (page === 'pack-list') {
          showPage('pack-list');
          PacksPage.load();
        } else if (page === 'my-learning') {
          showPage('my-learning');
          HistoryPage.load();
        }
      });
    });

    // Logo 点击回首页
    document.getElementById('nav-logo').addEventListener('click', () => {
      showPage('pack-list');
      PacksPage.load();
    });

    // 返回按钮
    document.getElementById('back-to-packs').addEventListener('click', () => {
      showPage('pack-list');
    });
    document.getElementById('back-to-scenes').addEventListener('click', () => {
      showPage('scene-list');
    });
  }

  return { init, showPage, getCurrentPage };
})();
