/**
 * router.js — SPA 视图路由 + 全局导航行为
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

    document.querySelectorAll('.nav-link, .mobile-nav-link').forEach(link => {
      link.classList.toggle('active', link.dataset.page === pageId);
    });

    // 关闭移动菜单
    const mm = document.getElementById('mobile-menu');
    if (mm) mm.classList.add('hidden');

    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function getCurrentPage() {
    return currentPage;
  }

  function navigateTo(page) {
    if (page === 'pack-list') { showPage('pack-list'); PacksPage.load(); }
    else if (page === 'my-learning') { showPage('my-learning'); HistoryPage.load(); }
  }

  function init() {
    // 桌面端 + 移动端导航
    document.querySelectorAll('.nav-link, .mobile-nav-link').forEach(link => {
      if (!link.dataset.page) return;
      link.addEventListener('click', () => navigateTo(link.dataset.page));
    });

    // Logo
    document.getElementById('nav-logo').addEventListener('click', () => navigateTo('pack-list'));

    // 移动菜单切换
    const menuBtn = document.getElementById('mobile-menu-btn');
    const menu = document.getElementById('mobile-menu');
    if (menuBtn && menu) {
      menuBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        menu.classList.toggle('hidden');
      });
      // 点击外部关闭
      document.addEventListener('click', (e) => {
        if (menu.classList.contains('hidden')) return;
        if (menu.contains(e.target) || menuBtn.contains(e.target)) return;
        menu.classList.add('hidden');
      });
    }

    // 新增积累按钮（桌面 + 移动）
    const openIngest = () => { if (typeof IngestWizard !== 'undefined') IngestWizard.open(); };
    const btnD = document.getElementById('open-ingest-btn-desktop');
    const btnM = document.getElementById('open-ingest-btn-mobile');
    if (btnD) btnD.addEventListener('click', openIngest);
    if (btnM) btnM.addEventListener('click', () => {
      document.getElementById('mobile-menu').classList.add('hidden');
      openIngest();
    });

    // 新建学习包
    const newPackBtn = document.getElementById('new-pack-btn');
    if (newPackBtn) newPackBtn.addEventListener('click', async () => {
      const name = await Modal.prompt({ title: '新建学习包', label: '名称', placeholder: '如：Shameless-S03' });
      if (!name) return;
      try {
        await Api.createPack(name);
        Modal.toast('已创建学习包', 'success');
        PacksPage.load();
      } catch (err) {
        Modal.toast(err.message, 'error', 3000);
      }
    });

    // 返回按钮
    document.getElementById('back-to-packs').addEventListener('click', () => {
      showPage('pack-list');
    });
    document.getElementById('back-to-scenes').addEventListener('click', () => {
      showPage('scene-list');
    });
  }

  return { init, showPage, getCurrentPage, navigateTo };
})();
