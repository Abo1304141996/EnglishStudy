/**
 * pcm-worklet.js — AudioWorklet Processor
 * 将浏览器原生采样率（通常 48kHz / 44.1kHz）线性下采样到 16kHz，
 * 转换为 Int16 PCM，每 ~100ms 通过 port 发给主线程。
 */
class PCMDownsampler extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const opts = (options && options.processorOptions) || {};
    this.targetRate = opts.targetRate || 16000;
    this.inputRate = sampleRate; // 全局变量：AudioContext 采样率
    this.ratio = this.inputRate / this.targetRate;

    // ~100ms 缓冲
    this.frameSize = Math.floor(this.targetRate * 0.1);
    this.buffer = new Int16Array(this.frameSize);
    this.bufferIndex = 0;

    // 用于线性插值的上一样本
    this._lastSample = 0;
    this._virtualIndex = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;
    const ch = input[0];
    if (!ch) return true;

    // 线性下采样
    while (this._virtualIndex < ch.length) {
      const i = Math.floor(this._virtualIndex);
      const frac = this._virtualIndex - i;
      const s0 = i === 0 ? this._lastSample : ch[i - 1];
      const s1 = ch[i] !== undefined ? ch[i] : s0;
      const sample = s0 + (s1 - s0) * frac;

      // float [-1,1] -> Int16
      let v = Math.max(-1, Math.min(1, sample));
      this.buffer[this.bufferIndex++] = v < 0 ? v * 0x8000 : v * 0x7fff;

      if (this.bufferIndex >= this.frameSize) {
        // 发送拷贝（ArrayBuffer 可 transfer）
        const out = new Int16Array(this.buffer);
        this.port.postMessage(out.buffer, [out.buffer]);
        this.buffer = new Int16Array(this.frameSize);
        this.bufferIndex = 0;
      }

      this._virtualIndex += this.ratio;
    }

    // 维护跨 block 索引
    this._virtualIndex -= ch.length;
    this._lastSample = ch[ch.length - 1] || 0;

    return true;
  }
}

registerProcessor('pcm-downsampler', PCMDownsampler);
