/**
 * voice-call.js — 语音通话主控制器
 * 连接 /ws/voice，协调麦克风、TTS 播放器与 UI
 */

const WS_URL = (() => {
  const base = (window.API_BASE || 'http://localhost:8888')
    .replace(/^http/, 'ws');
  return base + '/ws/voice';
})();

class VoiceCall {
  constructor() {
    this.ws = null;
    this.mic = null;
    this.player = null;
    this.connected = false;
    this.muted = false;      // 默认开启麦克风
    this.partialText = '';
    this.callbacks = {
      status: () => {},
      asrPartial: () => {},
      asrFinal: () => {},
      aiDelta: () => {},
      aiSpeakText: () => {},   // TTS 开始播某句
      error: () => {},
    };
  }

  on(event, fn) { this.callbacks[event] = fn; return this; }

  async start() {
    this._setStatus('connecting');
    await this._openSocket();

    this.player = new TTSQueuePlayer({
      onStateChange: ({ playing, text }) => {
        if (playing) this.callbacks.aiSpeakText(text);
      }
    });

    this.mic = new MicCapture({
      onPcm: (buf) => {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.ws.send(buf);
        }
      }
    });
    try {
      await this.mic.start();
    } catch (e) {
      this.callbacks.error('麦克风授权失败：' + e.message);
      throw e;
    }

    this.setMuted(false); // 默认开启
    this._setStatus('connected');
  }

  async stop() {
    this._setStatus('ended');
    try { this.ws && this.ws.close(); } catch {}
    if (this.mic) await this.mic.stop();
    if (this.player) this.player.flush();
    this.ws = this.mic = this.player = null;
    this.connected = false;
  }

  setMuted(v) {
    this.muted = !!v;
    if (this.mic) this.mic.setMuted(this.muted);
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: this.muted ? 'mute' : 'unmute' }));
    }
  }

  interrupt() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'interrupt' }));
    }
    if (this.player) this.player.flush();
  }

  reset() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'reset' }));
    }
    if (this.player) this.player.flush();
  }

  // ---------- WS ----------

  _openSocket() {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(WS_URL);
      ws.binaryType = 'arraybuffer';
      this.ws = ws;
      ws.onopen = () => { this.connected = true; resolve(); };
      ws.onclose = () => { this.connected = false; this._setStatus('ended'); };
      ws.onerror = (e) => {
        this.callbacks.error('WebSocket 连接失败');
        reject(e);
      };
      ws.onmessage = (ev) => this._onMessage(ev);
    });
  }

  _onMessage(ev) {
    if (typeof ev.data !== 'string') {
      // 二进制 MP3 chunk
      if (this.player) this.player.appendBinary(new Uint8Array(ev.data));
      return;
    }
    let msg;
    try { msg = JSON.parse(ev.data); } catch { return; }

    switch (msg.type) {
      case 'session.ready':
        this._setStatus('ready');
        break;
      case 'asr.partial':
        this.partialText = msg.text || '';
        this.callbacks.asrPartial(this.partialText);
        // 用户一说话就打断本地播放（立即感官反馈）
        if (this.player && this.player.playing) this.player.flush();
        break;
      case 'asr.final':
        this.partialText = '';
        this.callbacks.asrFinal(msg.text || '');
        break;
      case 'turn.start':
        this.callbacks.aiDelta({ seq: msg.seq, text: '', reset: true, userText: msg.user_text });
        break;
      case 'llm.delta':
        this.callbacks.aiDelta({ seq: msg.seq, text: msg.text || '' });
        break;
      case 'tts.begin':
        if (this.player) this.player.begin(msg.seq, msg.text || '');
        break;
      case 'tts.end':
        if (this.player) this.player.end(msg.seq);
        break;
      case 'tts.flush':
        if (this.player) this.player.flush();
        break;
      case 'turn.end':
      case 'turn.cancelled':
        break;
      case 'error':
        this.callbacks.error(`[${msg.code}] ${msg.message}`);
        break;
    }
  }

  _setStatus(s) { this.callbacks.status(s); }
}

window.VoiceCall = VoiceCall;
