/**
 * api.js — 后端 API 通信层
 */
const API_BASE = '';

const Api = {
  async fetch(path, options = {}) {
    const url = `${API_BASE}${path}`;
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    if (!res.ok) {
      let detail = `API ${res.status}: ${res.statusText}`;
      try {
        const errData = await res.json();
        if (errData && errData.detail) detail = errData.detail;
      } catch (_) { /* ignore */ }
      throw new Error(detail);
    }
    return res.json();
  },

  /** 获取学习包列表（含场景和统计） */
  async getPacks() {
    const data = await this.fetch('/api/packs');
    return data.packs || [];
  },

  /** 获取某个分类+场景下的闪卡 */
  async getFlashcards(category, scene) {
    const params = new URLSearchParams();
    if (category) params.set('category', category);
    if (scene) params.set('scene', scene);
    const data = await this.fetch(`/api/flashcards?${params}`);
    return data.flashcards || [];
  },

  /** 创建学习包 */
  createPack(name, tag) {
    return this.fetch('/api/packs', {
      method: 'POST',
      body: JSON.stringify({ name, tag: tag || '日常生活' }),
    });
  },
  updatePack(packId, payload) {
    return this.fetch(`/api/packs/${encodeURIComponent(packId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },
  deletePack(packId, force = false) {
    return this.fetch(`/api/packs/${encodeURIComponent(packId)}?force=${force}`, {
      method: 'DELETE',
    });
  },
  createScene(packId, name) {
    return this.fetch(`/api/packs/${encodeURIComponent(packId)}/scenes`, {
      method: 'POST',
      body: JSON.stringify({ name }),
    });
  },
  updateScene(packId, sceneId, name) {
    return this.fetch(`/api/packs/${encodeURIComponent(packId)}/scenes/${encodeURIComponent(sceneId)}`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    });
  },
  deleteScene(packId, sceneId, force = false) {
    return this.fetch(`/api/packs/${encodeURIComponent(packId)}/scenes/${encodeURIComponent(sceneId)}?force=${force}`, {
      method: 'DELETE',
    });
  },

  /** AI: 解析积累文本为候选卡片 */
  async aiParseCards(text) {
    const data = await this.fetch('/api/ai/parse-cards', {
      method: 'POST',
      body: JSON.stringify({ text }),
    });
    return data.cards || [];
  },
  /** AI: 优化单张卡片 */
  async aiRefineCard(front, back, instruction, originalSource) {
    const data = await this.fetch('/api/ai/refine-card', {
      method: 'POST',
      body: JSON.stringify({ front, back, instruction, original_source: originalSource }),
    });
    return data.card;
  },
  /** 落地审核通过的卡片 */
  commitCards(payload) {
    return this.fetch('/api/cards/commit', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /** 提交评分 */
  async rateCard(cardId, rating) {
    return this.fetch('/api/study/rate', {
      method: 'POST',
      body: JSON.stringify({ card_id: cardId, rating }),
    });
  },

  /** 获取学习进度 */
  async getProgress() {
    const data = await this.fetch('/api/study/progress');
    return data.progress || {};
  },

  /** 获取学习统计 */
  async getStats() {
    const data = await this.fetch('/api/study/stats');
    return data;
  },

  /** 获取学习记录 */
  async getStudyRecords(days = 30) {
    const data = await this.fetch(`/api/study/records?days=${days}`);
    return data.records || [];
  },

  /** 获取学习会话历史 */
  async getSessionHistory(limit = 20) {
    const data = await this.fetch(`/api/session/history?limit=${limit}`);
    return data.sessions || [];
  },
};
