/**
 * English Flashcard Study App
 * 英语抽认卡学习应用
 *
 * 前端对接后端 API（localhost:8888）
 * 后端不可用时降级为 localStorage 离线模式
 */

(function () {
  'use strict';

  // ============================================
  // API Configuration
  // ============================================
  const API_BASE = 'http://localhost:8888';
  let isOnline = false; // 后端是否可用

  async function apiFetch(path, options = {}) {
    const url = `${API_BASE}${path}`;
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
    return res.json();
  }

  // ============================================
  // State
  // ============================================
  let allCards = [];
  let totalCardCount = 0; // 当前场景的全部卡片总数
  let currentIndex = 0;
  let isFlipped = false;

  // Ratings storage: { cardId: 'know' | 'fuzzy' | 'unknown' }
  let ratings = {};

  // ============================================
  // DOM References
  // ============================================
  const $ = (sel) => document.querySelector(sel);

  const dom = {
    // Views
    directoryView: $('#directory-view'),
    studyView: $('#study-view'),
    categoryList: $('#category-list'),
    shortcutsPanel: $('#shortcuts-panel'),

    // Scene & Headers
    btnBackDir: $('#btn-back-dir'),
    currentSceneTitle: $('#current-scene-title'),

    // Card UI
    card: $('#card'),
    cardContainer: $('#card-container'),
    cardQuestion: $('#card-question'),
    cardAnswer: $('#card-answer'),
    cardCounter: $('#card-counter'),
    btnPrev: $('#btn-prev'),
    btnNext: $('#btn-next'),
    btnKnow: $('#btn-know'),
    btnFuzzy: $('#btn-fuzzy'),
    btnUnknown: $('#btn-unknown'),
    
    // Header actions & stats
    btnTheme: $('#btn-theme'),
    btnShuffle: $('#btn-shuffle'),
    progressText: $('#progress-text'),
    progressPercent: $('#progress-percent'),
    progressFill: $('#progress-fill'),
    progressBar: $('#progress-bar'),
    cardFeedback: $('#card-feedback'),
    feedbackIcon: $('#feedback-icon'),
    feedbackText: $('#feedback-text'),
    statKnow: $('#stat-know'),
    statFuzzy: $('#stat-fuzzy'),
    statUnknown: $('#stat-unknown'),
  };

  // Feedback messages config
  const FEEDBACK_CONFIG = {
    know:    { icon: '✅', text: 'Got it!', cssClass: 'feedback-know' },
    fuzzy:   { icon: '🤔', text: 'Almost!', cssClass: 'feedback-fuzzy' },
    unknown: { icon: '❌', text: "You'll get it next time", cssClass: 'feedback-unknown' },
  };

  // ============================================
  // Directory & Data Loading
  // ============================================
  
  async function initApp() {
    initTheme();
    bindEvents();
    // 首次进入应用，获取总体评分进度和目录树
    await loadGlobalProgress();
    await loadCategories();
  }

  async function loadGlobalProgress() {
    try {
      const progress = await apiFetch('/api/study/progress');
      ratings = progress.progress || {};
      isOnline = true;
      console.log(`[API] Loaded ${Object.keys(ratings).length} ratings from backend`);
      updateStats();
    } catch (err) {
      console.warn('[API] Backend unavailable, loading offline ratings:', err.message);
      isOnline = false;
      loadRatingsFromLocal();
      updateStats();
    }
  }

  async function loadCategories() {
    try {
      const data = await apiFetch('/api/categories');
      renderDirectory(data.categories);
    } catch (err) {
      console.warn('[API] Could not fetch categories. Falling back to simple default list.', err.message);
      // Fallback 只有在没起后端时临时给一个通道
      renderDirectory({ "基础口语": ["默认场景"] });
    }
  }

  function renderDirectory(categories) {
    if (!categories || Object.keys(categories).length === 0) {
      dom.categoryList.innerHTML = '<p>暂无任何课程，请先添加 flashcards 数据。</p>';
      return;
    }

    dom.categoryList.innerHTML = '';
    
    for (const [catName, scenes] of Object.entries(categories)) {
      const catBlock = document.createElement('div');
      catBlock.className = 'category-block';
      
      const catTitle = document.createElement('h3');
      catTitle.className = 'category-title';
      catTitle.textContent = catName;
      catBlock.appendChild(catTitle);
      
      const sceneList = document.createElement('div');
      sceneList.className = 'scene-list';
      
      scenes.forEach(sceneName => {
        const btn = document.createElement('button');
        btn.className = 'scene-item-btn';
        btn.textContent = `▶ ${sceneName}`;
        btn.dataset.category = catName;
        btn.dataset.scene = sceneName;
        btn.addEventListener('click', () => openScene(catName, sceneName));
        sceneList.appendChild(btn);
      });
      
      catBlock.appendChild(sceneList);
      dom.categoryList.appendChild(catBlock);
    }
  }

  // ============================================
  // Study Scene Logic
  // ============================================

  async function openScene(category, scene) {
    // 界面切换
    dom.directoryView.style.display = 'none';
    dom.studyView.style.display = 'block';
    dom.shortcutsPanel.style.display = 'flex';
    dom.currentSceneTitle.textContent = scene;
    
    try {
      const encodedCat = encodeURIComponent(category);
      const encodedScene = encodeURIComponent(scene);
      const data = await apiFetch(`/api/flashcards?category=${encodedCat}&scene=${encodedScene}`);
      
      allCards = data.flashcards.map((c) => ({
        id: c.id,
        question: c.question,
        answer: c.answer,
      }));
      console.log(`[API] Loaded ${allCards.length} cards for scene: ${scene}`);
    } catch (err) {
      console.warn('[API] Fetching scene failed, attempting offline.', err.message);
      if(allCards.length === 0) {
          // 如果也没有事先加载过全部卡片，那就 fallback
          await loadOfflineData(); 
          allCards = allCards.filter(c => true); // 简化处理
      }
    }

    totalCardCount = allCards.length;

    // 可以选择是否过滤掉当前场景中已学的卡片：
    // 若场景学习意在从头到尾连贯角色扮演，可以不过滤，或者加上 "复习模式"
    // 此处我们遵循原来的学习体系不过滤，仅做状态显示
    // 如果用户之前在设置中希望能跳过学过的卡片，可以加回 filter
    
    // 咱们在情境模式为了故事连贯，不剔除已学卡片，但会展示正确的已学比例！
    
    if (allCards.length > 0) {
      showCard(0);
    } else {
      showCard(-1); // 无数据
    }
  }

  function closeScene() {
    dom.studyView.style.display = 'none';
    dom.shortcutsPanel.style.display = 'none';
    dom.directoryView.style.display = 'block';
    // 清空状态
    allCards = [];
    totalCardCount = 0;
    currentIndex = 0;
  }

  async function loadOfflineData() {
    try {
      const response = await fetch('data/flashcards.csv');
      const text = await response.text();
      allCards = text.trim().split('\n').map((line, index) => {
        const sep = line.lastIndexOf(',');
        if (sep === -1) return null;
        return { id: `card_${index}`, question: line.substring(0, sep).trim(), answer: line.substring(sep + 1).trim() };
      }).filter(Boolean);
    } catch {
      allCards = [];
    }
  }

  // ============================================
  // Card Display
  // ============================================
  function showCard(index) {
    if (index === -1 || allCards.length === 0) {
      dom.cardQuestion.textContent = '此场景暂无卡片数据';
      dom.cardAnswer.textContent = '';
      dom.cardCounter.textContent = '0 / 0';
      dom.progressText.textContent = '0 / 0';
      dom.progressPercent.textContent = '0%';
      dom.progressFill.style.width = '0%';
      dom.progressBar.setAttribute('aria-valuenow', '0');
      return;
    }

    currentIndex = ((index % allCards.length) + allCards.length) % allCards.length;
    const card = allCards[currentIndex];

    dom.cardQuestion.textContent = card.question;
    dom.cardAnswer.textContent = card.answer;
    dom.cardCounter.textContent = `${currentIndex + 1} / ${allCards.length}`;

    // Unflip
    isFlipped = false;
    dom.card.classList.remove('flipped');

    updateProgress();
  }

  function updateProgress() {
    if(allCards.length === 0) return;
    
    // 计算当前场景下已经给过分（学过）的卡片数
    const studiedInScene = allCards.filter(c => ratings[c.id] !== undefined).length;
    const percent = Math.round((studiedInScene / totalCardCount) * 100);

    dom.progressText.textContent = `${studiedInScene} / ${totalCardCount} 已学习`;
    dom.progressPercent.textContent = `${percent}%`;
    dom.progressFill.style.width = `${percent}%`;
    dom.progressBar.setAttribute('aria-valuenow', String(percent));
  }

  // ============================================
  // Flip
  // ============================================
  function flipCard() {
    if (allCards.length === 0) return;
    isFlipped = !isFlipped;
    dom.card.classList.toggle('flipped', isFlipped);
  }

  // ============================================
  // Navigation
  // ============================================
  function prevCard() {
    showCard(currentIndex - 1);
  }

  function nextCard() {
    showCard(currentIndex + 1);
  }

  // ============================================
  // Rating (Backend API + Offline Fallback)
  // ============================================
  let isRating = false;

  function rateCard(rating) {
    if (allCards.length === 0 || isRating) return;
    isRating = true;

    const card = allCards[currentIndex];
    ratings[card.id] = rating;

    // 保存到后端或本地
    if (isOnline) {
      apiFetch('/api/study/rate', {
        method: 'POST',
        body: JSON.stringify({ card_id: card.id, rating }),
      }).catch((err) => {
        console.warn('[API] Rate failed, saved locally:', err.message);
        saveRatingsToLocal();
      });
    } else {
      saveRatingsToLocal();
    }

    updateStats();
    updateProgress(); // 及时更新内部进度条

    // Show feedback overlay, then advance
    showFeedback(rating, () => {
      isRating = false;
      if (currentIndex < allCards.length - 1) {
        showCard(currentIndex + 1);
      } else {
        // 完成此场景，可选择做彩蛋或者留在最后一张
        alert("🎉 恭喜！您已学完本场景所有剧情台词！");
      }
    });
  }

  function showFeedback(rating, onComplete) {
    const config = FEEDBACK_CONFIG[rating];
    if (!config) { onComplete(); return; }

    const fb = dom.cardFeedback;

    fb.classList.remove('show', 'feedback-know', 'feedback-fuzzy', 'feedback-unknown');
    void fb.offsetWidth;

    dom.feedbackIcon.textContent = config.icon;
    dom.feedbackText.textContent = config.text;
    fb.classList.add(config.cssClass, 'show');

    fb.addEventListener('animationend', function handler() {
      fb.removeEventListener('animationend', handler);
      fb.classList.remove('show', config.cssClass);
      onComplete();
    });
  }

  // ============================================
  // Stats
  // ============================================
  function updateStats() {
    let know = 0;
    let fuzzy = 0;
    let unknown = 0;

    for (const rating of Object.values(ratings)) {
      if (rating === 'know') know++;
      else if (rating === 'fuzzy') fuzzy++;
      else if (rating === 'unknown') unknown++;
    }

    // Header 显示全局统计
    if (dom.statKnow) dom.statKnow.textContent = String(know);
    if (dom.statFuzzy) dom.statFuzzy.textContent = String(fuzzy);
    if (dom.statUnknown) dom.statUnknown.textContent = String(unknown);
  }

  // ============================================
  // Shuffle
  // ============================================
  function shuffleCards() {
    if (allCards.length === 0) return;
    for (let i = allCards.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [allCards[i], allCards[j]] = [allCards[j], allCards[i]];
    }
    currentIndex = 0;
    showCard(0);
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

    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
      meta.content = next === 'light' ? 'hsl(220, 20%, 97%)' : 'hsl(230, 25%, 8%)';
    }
  }

  function updateThemeIcon() {
    const isDark = document.documentElement.dataset.theme !== 'light';
    dom.btnTheme.textContent = isDark ? '☀️' : '🌙';
  }

  // ============================================
  // Offline Persistence (localStorage fallback)
  // ============================================
  const STORAGE_KEY = 'flashcard-ratings';

  function saveRatingsToLocal() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(ratings));
    } catch (e) {
      console.warn('Failed to save ratings to localStorage:', e);
    }
  }

  function loadRatingsFromLocal() {
    try {
      const data = localStorage.getItem(STORAGE_KEY);
      if (data) {
        ratings = JSON.parse(data);
      }
    } catch (e) {
      console.warn('Failed to load ratings from localStorage:', e);
      ratings = {};
    }
  }

  // ============================================
  // Event Listeners
  // ============================================
  function bindEvents() {
    dom.btnBackDir.addEventListener('click', closeScene);
    dom.cardContainer.addEventListener('click', flipCard);

    dom.btnPrev.addEventListener('click', prevCard);
    dom.btnNext.addEventListener('click', nextCard);

    dom.btnKnow.addEventListener('click', () => rateCard('know'));
    dom.btnFuzzy.addEventListener('click', () => rateCard('fuzzy'));
    dom.btnUnknown.addEventListener('click', () => rateCard('unknown'));

    dom.btnTheme.addEventListener('click', toggleTheme);
    dom.btnShuffle.addEventListener('click', shuffleCards);

    document.addEventListener('keydown', handleKeyboard);
  }

  function handleKeyboard(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    
    // 如果当前是在目录页，不响应翻牌和评分键
    if (dom.studyView.style.display === 'none') {
        return;
    }

    switch (e.code) {
      case 'Space':
        e.preventDefault();
        flipCard();
        break;
      case 'ArrowLeft':
        e.preventDefault();
        prevCard();
        break;
      case 'ArrowRight':
        e.preventDefault();
        nextCard();
        break;
      case 'Digit1':
      case 'Numpad1':
        rateCard('know');
        break;
      case 'Digit2':
      case 'Numpad2':
        rateCard('fuzzy');
        break;
      case 'Digit3':
      case 'Numpad3':
        rateCard('unknown');
        break;
    }
  }

  // ============================================
  // Init Bootstrap
  // ============================================
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
  } else {
    initApp();
  }
})();
