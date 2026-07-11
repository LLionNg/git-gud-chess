// Move sounds decoded through WebAudio for low-latency playback. Files are
// fetched eagerly; decoding waits for the first user gesture (autoplay policy).
export class SoundBank {
  constructor(files) {
    this.data = {};
    this.buffers = {};
    this.ctx = null;
    for (const [name, url] of Object.entries(files)) {
      fetch(url).then(r => r.arrayBuffer()).then(buf => { this.data[name] = buf; }).catch(() => {});
    }
  }

  unlock() {
    if (!this.ctx) this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (this.ctx.state === 'suspended') this.ctx.resume();
    for (const [name, buf] of Object.entries(this.data)) {
      if (this.buffers[name] || !buf) continue;
      this.ctx.decodeAudioData(buf.slice(0), decoded => { this.buffers[name] = decoded; });
    }
  }

  play(name) {
    if (!this.ctx || !this.buffers[name]) return;
    const source = this.ctx.createBufferSource();
    source.buffer = this.buffers[name];
    source.connect(this.ctx.destination);
    source.start();
  }
}
