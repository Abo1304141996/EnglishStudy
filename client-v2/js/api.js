/**
 * api.js — 后端 API 通信层
 */
const API_BASE = 'http://localhost:8000';

const Api = {
  async fetch(path, options = {}) {
    const url = `${API_BASE}${path}`;
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
    return res.json();
  },

  /** 获取学习包列表（含场景和统计） */
  async getPacks() {
    const data = await this.fetch('/api/categories');
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
