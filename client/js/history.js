/**
 * History Page - 学习记录
 *
 * 功能：
 * - 三个 Tab 展示认识/模糊/不认识的单词
 * - 认识 Tab：可调整分类（纠错）
 * - 模糊/不认识 Tab：点击学习 → 弹出模态 → 重新评分
 */

(function () {
  'use strict';

  const API_BASE = 'http://localhost:8888';

  // ============================================
  // State
  // ============================================
  let allCards = [];       // All flashcards from backend
  let progress = {};       // { card_id: rating }
  let activeTab = 'know';  // Current tab
  let studyCardId = null;  // Card being studied in modal
  let isFlipped = false;

  // ============================================
  // API
  // ============================================
  async function apiFetch(path, options = {}) {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    return res.json();
  }

  // ============================================
  // DOM
  // ============================================
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const dom = {
    // Stats
    statTotal: $('#stat-total'),
    statKnowCount: $('#stat-know-count'),
    statFuzzyCount: $('#stat-fuzzy-count'),
    statUnknownCount: $('#stat-unknown-count'),
    // Tabs
    tabKnow: $('#tab-know'),
    tabFuzzy: $('#tab-fuzzy'),
    tabUnknown: $('#tab-unknown'),
    tabKnowCount: $('#tab-know-count'),
    tabFuzzyCount: $('#tab-fuzzy-count'),
    tabUnknownCount: $('#tab-unknown-count'),
    // List
    cardList: $('#card-list'),
    emptyState: $('#empty-state'),
    emptyText: $('#empty-text'),
    // Modal
    studyModal: $('#study-modal'),
    modalClose: $('#modal-close'),
    modalCardContainer: $('#modal-card-container'),
    modalCard: $('#modal-card'),
    modalQuestion: $('#modal-question'),
    modalAnswer: $('#modal-answer'),
    modalKnow: $('#modal-know'),
    modalFuzzy: $('#modal-fuzzy'),
    modalUnknown: $('#modal-unknown'),
    // Theme
    btnTheme: $('#btn-theme'),
  };

  // ============================================
  // Data Loading
  // ============================================
  async function loadData() {
    try {
      const [cardsData, progressData] = await Promise.all([
        apiFetch('/api/flashcards'),
        apiFetch('/api/study/progress'),
      ]);
      allCards = cardsData.flashcards || [];
      progress = progressData.progress || {};
    } catch (err) {
      console.error('[History] Failed to load data:', err);
      allCards = [];
      progress = {};
    }

    updateCounts();
    renderList();
  }

  // ============================================
  // Counts
  // ============================================
  function getCounts() {
    let know = 0, fuzzy = 0, unknown = 0;
    for (const rating of Object.values(progress)) {
      if (rating === 'know') know++;
      else if (rating === 'fuzzy') fuzzy++;
      else if (rating === 'unknown') unknown++;
    }
    return { know, fuzzy, unknown, total: know + fuzzy + unknown };
  }

  function updateCounts() {
    const counts = getCounts();
    dom.statTotal.textContent = counts.total;
    dom.statKnowCount.textContent = counts.know;
    dom.statFuzzyCount.textContent = counts.fuzzy;
    dom.statUnknownCount.textContent = counts.unknown;

    dom.tabKnowCount.textContent = counts.know;
    dom.tabFuzzyCount.textContent = counts.fuzzy;
    dom.tabUnknownCount.textContent = counts.unknown;
  }

  // ============================================
  // Tab Switching
  // ============================================
  function switchTab(tab) {
    activeTab = tab;

    $$('.tab').forEach((btn) => {
      const isActive = btn.dataset.tab === tab;
      btn.classList.toggle('active', isActive);
      btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });

    renderList();
  }

  // ============================================
  // Card List Rendering
  // ============================================
  function getCardsByRating(rating) {
    const cardIds = Object.entries(progress)
      .filter(([, r]) => r === rating)
      .map(([id]) => id);

    return allCards.filter((c) => cardIds.includes(c.id));
  }

  function renderList() {
    const cards = getCardsByRating(activeTab);

    if (cards.length === 0) {
      dom.cardList.style.display = 'none';
      dom.emptyState.style.display = 'flex';
      const msgs = {
        know: '还没有标记为"认识"的单词',
        fuzzy: '还没有标记为"模糊"的单词',
        unknown: '还没有标记为"不认识"的单词',
      };
      dom.emptyText.textContent = msgs[activeTab] || '暂无数据';
      return;
    }

    dom.emptyState.style.display = 'none';
    dom.cardList.style.display = 'grid';

    dom.cardList.innerHTML = cards.map((card) => {
      if (activeTab === 'know') {
        return renderKnowCard(card);
      } else {
        return renderStudyCard(card);
      }
    }).join('');

    // Bind events
    if (activeTab === 'know') {
      dom.cardList.querySelectorAll('[data-action="move"]').forEach((btn) => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const cardId = btn.dataset.cardId;
          const newRating = btn.dataset.rating;
          rateCard(cardId, newRating);
        });
      });
    } else {
      dom.cardList.querySelectorAll('[data-action="study"]').forEach((btn) => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          openStudyModal(btn.dataset.cardId);
        });
      });
    }
  }

  function renderKnowCard(card) {
    return `
      <div class="history-card">
        <div class="history-card-content">
          <p class="history-card-question">${escapeHtml(card.question)}</p>
          <p class="history-card-answer">${escapeHtml(card.answer)}</p>
        </div>
        <div class="history-card-actions">
          <button class="btn-move btn-move-fuzzy" data-action="move" data-card-id="${card.id}" data-rating="fuzzy" title="调整为模糊">
            🤔 调整为模糊
          </button>
          <button class="btn-move btn-move-unknown" data-action="move" data-card-id="${card.id}" data-rating="unknown" title="调整为不认识">
            ❌ 调整为不认识
          </button>
        </div>
      </div>`;
  }

  function renderStudyCard(card) {
    return `
      <div class="history-card">
        <div class="history-card-content">
          <p class="history-card-question">${escapeHtml(card.question)}</p>
          <p class="history-card-answer">${escapeHtml(card.answer)}</p>
        </div>
        <div class="history-card-actions">
          <button class="btn-study" data-action="study" data-card-id="${card.id}">
            📖 开始学习
          </button>
        </div>
      </div>`;
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // ============================================
  // Rating (adjust / re-rate)
  // ============================================
  async function rateCard(cardId, newRating) {
    // Optimistic update
    progress[cardId] = newRating;
    updateCounts();
    renderList();

    try {
      await apiFetch('/api/study/rate', {
        method: 'POST',
        body: JSON.stringify({ card_id: cardId, rating: newRating }),
      });
    } catch (err) {
      console.error('[History] Rate failed:', err);
    }
  }

  // ============================================
  // Study Modal
  // ============================================
  function openStudyModal(cardId) {
    const card = allCards.find((c) => c.id === cardId);
    if (!card) return;

    studyCardId = cardId;
    isFlipped = false;

    dom.modalQuestion.textContent = card.question;
    dom.modalAnswer.textContent = card.answer;
    dom.modalCard.classList.remove('flipped');

    dom.studyModal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }

  function closeStudyModal() {
    dom.studyModal.style.display = 'none';
    document.body.style.overflow = '';
    studyCardId = null;
    isFlipped = false;
  }

  function flipModalCard() {
    isFlipped = !isFlipped;
    dom.modalCard.classList.toggle('flipped', isFlipped);
  }

  async function modalRate(rating) {
    if (!studyCardId) return;
    await rateCard(studyCardId, rating);
    closeStudyModal();
  }

  // ============================================
  // Theme
  // ============================================
  function initTheme() {
    const saved = localStorage.getItem('flashcard-theme');
    if (saved) {
      document.documentElement.dataset.theme = saved;
    } else if (window.matchMedia('(prefers-color-scheme: light)').matches) {
      document.documentElement.dataset.theme = 'light';
    }
    updateThemeIcon();
  }

  function toggleTheme() {
    const current = document.documentElement.dataset.theme;
    const next = current === 'light' ? 'dark' : 'light';
    document.documentElement.dataset.theme = next;
    localStorage.setItem('flashcard-theme', next);
    updateThemeIcon();
  }

  function updateThemeIcon() {
    const isDark = document.documentElement.dataset.theme !== 'light';
    dom.btnTheme.textContent = isDark ? '☀️' : '🌙';
  }

  // ============================================
  // Event Binding
  // ============================================
  function bindEvents() {
    // Tab switching
    $$('.tab').forEach((btn) => {
      btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Modal
    dom.modalCardContainer.addEventListener('click', flipModalCard);
    dom.modalClose.addEventListener('click', closeStudyModal);
    dom.modalKnow.addEventListener('click', () => modalRate('know'));
    dom.modalFuzzy.addEventListener('click', () => modalRate('fuzzy'));
    dom.modalUnknown.addEventListener('click', () => modalRate('unknown'));

    // Close modal on overlay click
    dom.studyModal.addEventListener('click', (e) => {
      if (e.target === dom.studyModal) closeStudyModal();
    });

    // Theme
    dom.btnTheme.addEventListener('click', toggleTheme);

    // Keyboard
    document.addEventListener('keydown', (e) => {
      if (dom.studyModal.style.display === 'flex') {
        if (e.code === 'Escape') closeStudyModal();
        if (e.code === 'Space') { e.preventDefault(); flipModalCard(); }
        if (e.code === 'Digit1' || e.code === 'Numpad1') modalRate('know');
        if (e.code === 'Digit2' || e.code === 'Numpad2') modalRate('fuzzy');
        if (e.code === 'Digit3' || e.code === 'Numpad3') modalRate('unknown');
      }
    });
  }

  // ============================================
  // Init
  // ============================================
  function init() {
    initTheme();
    bindEvents();
    loadData();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
