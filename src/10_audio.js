const Snd = (() => {
  let ctx = null, master = null, musicG = null, sfxG = null, muted = store.get('muted', false);
  let timer = null, nextT = 0, step = 0, started = false;
  const mtof = (m) => 440 * Math.pow(2, (m - 69) / 12);
  function init() {
    if (ctx) { if (ctx.state === 'suspended') ctx.resume(); return; }
    const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return;
    ctx = new AC();
    const hp = ctx.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 120; hp.Q.value = 0.7;
    const comp = ctx.createDynamicsCompressor(); comp.threshold.value = -16; comp.ratio.value = 4; comp.attack.value = 0.004; comp.release.value = 0.18;
    master = ctx.createGain(); master.gain.value = muted ? 0 : 0.9;
    hp.connect(comp); comp.connect(master); master.connect(ctx.destination);
    musicG = ctx.createGain(); musicG.gain.value = 0.46; musicG.connect(hp);
    sfxG = ctx.createGain(); sfxG.gain.value = 0.9; sfxG.connect(hp);
    started = true;
  }
  function tone(type, f, t, dur, vol, o) {
    o = o || {}; const osc = ctx.createOscillator(); osc.type = type; osc.frequency.setValueAtTime(f, t);
    if (o.f2) osc.frequency.exponentialRampToValueAtTime(o.f2, t + dur);
    const g = ctx.createGain(); const a = o.a || 0.004;
    g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(vol, t + a); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    let last = osc;
    if (o.lp) { const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.setValueAtTime(o.lp, t); if (o.lp2) lp.frequency.exponentialRampToValueAtTime(o.lp2, t + dur); osc.connect(lp); last = lp; }
    last.connect(g); g.connect(o.dest || musicG);
    osc.start(t); osc.stop(t + dur + 0.05);
  }
  function noise(t, dur, vol, type, f1, f2) {
    const n = ctx.createBuffer(1, ctx.sampleRate * dur + 8, ctx.sampleRate);
    const d = n.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    const s = ctx.createBufferSource(); s.buffer = n;
    const f = ctx.createBiquadFilter(); f.type = type; f.frequency.setValueAtTime(f1, t); if (f2) f.frequency.exponentialRampToValueAtTime(f2, t + dur);
    const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(vol, t + 0.006); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    s.connect(f); f.connect(g); g.connect(sfxG); s.start(t); s.stop(t + dur + 0.05);
  }
  // bouncy picnic march in C, bass kept above the 120 Hz high-pass
  const bass = [0, -1, 7, -1, 12, -1, 7, -1, 0, -1, 7, -1, 5, -1, 7, -1];
  const mel = [72, -1, 76, 79, -1, 76, 72, -1, 74, -1, 76, 79, 81, -1, 79, 76, 74, -1, 72, 76, -1, 79, 76, -1, 74, 72, 67, 69, 71, -1, 72, -1];
  function sched(st, t) {
    const root = 60, sp = st & 15, bar = (st >> 4) & 1;
    if (sp % 4 === 0) { tone('triangle', 220, t, 0.12, 0.36, { f2: 140, a: 0.001, dest: musicG }); noise(t, 0.03, 0.08, 'highpass', 3000); }
    if (sp === 4 || sp === 12) noise(t, 0.12, 0.22, 'bandpass', 1800, 1200);
    if (sp % 2 === 0) noise(t, 0.04, 0.05, 'highpass', 7000);
    const b = bass[sp]; if (b >= 0) tone('sawtooth', mtof(root - 12 + b), t, 0.16, 0.16, { lp: 900, lp2: 400, dest: musicG });
    if (sp === 2 || sp === 10) [0, 4, 7].forEach((iv) => tone('square', mtof(root + iv), t, 0.12, 0.04, { lp: 2400 }));
    const m = mel[(st + bar * 0) & 31]; if (m > 0) tone('triangle', mtof(m), t, 0.22, 0.09, { lp: 2800, a: 0.01 });
  }
  function tick() {
    if (!ctx) return; while (nextT < ctx.currentTime + 0.14) { sched(step, nextT); nextT += 60 / 126 / 4; step = (step + 1) % 64; }
  }
  function startMusic() {
    init(); if (!ctx) return; step = 0; nextT = ctx.currentTime + 0.06;
    if (timer) clearInterval(timer); timer = setInterval(tick, 28); tick();
  }
  function stopMusic() { if (timer) { clearInterval(timer); timer = null; } }
  const ok = () => ctx && started && !muted;
  const A = {
    init, startMusic, stopMusic,
    get muted() { return muted; },
    setMuted(v) { muted = !!v; store.set('muted', muted); if (master) master.gain.value = muted ? 0 : 0.9; },
    click() { init(); if (!ok()) return; const t = ctx.currentTime; tone('square', 880, t, 0.07, 0.08, { dest: sfxG, lp: 3000 }); },
    slash() { init(); if (!ok()) return; const t = ctx.currentTime; noise(t, 0.12, 0.28, 'bandpass', 2400, 900); tone('sawtooth', 720, t, 0.1, 0.1, { f2: 280, dest: sfxG, lp: 2000 }); },
    spin() { init(); if (!ok()) return; const t = ctx.currentTime; tone('triangle', 520, t, 0.22, 0.12, { f2: 880, dest: sfxG }); noise(t, 0.2, 0.18, 'highpass', 2000, 800); },
    bonk() { init(); if (!ok()) return; const t = ctx.currentTime; noise(t, 0.16, 0.34, 'bandpass', 420, 180); tone('square', 196, t, 0.18, 0.24, { f2: 90, dest: sfxG, lp: 700 }); tone('triangle', 784, t, 0.1, 0.14, { f2: 1320, dest: sfxG }); tone('square', 523, t + 0.045, 0.09, 0.1, { f2: 280, dest: sfxG, lp: 2200 }); noise(t, 0.09, 0.18, 'highpass', 4500, 1800); },
    nibble() { init(); if (!ok()) return; const t = ctx.currentTime; tone('square', 420 + Math.random() * 40, t, 0.05, 0.06, { f2: 260, dest: sfxG, lp: 1600 }); },
    wave() { init(); if (!ok()) return; const t = ctx.currentTime; tone('triangle', 523, t, 0.16, 0.1, { dest: sfxG }); tone('triangle', 659, t + 0.08, 0.18, 0.1, { dest: sfxG }); },
    poof() { init(); if (!ok()) return; const t = ctx.currentTime; noise(t, 0.2, 0.22, 'bandpass', 1400, 500); tone('triangle', 620, t, 0.12, 0.07, { f2: 280, dest: sfxG, lp: 1800 }); },
    lose() { init(); if (!ok()) return; const t = ctx.currentTime; tone('triangle', 392, t, 0.25, 0.12, { dest: sfxG }); tone('triangle', 311, t + 0.18, 0.35, 0.12, { f2: 200, dest: sfxG }); },
    bark(who) {
      init(); if (!ok()) return;
      const t = ctx.currentTime;
      const emma = who === 'emma';
      const f0 = emma ? 320 : 430;
      const f1 = emma ? 180 : 240;
      tone('triangle', f0, t, 0.16, 0.22, { f2: f1, dest: sfxG, lp: 1600, a: 0.006 });
      tone('square', f0 * 0.72, t, 0.12, 0.08, { f2: f1 * 0.8, dest: sfxG, lp: 900 });
      noise(t, 0.14, 0.2, 'bandpass', emma ? 700 : 900, 320);
      tone('triangle', f0 * 1.15, t + 0.14, 0.13, 0.16, { f2: f1 * 0.9, dest: sfxG, lp: 1400, a: 0.005 });
      noise(t + 0.14, 0.11, 0.14, 'bandpass', 800, 280);
    },
    scamper() {
      init(); if (!ok()) return;
      const t = ctx.currentTime;
      noise(t, 0.18, 0.16, 'bandpass', 1400, 600);
      noise(t + 0.08, 0.16, 0.12, 'highpass', 1800, 900);
      tone('triangle', 260, t, 0.08, 0.05, { f2: 180, dest: sfxG, lp: 700 });
    },
    roundStart() {
      init(); if (!ok()) return;
      const t = ctx.currentTime;
      tone('triangle', 523, t, 0.16, 0.12, { dest: sfxG });
      tone('triangle', 659, t + 0.09, 0.16, 0.12, { dest: sfxG });
      tone('triangle', 784, t + 0.18, 0.28, 0.14, { dest: sfxG });
    },
    roundClear() {
      init(); if (!ok()) return;
      const t = ctx.currentTime;
      [523, 659, 784, 1046].forEach((f, i) => tone('triangle', f, t + i * 0.09, 0.28, 0.13, { dest: sfxG }));
    },
    armor() {
      init(); if (!ok()) return;
      const t = ctx.currentTime;
      tone('square', 240, t, 0.09, 0.16, { f2: 140, dest: sfxG, lp: 900 });
      noise(t, 0.1, 0.22, 'bandpass', 900, 400);
      tone('triangle', 620, t + 0.04, 0.08, 0.08, { f2: 300, dest: sfxG, lp: 1600 });
    },
    buzz() {
      init(); if (!ok()) return;
      const t = ctx.currentTime;
      tone('sawtooth', 280, t, 0.16, 0.06, { f2: 340, dest: sfxG, lp: 1400, a: 0.02 });
      noise(t, 0.14, 0.08, 'bandpass', 2200, 1600);
    },
    waspHit() {
      init(); if (!ok()) return;
      const t = ctx.currentTime;
      noise(t, 0.14, 0.26, 'bandpass', 1800, 700);
      tone('square', 880, t, 0.09, 0.1, { f2: 220, dest: sfxG, lp: 2400 });
    },
    bossHorn() {
      init(); if (!ok()) return;
      const t = ctx.currentTime;
      tone('square', 196, t, 0.22, 0.18, { dest: sfxG, lp: 900 });
      tone('triangle', 294, t + 0.12, 0.28, 0.16, { dest: sfxG });
      tone('triangle', 392, t + 0.26, 0.36, 0.16, { dest: sfxG });
      noise(t, 0.2, 0.16, 'bandpass', 600, 280);
    },
    bossHit() {
      init(); if (!ok()) return;
      const t = ctx.currentTime;
      noise(t, 0.16, 0.3, 'bandpass', 520, 180);
      tone('square', 165, t, 0.14, 0.2, { f2: 90, dest: sfxG, lp: 700 });
      tone('triangle', 523, t + 0.05, 0.1, 0.1, { f2: 300, dest: sfxG });
    },
    bossDown() {
      init(); if (!ok()) return;
      const t = ctx.currentTime;
      [392, 494, 587, 784, 988].forEach((f, i) => tone('triangle', f, t + i * 0.08, 0.28, 0.14, { dest: sfxG }));
      noise(t, 0.28, 0.22, 'bandpass', 900, 300);
    },
    bearPop() {
      init(); if (!ok()) return;
      const t = ctx.currentTime;
      // Boing + a short playful jig (original, not a licensed tune)
      tone('sine', 160, t, 0.2, 0.22, { f2: 420, dest: sfxG, lp: 1800, a: 0.004 });
      tone('triangle', 320, t + 0.05, 0.22, 0.16, { f2: 220, dest: sfxG, lp: 1400 });
      noise(t, 0.12, 0.14, 'bandpass', 700, 300);
      [392, 494, 523, 659, 784, 659].forEach((f, i) => {
        tone('triangle', f, t + 0.18 + i * 0.075, 0.16, 0.13, { dest: sfxG, lp: 2200 });
      });
    }
  };
  return A;
})();
