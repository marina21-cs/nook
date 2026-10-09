// Canonical, bounded PCM WAV. No recorded audio is written to browser storage.
export function wav16(chunks, rate) {
  if (!Number.isFinite(rate) || rate < 16000 || rate > 192000) throw new Error('Unsupported microphone sample rate. Type your question instead.');
  const total = Math.min(chunks.reduce((n, c) => n + c.length, 0), rate * 10);
  const input = new Float32Array(total);
  let at = 0;
  for (const chunk of chunks) { const size = Math.min(chunk.length, total - at); input.set(chunk.subarray(0, size), at); at += size; if (at === total) break; }
  const count = Math.min(160000, Math.floor(total * 16000 / rate));
  if (!count) throw new Error('No audio recorded. Try again or type your question.');
  const bytes = new Uint8Array(44 + count * 2), view = new DataView(bytes.buffer);
  const text = (offset, s) => [...s].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
  text(0, 'RIFF'); view.setUint32(4, bytes.length - 8, true); text(8, 'WAVE'); text(12, 'fmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, 16000, true); view.setUint32(28, 32000, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  text(36, 'data'); view.setUint32(40, count * 2, true);
  // Average each source interval to reduce aliasing when the browser uses 44.1/48 kHz.
  for (let i = 0; i < count; i++) {
    const start = Math.floor(i * rate / 16000), end = Math.min(total, Math.floor((i + 1) * rate / 16000));
    let sample = 0; for (let j = start; j < end; j++) sample += input[j];
    sample = Math.max(-1, Math.min(1, sample / Math.max(1, end - start)));
    view.setInt16(44 + i * 2, sample < 0 ? sample * 32768 : sample * 32767, true);
  }
  return bytes;
}
export function base64(bytes) {
  let binary = ''; for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return btoa(binary);
}
export class Recorder {
  constructor() { this.serial = 0; this.chunks = []; }
  async start(onLimit) {
    await this.cancel(); const serial = this.serial;
    const stream = await navigator.mediaDevices.getUserMedia({audio: {channelCount: 1, echoCancellation: true}, video: false});
    if (serial !== this.serial) { stream.getTracks().forEach(t => t.stop()); return false; }
    this.stream = stream;
    try {
      this.context = new AudioContext({sampleRate: 16000});
      await this.context.audioWorklet.addModule('/assets/recorder.js');
      if (serial !== this.serial) return false;
      this.rate = this.context.sampleRate; this.chunks = []; this.samples = 0;
      this.node = new AudioWorkletNode(this.context, 'bounded-recorder');
      this.node.port.onmessage = ({data}) => {
        if (serial !== this.serial) return;
        const remaining = this.rate * 10 - this.samples;
        if (remaining <= 0) return;
        const chunk = data.subarray(0, remaining); this.chunks.push(chunk); this.samples += chunk.length;
        if (this.samples >= this.rate * 10) onLimit();
      };
      this.source = this.context.createMediaStreamSource(stream); this.source.connect(this.node);
      // Processor emits silence; connecting keeps the graph running without microphone playback.
      this.node.connect(this.context.destination); await this.context.resume();
      if (serial !== this.serial) return false;
      this.timer = setTimeout(onLimit, 10000); return true;
    } catch (error) { await this.cancel(); throw error; }
  }
  async stop() { const chunks = this.chunks, rate = this.rate; await this.cancel(); return wav16(chunks, rate); }
  async cancel() {
    this.serial++; clearTimeout(this.timer);
    this.stream?.getTracks().forEach(t => t.stop()); this.stream = null;
    this.source?.disconnect(); this.node?.disconnect(); if (this.node) this.node.port.onmessage = null;
    const context = this.context; this.context = null;
    this.chunks = []; this.samples = 0;
    if (context && context.state !== 'closed') await context.close();
  }
}
