const STICK_DEAD = 0.15;
const STICK_RADIUS = 60;
const CAM_TURN = Math.PI * 2 / 3; // 120 deg/s when held
const CAM_SWIPE = 0.008; // radians per CSS pixel
const CAM_TAP = 0.18; // seconds: short press = 45° step

const Input = {
  x: 0, z: 0,
  slash: false, slashEdge: false, slashFromTouch: false,
  spin: false, spinEdge: false,
  kbX: 0, kbZ: 0, padX: 0, padZ: 0, gpX: 0, gpZ: 0,
  gpHave: false, gpActive: false, prevBtn: [],
  stickOn: false, stickCx: 0, stickCy: 0,
  kbYaw: 0, btnYaw: 0, gpYaw: 0,
  yawSnap: 0, yawReleaseSnap: false, swipeDelta: 0,
  _qDown: 0, _eDown: 0, _qT: 0, _eT: 0,
  _btnL: 0, _btnR: 0, _btnLT: 0, _btnRT: 0,
  _gpStickOn: false,
  init() {
    const isTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints || 0) > 0;
    if (isTouch || /touch=1/.test(location.search)) document.body.classList.add('touch');
    this.initKeys(); this.initTouch(); this.initPad(); this.initOrbit(); this.initSecret();
  },
  initKeys() {
    const down = (e, on) => {
      const k = e.key;
      if (k === 'ArrowLeft' || k === 'a' || k === 'A') this.kbX = on ? -1 : (this.kbX < 0 ? 0 : this.kbX);
      else if (k === 'ArrowRight' || k === 'd' || k === 'D') this.kbX = on ? 1 : (this.kbX > 0 ? 0 : this.kbX);
      else if (k === 'ArrowUp' || k === 'w' || k === 'W') this.kbZ = on ? -1 : (this.kbZ < 0 ? 0 : this.kbZ);
      else if (k === 'ArrowDown' || k === 's' || k === 'S') this.kbZ = on ? 1 : (this.kbZ > 0 ? 0 : this.kbZ);
      else if (k === 'q' || k === 'Q') this._yawKey('q', on);
      else if (k === 'e' || k === 'E') this._yawKey('e', on);
      else if (k === ' ' || k === 'j' || k === 'J') {
        if (on && Game.state === 'steal') { UI.skipSteal(); return; }
        if (on && !this.slash) { this.slashEdge = true; this.slashFromTouch = false; } this.slash = on;
      }
      else if (k === 'Shift' || k === 'k' || k === 'K') { if (on && !this.spin) this.spinEdge = true; this.spin = on; }
      else if (on && (k === 'p' || k === 'P' || k === 'Escape')) UI.onPause && UI.onPause();
      else if (on && (k === 'm' || k === 'M')) { Snd.init(); Snd.setMuted(!Snd.muted); UI.refreshMute(); }
      else if (on && k === 'Enter') UI.onConfirm && UI.onConfirm();
      else if (on && (k === 'b' || k === 'B')) { registerBasketTap(); }
      else return;
      if (['ArrowLeft','ArrowRight','ArrowUp','ArrowDown',' ','q','Q','e','E'].indexOf(k) >= 0) e.preventDefault();
    };
    window.addEventListener('keydown', (e) => { if (!e.repeat) down(e, true); });
    window.addEventListener('keyup', (e) => down(e, false));
  },
  _yawKey(which, on) {
    const now = performance.now() * 0.001;
    if (which === 'q') {
      if (on && !this._qDown) this._qT = now;
      if (!on && this._qDown) {
        if (now - this._qT < CAM_TAP) this.yawSnap -= 1;
        else this.yawReleaseSnap = true;
      }
      this._qDown = on ? 1 : 0;
    } else {
      if (on && !this._eDown) this._eT = now;
      if (!on && this._eDown) {
        if (now - this._eT < CAM_TAP) this.yawSnap += 1;
        else this.yawReleaseSnap = true;
      }
      this._eDown = on ? 1 : 0;
    }
    this._syncKbYaw();
  },
  _syncKbYaw() {
    const now = performance.now() * 0.001;
    let v = 0;
    if (this._qDown && now - this._qT >= CAM_TAP) v -= 1;
    if (this._eDown && now - this._eT >= CAM_TAP) v += 1;
    this.kbYaw = v;
  },
  _deadzone(dx, dy) {
    const m = Math.hypot(dx, dy);
    if (m < STICK_DEAD || m < 1e-6) return { x: 0, z: 0 };
    const t = (m - STICK_DEAD) / (1 - STICK_DEAD);
    return { x: (dx / m) * t, z: (dy / m) * t };
  },
  _uiBlockers() {
    return '#slashBtn, #spinBtn, #btnPause, #btnMute, #btnMuteTitle, #camLeft, #camRight, #camBtns, #skipHint, #cNext, #cTitle, .screen, .roundBtn, .pill, .tbtn';
  },
  onButtons(t) {
    const el = document.elementFromPoint(t.clientX, t.clientY);
    if (!el || !el.closest) return false;
    return !!el.closest(this._uiBlockers());
  },
  initTouch() {
    const pad = $('pad'), knob = $('padKnob'), zone = $('stickZone');
    let id = null, cx = 0, cy = 0;
    const rad = () => STICK_RADIUS;
    const safe = () => {
      const cs = getComputedStyle(document.documentElement);
      const n = (v, d) => { const x = parseFloat(cs.getPropertyValue(v)); return Number.isFinite(x) ? x : d; };
      return { l: n('--sl', 12), r: n('--sr', 12), t: n('--st', 8), b: n('--sb', 10) };
    };
    const hide = () => {
      id = null; this.stickOn = false; this.padX = 0; this.padZ = 0;
      knob.style.transform = '';
      pad.classList.remove('show');
    };
    const place = (px, py) => {
      const R = rad();
      const s = safe();
      const w = window.innerWidth, h = window.innerHeight;
      cx = clamp(px, s.l + R, Math.min(w * 0.5, w - s.r - R));
      cy = clamp(py, s.t + R, h - s.b - R);
      pad.style.width = (R * 2) + 'px';
      pad.style.height = (R * 2) + 'px';
      pad.style.left = (cx - R) + 'px';
      pad.style.top = (cy - R) + 'px';
      pad.style.bottom = 'auto';
      pad.style.right = 'auto';
      pad.classList.add('show');
      this.stickOn = true; this.stickCx = cx; this.stickCy = cy;
    };
    const set = (px, py) => {
      const R = rad();
      let dx = (px - cx) / R, dy = (py - cy) / R;
      const m = Math.hypot(dx, dy);
      if (m > 1) { dx /= m; dy /= m; }
      const v = this._deadzone(dx, dy);
      this.padX = v.x; this.padZ = v.z;
      const travel = R - 22;
      knob.style.transform = 'translate(' + (dx * travel).toFixed(1) + 'px,' + (dy * travel).toFixed(1) + 'px)';
    };
    const inLeft = (t) => t.clientX < window.innerWidth * 0.5;
    const start = (e) => {
      if (Game.state !== 'play') return;
      if (id != null) return;
      for (const t of e.changedTouches) {
        if (!inLeft(t) || this.onButtons(t)) continue;
        e.preventDefault();
        id = t.identifier;
        place(t.clientX, t.clientY);
        set(t.clientX, t.clientY);
        break;
      }
    };
    const move = (e) => {
      if (id == null) return;
      for (const t of e.changedTouches) if (t.identifier === id) {
        e.preventDefault();
        set(t.clientX, t.clientY);
        break;
      }
    };
    const end = (e) => {
      if (id == null) return;
      for (const t of e.changedTouches) if (t.identifier === id) {
        e.preventDefault();
        hide();
        break;
      }
    };
    const opts = { passive: false };
    const root = zone || document.getElementById('app');
    root.addEventListener('touchstart', start, opts);
    window.addEventListener('touchmove', move, opts);
    window.addEventListener('touchend', end, opts);
    window.addEventListener('touchcancel', end, opts);
    const hold = (el, edgeKey, holdKey) => {
      const d = (e) => { e && e.preventDefault(); if (!this[holdKey]) this[edgeKey] = true; if (edgeKey === 'slashEdge' && e && e.type && e.type.indexOf('touch') === 0) this.slashFromTouch = true; this[holdKey] = true; el.classList.add('on'); };
      const u = (e) => { e && e.preventDefault(); this[holdKey] = false; el.classList.remove('on'); };
      el.addEventListener('touchstart', d, { passive: false }); el.addEventListener('touchend', u, { passive: false }); el.addEventListener('touchcancel', u, { passive: false });
      el.addEventListener('mousedown', d); window.addEventListener('mouseup', () => { if (el.classList.contains('on')) u(); });
    };
    hold($('slashBtn'), 'slashEdge', 'slash');
    hold($('spinBtn'), 'spinEdge', 'spin');
    document.addEventListener('touchmove', (e) => { if (e.target.closest && e.target.closest('#touch')) e.preventDefault(); }, { passive: false });
  },
  initOrbit() {
    const self = this;
    let oid = null, lastX = 0, moved = 0, mouse = false;
    const inRight = (x) => x >= window.innerWidth * 0.5;
    const startAt = (x, y, id) => {
      oid = id; lastX = x; moved = 0; mouse = (id === 'mouse');
    };
    const moveAt = (x) => {
      const dx = x - lastX;
      lastX = x;
      moved += Math.abs(dx);
      // Drag right looks right (camera orbits left of the knight, yaw increases).
      self.swipeDelta += dx * CAM_SWIPE;
    };
    const endAt = () => {
      if (oid == null) return;
      if (moved > 6) self.yawReleaseSnap = true;
      oid = null; mouse = false; moved = 0;
    };
    const opts = { passive: false };
    window.addEventListener('touchstart', (e) => {
      if (Game.state !== 'play') return;
      if (oid != null) return;
      for (const t of e.changedTouches) {
        if (!inRight(t.clientX) || self.onButtons(t)) continue;
        e.preventDefault();
        startAt(t.clientX, t.clientY, t.identifier);
        break;
      }
    }, opts);
    window.addEventListener('touchmove', (e) => {
      if (oid == null || mouse) return;
      for (const t of e.changedTouches) if (t.identifier === oid) {
        e.preventDefault();
        moveAt(t.clientX);
        break;
      }
    }, opts);
    const te = (e) => {
      if (oid == null || mouse) return;
      for (const t of e.changedTouches) if (t.identifier === oid) { e.preventDefault(); endAt(); break; }
    };
    window.addEventListener('touchend', te, opts);
    window.addEventListener('touchcancel', te, opts);

    const zone = $('orbitZone') || $('app');
    zone.addEventListener('mousedown', (e) => {
      if (Game.state !== 'play') return;
      if (e.button !== 0) return;
      if (!inRight(e.clientX) || self.onButtons(e)) return;
      e.preventDefault();
      startAt(e.clientX, e.clientY, 'mouse');
    });
    window.addEventListener('mousemove', (e) => {
      if (oid !== 'mouse') return;
      e.preventDefault();
      moveAt(e.clientX);
    });
    window.addEventListener('mouseup', () => { if (oid === 'mouse') endAt(); });

    const bindBtn = (el, dir) => {
      if (!el) return;
      const press = (e) => {
        e && e.preventDefault();
        el.classList.add('on');
        const now = performance.now() * 0.001;
        if (dir < 0) { if (!self._btnL) self._btnLT = now; self._btnL = 1; }
        else { if (!self._btnR) self._btnRT = now; self._btnR = 1; }
      };
      const release = (e) => {
        e && e.preventDefault();
        el.classList.remove('on');
        const now = performance.now() * 0.001;
        if (dir < 0 && self._btnL) {
          if (now - self._btnLT < CAM_TAP) self.yawSnap -= 1;
          else self.yawReleaseSnap = true;
          self._btnL = 0;
        }
        if (dir > 0 && self._btnR) {
          if (now - self._btnRT < CAM_TAP) self.yawSnap += 1;
          else self.yawReleaseSnap = true;
          self._btnR = 0;
        }
      };
      el.addEventListener('touchstart', press, { passive: false });
      el.addEventListener('touchend', release, { passive: false });
      el.addEventListener('touchcancel', release, { passive: false });
      el.addEventListener('mousedown', press);
      window.addEventListener('mouseup', () => { if (el.classList.contains('on')) release(); });
    };
    bindBtn($('camLeft'), -1);
    bindBtn($('camRight'), 1);
  },
  _syncBtnYaw() {
    const now = performance.now() * 0.001;
    let v = 0;
    if (this._btnL && now - this._btnLT >= CAM_TAP) v -= 1;
    if (this._btnR && now - this._btnRT >= CAM_TAP) v += 1;
    this.btnYaw = v;
  },
  initPad() {
    const self = this;
    window.addEventListener('gamepadconnected', () => { self.gpHave = true; UI.toast('Controller connected'); });
    window.addEventListener('gamepaddisconnected', () => {
      const L = navigator.getGamepads ? navigator.getGamepads() : [];
      if (![...L].some((g) => g && g.connected)) { self.gpHave = false; self.gpActive = false; self.gpX = 0; self.gpZ = 0; self.gpYaw = 0; document.body.classList.remove('gp'); UI.toast('Controller disconnected'); }
    });
    window.addEventListener('touchstart', () => { if (self.gpActive) { self.gpActive = false; document.body.classList.remove('gp'); } }, { capture: true, passive: true });
  },
  pollPad() {
    let gp = null;
    try { const L = navigator.getGamepads ? navigator.getGamepads() : []; for (let i = 0; i < L.length; i++) if (L[i] && L[i].connected) { gp = (L[i].mapping === 'standard' || !gp) ? L[i] : gp; } } catch (e) { return; }
    if (!gp) return;
    const B = gp.buttons || [];
    const pr = (i) => { const x = B[i]; return !!x && (typeof x === 'object' ? (x.pressed || x.value > 0.5) : x > 0.5); };
    const now = []; for (let i = 0; i < 17; i++) now[i] = pr(i);
    const edge = (i) => now[i] && !this.prevBtn[i];
    const ax = (gp.axes && gp.axes[0]) || 0, ay = (gp.axes && gp.axes[1]) || 0;
    const v = this._deadzone(ax, ay);
    let sx = v.x, sz = v.z;
    if (now[14]) sx = -1; if (now[15]) sx = 1; if (now[12]) sz = -1; if (now[13]) sz = 1;
    const rx = (gp.axes && gp.axes.length > 2) ? (gp.axes[2] || 0) : 0;
    const ry = (gp.axes && gp.axes.length > 3) ? (gp.axes[3] || 0) : 0;
    const rv = this._deadzone(rx, ry);
    let used = Math.hypot(ax, ay) > 0.35 || Math.hypot(rx, ry) > 0.35; for (let i = 0; i < 16; i++) if (now[i]) used = true;
    if (used) { this.gpActive = true; document.body.classList.add('gp'); this.gpHave = true; }
    this.gpX = this.gpActive ? sx : 0; this.gpZ = this.gpActive ? sz : 0;
    if (this.gpActive) {
      this.gpYaw = rv.x;
      if (this._gpStickOn && Math.abs(rv.x) < 1e-4) this.yawReleaseSnap = true;
      this._gpStickOn = Math.abs(rv.x) > 1e-4;
      if (edge(0)) this.slashEdge = true;
      if (edge(2) || edge(5)) this.spinEdge = true;
      if (edge(4)) this.yawSnap -= 1; // LB: snap 45° left
      if (edge(7)) this.yawSnap += 1; // RT: snap 45° right (RB stays spin)
      if (edge(3)) registerBasketTap(); // Y / Triangle: basket easter-egg tap
      if (edge(9)) UI.onPause && UI.onPause();
      if (edge(0) && !document.body.classList.contains('inplay')) UI.onConfirm && UI.onConfirm();
      if (edge(1)) UI.onBack && UI.onBack();
    } else {
      this.gpYaw = 0;
    }
    this.prevBtn = now;
  },
  initSecret() {
    const go = (x, y, e) => {
      if (typeof hitPicnicBasket !== 'function') return false;
      if (Game.state !== 'play') return false;
      if (this.onButtons({ clientX: x, clientY: y })) return false;
      if (!hitPicnicBasket(x, y)) return false;
      if (e) { e.preventDefault(); e.stopPropagation(); }
      registerBasketTap();
      return true;
    };
    window.addEventListener('pointerdown', (e) => {
      if (e.button != null && e.button !== 0) return;
      go(e.clientX, e.clientY, e);
    }, { capture: true });
    window.addEventListener('touchstart', (e) => {
      const t = e.changedTouches && e.changedTouches[0];
      if (t) go(t.clientX, t.clientY, e);
    }, { capture: true, passive: false });
  },
  poll() {
    this.pollPad();
    this._syncKbYaw();
    this._syncBtnYaw();
    this.x = clamp(this.kbX + this.padX + this.gpX, -1, 1);
    this.z = clamp(this.kbZ + this.padZ + this.gpZ, -1, 1);
    const m = Math.hypot(this.x, this.z); if (m > 1) { this.x /= m; this.z /= m; }
    const se = this.slashEdge, sp = this.spinEdge; this.slashEdge = false; this.spinEdge = false;
    return { x: this.x, z: this.z, slashEdge: se, spinEdge: sp };
  },
  consumeCam() {
    this._syncKbYaw();
    this._syncBtnYaw();
    const rate = clamp(this.kbYaw + this.btnYaw + this.gpYaw, -1, 1);
    const snap = this.yawSnap;
    const release = this.yawReleaseSnap;
    const swipe = this.swipeDelta;
    this.yawSnap = 0;
    this.yawReleaseSnap = false;
    this.swipeDelta = 0;
    return { rate, snap, release, swipe };
  }
};
