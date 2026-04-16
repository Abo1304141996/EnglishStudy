/**
 * flashcard.js — 闪卡学习页核心逻辑（含进度保存）
 */
const FlashcardPage = (() => {
  let cards = [];
  let currentIndex = 0;
  let isFlipped = false;
  let isAnimating = false;
  let currentCategory = '';
  let currentScene = '';

  const PROGRESS_KEY = 'flashcard-scene-progress';

  const FEEDBACK = {
    know:    { text: 'Got it', css: 'feedback-know' },
    fuzzy:   { text: 'Almost!', css: 'feedback-fuzzy' },
    unknown: { text: "You'll get it next time", css: 'feedback-unknown' },
  };

  // ===== 进度持久化 =====
  function getProgressKey() {
    return `${currentCategory}::${currentScene}`;
  }

  function saveProgress() {
    try {
      const all = JSON.parse(localStorage.getItem(PROGRESS_KEY) || '{}');
      all[getProgressKey()] = currentIndex;
      localStorage.setItem(PROGRESS_KEY, JSON.stringify(all));
    } catch (e) { /* ignore */ }
  }

  function loadProgress() {
    try {
      const all = JSON.parse(localStorage.getItem(PROGRESS_KEY) || '{}');
      return all[getProgressKey()] || 0;
    } catch (e) { return 0; }
  }

  // ===== 页面入口 =====
  async function open(category, scene) {
    currentCategory = category;
    currentScene = scene;
    isFlipped = false;

    document.getElementById('current-scene-name').textContent = scene;
    Router.showPage('flashcard');

    try {
      cards = await Api.getFlashcards(category, scene);
      if (cards.length === 0) {
        document.getElementById('card-front-text').textContent = '此场景暂无卡片';
        document.getElementById('card-index-display').textContent = '0 / 0';
        return;
      }
      // 恢复上次进度
      const savedIdx = loadProgress();
      currentIndex = savedIdx < cards.length ? savedIdx : 0;
      renderCard();
    } catch (err) {
      console.error('[Flashcard] Failed to load:', err);
      document.getElementById('card-front-text').textContent = '加载失败';
    }
  }

  function renderCard() {
    if (cards.length === 0) return;
    const card = cards[currentIndex];

    document.getElementById('card-front-text').textContent = card.question;
    document.getElementById('card-back-text').textContent = card.answer;
    document.getElementById('card-index-display').textContent = `${currentIndex + 1} / ${cards.length}`;

    const pct = Math.round(((currentIndex + 1) / cards.length) * 100);
    document.getElementById('card-progress-bar').style.width = `${pct}%`;

    isFlipped = false;
    document.getElementById('flashcard').classList.remove('card-flipped');

    // 每次翻到新卡都保存进度
    saveProgress();
  }

  function flipCard() {
    if (cards.length === 0 || isAnimating) return;
    isFlipped = !isFlipped;
    document.getElementById('flashcard').classList.toggle('card-flipped', isFlipped);
  }

  function prevCard() {
    if (cards.length === 0 || isAnimating) return;
    if (currentIndex > 0) {
      currentIndex--;
      switchWithAnimation();
    }
  }

  function nextCard() {
    if (cards.length === 0 || isAnimating) return;
    if (currentIndex < cards.length - 1) {
      currentIndex++;
    } else {
      currentIndex = 0;
    }
    switchWithAnimation();
  }

  function switchWithAnimation() {
    isAnimating = true;
    const el = document.getElementById('flashcard');
    el.classList.add('card-slide-out-left');
    setTimeout(() => {
      renderCard();
      el.classList.remove('card-slide-out-left');
      el.classList.add('card-slide-in-right');
      setTimeout(() => {
        el.classList.remove('card-slide-in-right');
        isAnimating = false;
      }, 350);
    }, 350);
  }

  /** 评分反馈：浮现覆盖卡片 + 旋转错开 */
  function showFeedback(rating, onComplete) {
    const config = FEEDBACK[rating];
    if (!config) { onComplete(); return; }

    const fb = document.getElementById('card-feedback');
    fb.classList.remove('show', 'feedback-know', 'feedback-fuzzy', 'feedback-unknown', 'hidden');
    document.getElementById('feedback-text').textContent = config.text;
    fb.classList.add(config.css);

    void fb.offsetWidth;
    fb.classList.add('show');

    fb.addEventListener('animationend', function handler() {
      fb.removeEventListener('animationend', handler);
      fb.classList.remove('show', config.css);
      fb.classList.add('hidden');
      onComplete();
    });
  }

  function rateCard(rating) {
    if (cards.length === 0 || isAnimating) return;
    isAnimating = true;

    const card = cards[currentIndex];
    Api.rateCard(card.id, rating).catch(err => {
      console.warn('[Flashcard] Rate failed:', err.message);
    });

    showFeedback(rating, () => {
      if (currentIndex < cards.length - 1) {
        currentIndex++;
        switchWithAnimation();
      } else {
        isAnimating = false;
        // 学完清除该场景进度
        try {
          const all = JSON.parse(localStorage.getItem(PROGRESS_KEY) || '{}');
          delete all[getProgressKey()];
          localStorage.setItem(PROGRESS_KEY, JSON.stringify(all));
        } catch (e) { /* ignore */ }
        alert('🎉 恭喜！你已学完本场景所有卡片！');
      }
    });
  }

  function init() {
    document.getElementById('flashcard').addEventListener('click', flipCard);
    document.getElementById('prev-card').addEventListener('click', prevCard);
    document.getElementById('next-card').addEventListener('click', nextCard);

    document.querySelectorAll('.rate-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        rateCard(btn.dataset.rating);
      });
    });

    document.addEventListener('keydown', (e) => {
      if (Router.getCurrentPage() !== 'flashcard') return;
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      switch (e.code) {
        case 'Space': e.preventDefault(); flipCard(); break;
        case 'ArrowLeft': e.preventDefault(); prevCard(); break;
        case 'ArrowRight': e.preventDefault(); nextCard(); break;
        case 'Digit1': case 'Numpad1': rateCard('know'); break;
        case 'Digit2': case 'Numpad2': rateCard('fuzzy'); break;
        case 'Digit3': case 'Numpad3': rateCard('unknown'); break;
      }
    });
  }

  return { open, init };
})();
