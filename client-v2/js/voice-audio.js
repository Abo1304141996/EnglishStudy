/**
 * voice-audio.js — 麦克风采集 + MP3 句子队列播放
 *
 * 采集：
 *   getUserMedia → AudioContext → AudioWorkletNode(pcm-downsampler) → 16kHz Int16 PCM
 *   调用 onPcm(ArrayBuffer) 回调
 *
 * 播放：
 *   按 seq 维护句子队列；每收到一个 tts.begin 开一个新条目，chunk 追加累积，
 *   tts.end 转 Blob 播放；tts.flush 清队列、停止当前播放。
 */

class MicCapture {
  constructor({ onPcm }) {
    this.onPcm = onPcm;
    this.stream = null;
    this.ctx = null;
    this.node = null;
    this.source = null;
    this.muted = false;
  }

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
      },
      video: false,
    });

    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (this.ctx.state === 'suspended') await this.ctx.resume();

    await this.ctx.audioWorklet.addModule('js/pcm-worklet.js');
    this.node = new AudioWorkletNode(this.ctx, 'pcm-downsampler', {
      processorOptions: { targetRate: 16000 },
    });
    this.node.port.onmessage = (ev) => {
      if (this.muted) return;
      if (this.onPcm) this.onPcm(ev.data); // ArrayBuffer
    };

    this.source = this.ctx.createMediaStreamSource(this.stream);
    this.source.connect(this.node);
    // 不连到 destination，避免回声
  }

  setMuted(v) { this.muted = !!v; }

  async stop() {
    try { this.node && this.node.disconnect(); } catch {}
    try { this.source && this.source.disconnect(); } catch {}
    try { this.ctx && await this.ctx.close(); } catch {}
    try { this.stream && this.stream.getTracks().forEach(t => t.stop()); } catch {}
    this.stream = this.ctx = this.node = this.source = null;
  }
}


class TTSQueuePlayer {
  constructor({ onStateChange } = {}) {
    this.onStateChange = onStateChange || (() => {});
    // seq -> { chunks: Uint8Array[], ended: boolean, text: string }
    this.pending = new Map();
    this.queue = []; // [{seq, blob, text}]
    this.currentSeq = null;
    this.audio = new Audio();
    this.audio.addEventListener('ended', () => this._playNext());
    this.audio.addEventListener('error', () => this._playNext());
    this.playing = false;
  }

  begin(seq, text) {
    this.pending.set(seq, { chunks: [], ended: false, text });
  }

  appendBinary(bytes) {
    // 二进制 chunk 归属当前"最新 begin 但尚未 end"的 seq
    // 简化：找到最大的 pending seq
    let latest = -1;
    for (const seq of this.pending.keys()) {
      if (seq > latest) latest = seq;
    }
    if (latest < 0) return;
    const item = this.pending.get(latest);
    if (!item || item.ended) return;
    item.chunks.push(bytes);
  }

  end(seq) {
    const item = this.pending.get(seq);
    if (!item) return;
    item.ended = true;
    this.pending.delete(seq);
    const blob = new Blob(item.chunks, { type: 'audio/mpeg' });
    this.queue.push({ seq, blob, text: item.text });
    if (!this.playing) this._playNext();
  }

  flush() {
    this.pending.clear();
    this.queue = [];
    this.currentSeq = null;
    try { this.audio.pause(); } catch {}
    try {
      if (this.audio.src) URL.revokeObjectURL(this.audio.src);
    } catch {}
    this.audio.removeAttribute('src');
    this.audio.load();
    this.playing = false;
    this.onStateChange({ playing: false, text: '' });
  }

  _playNext() {
    // 释放上一条 url
    try {
      if (this.audio.src) URL.revokeObjectURL(this.audio.src);
    } catch {}
    const next = this.queue.shift();
    if (!next) {
      this.playing = false;
      this.currentSeq = null;
      this.onStateChange({ playing: false, text: '' });
      return;
    }
    this.currentSeq = next.seq;
    this.playing = true;
    const url = URL.createObjectURL(next.blob);
    this.audio.src = url;
    this.audio.play().catch(err => {
      console.error('[TTS] play failed:', err);
      this._playNext();
    });
    this.onStateChange({ playing: true, text: next.text });
  }
}

window.MicCapture = MicCapture;
window.TTSQueuePlayer = TTSQueuePlayer;
