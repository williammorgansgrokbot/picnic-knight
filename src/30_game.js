/* Picnic Knight — miniature knight, giant picnic, 3D walking, juicy kills */
const WORLD = 16;
const FOOD_MAX = 100;
const KNIGHT_H = 0.82;
const KNIGHT_WALK = 0.70;
const KNIGHT_RUN = 1.52;
const KNIGHT_RAD = 0.16;
const MOVE_ACCEL_T = 0.15;
const CAM_YAW = 0;
const SLASH_TIME = 0.30, SLASH_RANGE = 1.02, SLASH_ARC = Math.PI * 150 / 180, ANT_HIT_R = 0.22;
const SPIN_TIME = 0.42, SPIN_RANGE = 1.22, SPIN_CD = 1.65;
const ANT_H = 0.48;
const BEETLE_H = 0.56;
const WASP_H = 0.64;
const WASP_HOVER = 0.70;
const BOSS_H = 1.08;
const ANT_HP_NIBBLE = 2.38;      // was 2.8  (~15% slower bites)
const BEETLE_NIBBLE = 2.72;      // was 3.2
const WASP_NIBBLE = 2.04;        // was 2.4
const BOSS_WINDOW = 22;          // was 42; last ~24% of a 90s round
const PLAY_RADIUS = 6.5;
const HITSTOP = 0.072;
const CAM_DIST = 3.25;
const CAM_H = 2.22;
const CAM_LOOK_Y = 0.48;
const ROUND_TIME = 90;          // was 180 (1.5-minute rounds)
const STEAL_DUR = 5.15;
// Emma keeps her established height. Stormy is about half as tall (Bill:
// the Aussie is really about half Emma's size). This replaces the old
// Emma = 1.1× Stormy rule for this game.
const EMMA_H = 2.805;
const STORMY_H = EMMA_H * 0.55; // 1.54275
const SAUSAGE = { x: 0.12, z: 1.18, h: 0.62, r: 0.46 };
// Two picnickers sit on the grass just beyond the blanket (~6.6u square,
// edges near ±3.4). Placed opposite each other outside PLAY_RADIUS so one
// is usually in the far background of any camera orbit.
const WATCHERS = [
  { id: 'woman', x: 4.08, z: -1.50, h: 1.38, prefix: 'watcher_woman_' },
  { id: 'man',   x: -3.58, z: -0.85, h: 1.36, prefix: 'watcher_man_' }
];
const BEAR_H = 1.42;
const BEAR_POP = 0.42;
const BEAR_DANCE = 5.0;
const BEAR_DUCK = 0.48;

const FOOD = { x: -1.15, z: -0.25, h: 0.75, r: 0.4125 };
const FOOD_EAT_R = 0.435; // was 0.58; 75% so ants still gather on the smaller sandwich
// Pie sprite world width = 0.80 * (190/147) = 1.034. Basket opening is ~0.82 of
// its sprite width (cartoon rim/walls). Scale so that opening is ~1.30× the pie
// (inside the 1.25–1.35 band), height matched. Same world size for the raided
// variant (basket_bitten.png) if/when it is shown.
const BASKET_H = 1.53;
const BASKET_R = 0.80;
const FOOD_ITEMS = [
  { id: 'sandwich', intact: 'sandwich_intact.png', bitten: 'sandwich_bitten.png', x: -1.15, z: -0.25, h: 0.75, r: 0.4125, eatR: 0.435, max: 22 },
  { id: 'pie', intact: 'pie_intact.png', bitten: 'pie_bitten.png', x: -2.50, z: 0.95, h: 0.80, r: 0.48, eatR: 0.50, max: 22 },
  { id: 'cookies', intact: 'cookies_intact.png', bitten: 'cookies_bitten.png', x: 0.90, z: 0.58, h: 0.52, r: 0.40, eatR: 0.42, max: 16 },
  { id: 'melon', intact: 'watermelon_intact.png', bitten: 'watermelon_bitten.png', x: 2.30, z: 1.02, h: 0.82, r: 0.44, eatR: 0.46, max: 18 },
  { id: 'basket', intact: 'basket_intact.png', bitten: 'basket_bitten.png', x: 1.75, z: -1.50, h: BASKET_H, r: BASKET_R, eatR: BASKET_R + 0.05, max: 22 }
];
const DECOS = FOOD_ITEMS.filter((f) => f.id !== 'sandwich').map((f) => [f.intact, f.x, f.z, f.h, f.r]);

const Game = {
  state: 'boot',
  score: 0, wave: 0, round: 1, food: FOOD_MAX, t: 0, waveT: 0, spawnLeft: 0,
  timeLeft: ROUND_TIME, bannerT: 0,
  knight: { x: 0.45, z: 1.90, vx: 0, vz: 0, yaw: 0, face: 1, view: 'back', anim: 'idle', at: 0, slashT: 0, spinT: 0, spinCd: 0, speed: 0 },
  foodPos: { x: FOOD.x, z: FOOD.z },
  foods: [],
  ants: [],
  fx: [],
  hitStop: 0,
  shake: 0,
  shakeAmp: 0,
  lastNibbleSnd: 0,
  lastBuzzSnd: 0,
  _nextArm: 0,
  spawnQueue: [],
  steal: null,
  titleT: 0,
  boss: null,
  bossDone: false,
  newBest: false,
  lastBonus: 0,
  basketTaps: [],
  bear: { on: false, t: 0 }
};

const UI = {
  onPause: null, onConfirm: null, onBack: null,
  toastT: 0,
  init() {
    const A = window.__ASSETS || {};
    const logo = $('logo'); if (logo) logo.src = A['logo.png'] || 'art/logo.png';
    this.refreshMute();
    this.refreshBest();
    const bindMute = (id) => $(id) && $(id).addEventListener('click', (e) => { e.stopPropagation(); Snd.init(); Snd.setMuted(!Snd.muted); this.refreshMute(); Snd.click(); });
    bindMute('btnMute'); bindMute('btnMuteTitle');
    $('btnPlay').addEventListener('click', () => this.startFromTitle());
    $('title').addEventListener('click', (e) => { if (e.target.closest && e.target.closest('#btnMuteTitle')) return; });
    $('btnPause').addEventListener('click', () => this.togglePause());
    $('pResume').addEventListener('click', () => { Snd.click(); this.resume(); });
    $('pRestart').addEventListener('click', () => { Snd.click(); this.restart(); });
    $('pQuit').addEventListener('click', () => { Snd.click(); this.toTitle(); });
    $('lAgain').addEventListener('click', () => { Snd.click(); this.restart(); });
    $('lTitle').addEventListener('click', () => { Snd.click(); this.toTitle(); });
    $('cNext').addEventListener('click', () => { Snd.click(); this.nextRound(); });
    $('cTitle').addEventListener('click', () => { Snd.click(); this.toTitle(); });
    $('skipHint').addEventListener('click', (e) => { e.stopPropagation(); this.skipSteal(); });
    this.onPause = () => { if (Game.state === 'play' || Game.state === 'pause') this.togglePause(); };
    this.onConfirm = () => {
      if (Game.state === 'title') this.startFromTitle();
      else if (Game.state === 'steal') this.skipSteal();
      else if (Game.state === 'pause') this.resume();
      else if (Game.state === 'lose') this.restart();
      else if (Game.state === 'clear') this.nextRound();
    };
    this.onBack = () => {
      if (Game.state === 'steal') this.skipSteal();
      else if (Game.state === 'pause') this.resume();
      else if (Game.state === 'lose' || Game.state === 'clear') this.toTitle();
    };
  },
  refreshMute() {
    const h = Snd.muted ? ICON_OFF : ICON_ON;
    ['btnMute', 'btnMuteTitle'].forEach((id) => { if ($(id)) $(id).innerHTML = h; });
  },
  show(id, on) { const el = $(id); if (el) el.classList.toggle('show', !!on); },
  startFromTitle() {
    Snd.init(); Snd.click(); Snd.startMusic();
    this.beginPlay();
  },
  resetKnight() {
    const k = Game.knight;
    k.x = 0.45; k.z = 1.90; k.vx = 0; k.vz = 0;
    k.yaw = 0; k.face = 1; k.view = 'back';
    k.anim = 'idle'; k.at = 0; k.slashT = 0; k.spinT = 0; k.spinCd = 0; k.speed = 0;
  },
  resetFoods() {
    Game.foods = FOOD_ITEMS.map((f) => Object.assign({}, f, { hp: f.max }));
    Game.food = FOOD_MAX;
    if (World.foodSprs) syncFoodSprites();
  },
  refreshBest() {
    const best = store.get('best', 0);
    const set = (id, v) => { const el = $(id); if (el) el.textContent = v; };
    set('bestScore', 'Best ' + best);
    set('clearBest', String(best));
    set('loseBest', String(best));
  },
  recordScore() {
    const best = store.get('best', 0);
    if (Game.score > best) {
      store.set('best', Game.score);
      Game.newBest = true;
    }
    this.refreshBest();
  },
  beginPlay() {
    World.reset();
    Game.score = 0; Game.wave = 0; Game.round = 1; Game.food = FOOD_MAX; Game.t = 0;
    Game.timeLeft = ROUND_TIME; Game.bannerT = 0;
    Game.boss = null; Game.bossDone = false; Game.newBest = false; Game.lastBonus = 0;
    this.resetKnight();
    this.resetFoods();
    Game.ants = []; Game.spawnLeft = 0; Game.spawnQueue = []; Game.waveT = 0; Game.fx = [];
    Game.hitStop = 0; Game.shake = 0; Game._nextArm = 0;
    World.camYaw = CAM_YAW;
    World.camYawTarget = CAM_YAW;
    Input.kbYaw = 0; Input.btnYaw = 0; Input.gpYaw = 0;
    Input.yawSnap = 0; Input.swipeDelta = 0; Input.yawReleaseSnap = false;
    Input._qDown = Input._eDown = Input._btnL = Input._btnR = 0;
    document.body.classList.add('inplay');
    document.body.classList.remove('pause','lose','clear','steal');
    this.show('title', false); this.show('pause', false); this.show('lose', false);
    this.show('clear', false); this.show('loading', false);
    this.startSteal();
    this.hud();
  },
  startSteal() {
    const who = (Game.round % 2 === 1) ? 'stormy' : 'emma';
    Game.state = 'steal';
    hideBear();
    Game.steal = { t: 0, dur: STEAL_DUR, who, grabbed: false, barked: false, scampered: false, sausageOn: true };
    Game.timeLeft = ROUND_TIME;
    Game.bannerT = 0;
    Game.ants = []; Game.spawnLeft = 0; Game.waveT = 99; Game._nextArm = 99; Game.fx = [];
    this.resetKnight();
    const k = Game.knight;
    k.x = 1.15; k.z = 2.18; k.yaw = -0.85; k.anim = 'idle'; k.at = 0;
    document.body.classList.add('steal');
    document.body.classList.remove('pause','lose','clear');
    this.show('clear', false);
    this.showBanner(false);
    World.showSausage(true);
    World.placeDogsForSteal(0, who, false);
    World.lockStealCam();
    if (Snd.scamper) Snd.scamper();
    loop.frozen = false;
    this.hud();
  },
  skipSteal() {
    if (Game.state !== 'steal') return;
    this.endSteal();
  },
  endSteal() {
    if (Game.state !== 'steal') return;
    this.startTimedRound();
  },
  startTimedRound() {
    // TODO: ant-captain picnic boss after later rounds. Hook only — not in this build.
    Game.boss = null; Game.bossDone = false;
    maybeStartBoss();
    Game.state = 'play';
    Game.steal = null;
    Game.timeLeft = ROUND_TIME;
    Game.bannerT = 1.85;
    Game.ants = []; Game.spawnLeft = 0; Game.waveT = 0; Game._nextArm = 0; Game.fx = [];
    Input.slashEdge = false; Input.spinEdge = false; Input.slash = false; Input.spin = false;
    document.body.classList.remove('steal','clear','pause','lose');
    document.body.classList.add('inplay');
    World.hideDogs();
    World.showSausage(false);
    World.camLock = 0; World.lookLock = null;
    World.camYaw = CAM_YAW; World.camYawTarget = CAM_YAW;
    this.resetKnight();
    World.snapCam();
    this.showBanner(true, 'ROUND START');
    if (Snd.roundStart) Snd.roundStart();
    loop.frozen = false;
    this.nextWave();
    this.hud();
  },
  nextRound() {
    Game.round += 1;
    Game.t = 0;
    Game.bannerT = 0;
    Game.boss = null; Game.bossDone = false; Game.lastBonus = 0;
    this.resetFoods();
    Game.ants = []; Game.spawnLeft = 0; Game.waveT = 0; Game.fx = [];
    Game.hitStop = 0; Game.shake = 0; Game._nextArm = 0;
    this.resetKnight();
    this.show('clear', false);
    document.body.classList.remove('clear','lose','pause');
    World.reset();
    World.camYaw = CAM_YAW;
    World.camYawTarget = CAM_YAW;
    this.startSteal();
    this.hud();
  },
  showBanner(on, text) {
    const el = $('banner');
    if (!el) return;
    if (text) el.textContent = text;
    el.classList.toggle('show', !!on);
  },
  roundClear() {
    if (Game.state !== 'play') return;
    Game.state = 'clear';
    Game.timeLeft = 0;
    const pct = clamp(Game.food / FOOD_MAX, 0, 1);
    const hold = Math.round(pct * (80 + 25 * Game.round));
    Game.score += hold;
    Game.lastBonus = hold;
    this.recordScore();
    Game.ants = Game.ants.filter((a) => a.type === 'boss' && !a.alive);
    Game.spawnLeft = 0;
    hideBear();
    document.body.classList.add('clear');
    document.body.classList.remove('steal','pause');
    this.showBanner(false);
    const pctN = Math.round(pct * 100);
    $('clearScore').textContent = String(Game.score);
    $('clearPicnic').textContent = pctN + '%';
    let sub = 'Round ' + Game.round + ' — picnic bonus +' + hold + '.';
    if (Game.bossDone) sub += ' Captain down!';
    else if (Game.boss && Game.boss.alive) sub += ' The captain got away.';
    if (Game.newBest) sub += ' New best!';
    $('clearSub').textContent = sub;
    this.show('clear', true);
    if (Snd.roundClear) Snd.roundClear();
    this.hud();
  },
  nextWave() {
    Game.wave += 1;
    const n = Math.max(2, Math.min(Math.round((2 + Game.wave + Math.max(0, Game.round - 1)) * 0.82), 7));
    Game.spawnQueue = makeWaveQueue(Game.wave, Game.round, n);
    Game.spawnLeft = Game.spawnQueue.length;
    Game.waveT = 0.25;
    Snd.wave();
    this.hud();
  },
  togglePause() {
    if (Game.state === 'play') { Game.state = 'pause'; document.body.classList.add('pause'); this.show('pause', true); }
    else if (Game.state === 'pause') this.resume();
  },
  resume() { if (Game.state !== 'pause') return; Game.state = 'play'; document.body.classList.remove('pause'); this.show('pause', false); },
  restart() { this.show('pause', false); this.show('lose', false); this.beginPlay(); },
  toTitle() {
    Game.state = 'title'; document.body.classList.remove('inplay','pause','lose','steal','clear');
    this.show('pause', false); this.show('lose', false); this.show('clear', false); this.show('title', true);
    this.showBanner(false);
    this.resetKnight();
    Game.ants = []; Game.fx = []; Game.steal = null; Game.bannerT = 0;
    Game.boss = null; Game.titleT = 0;
    hideBear();
    World.reset();
    World.showSausage(false);
    World.camHome();
    this.refreshBest();
  },
  lose() {
    if (Game.state !== 'play') return;
    Game.state = 'lose'; document.body.classList.add('lose'); Snd.lose();
    hideBear();
    this.recordScore();
    $('loseScore').textContent = Game.score; $('loseWaves').textContent = String(Game.wave);
    const sub = $('loseSub');
    if (sub) sub.textContent = Game.newBest ? 'The bugs got the picnic. New best!' : 'The bugs got the picnic.';
    this.show('lose', true);
  },
  hud() {
    $('waveNum').textContent = Game.wave || 1;
    $('scoreNum').textContent = Game.score;
    const p = clamp(Game.food / FOOD_MAX, 0, 1);
    $('meterFill').style.width = (p * 100).toFixed(1) + '%';
    $('meterWrap').classList.toggle('low', p < 0.45 && p >= 0.22);
    $('meterWrap').classList.toggle('crit', p < 0.22);
    const secs = Math.max(0, Math.ceil(Game.timeLeft - 1e-6));
    const mm = Math.floor(secs / 60), ss = secs % 60;
    const tEl = $('timerNum');
    if (tEl) tEl.textContent = mm + ':' + (ss < 10 ? '0' : '') + ss;
    const tp = $('timerPanel');
    if (tp) {
      tp.classList.toggle('warn', Game.state === 'play' && Game.timeLeft <= 20 && Game.timeLeft > 8);
      tp.classList.toggle('crit', Game.state === 'play' && Game.timeLeft <= 8);
    }
    const cd = Game.knight.spinCd / SPIN_CD;
    $('spinBtn').classList.toggle('cd', cd > 0 && Game.knight.spinT <= 0);
    $('spinCd').style.transform = 'scaleY(' + clamp(cd, 0, 1).toFixed(3) + ')';
    const bw = $('bossWrap'), bf = $('bossFill');
    const b = Game.boss;
    const showB = !!(b && b.alive && (Game.state === 'play' || Game.state === 'pause'));
    if (bw) bw.classList.toggle('hidden', !showB);
    if (showB && bf) {
      const p = clamp(b.hp / Math.max(1, b.hpMax), 0, 1);
      bf.style.width = (p * 100).toFixed(1) + '%';
      if (bw) bw.classList.toggle('warn', p < 0.35);
    }
  },
  toast(msg) {
    let el = $('toast');
    if (!el) { el = document.createElement('div'); el.id = 'toast'; document.getElementById('app').appendChild(el); }
    el.textContent = msg; el.classList.add('show');
    clearTimeout(this.toastT); this.toastT = setTimeout(() => el.classList.remove('show'), 2200);
  },
  setArrow(on, side, nx, ny) {
    const el = $('arrow');
    el.classList.toggle('hidden', !on);
    el.classList.remove('left', 'top', 'bottom');
    el.style.left = el.style.right = el.style.top = el.style.bottom = el.style.transform = '';
    if (!on) return;
    if (side) el.classList.add(side);
    const px = clamp(((nx || 0) + 1) / 2, 0.16, 0.84);
    const py = clamp((1 - (ny || 0)) / 2, 0.2, 0.7);
    if (side === 'top' || side === 'bottom') {
      let x = px * 100;
      if (x > 38 && x < 62) x = px < 0.5 ? 28 : 72;
      el.style.left = x.toFixed(2) + '%';
      el.style.transform = 'translateX(-50%)';
    } else {
      let y = py * 100;
      if (y > 40 && y < 60) y = py < 0.5 ? 30 : 66;
      y = clamp(y, 22, 68);
      el.style.top = y.toFixed(2) + '%';
      el.style.transform = 'translateY(-50%)';
    }
  }
};

const World = {
  renderer: null, scene: null, camera: null, tex: {},
  knightSpr: null, foodSpr: null, antSpr: [], fxSpr: [], ground: null,
  obstacles: [],
  cam: { x: 0, y: CAM_H, z: CAM_DIST },
  camYaw: 0, camYawTarget: 0, camLock: 0,
  ready: false,
  asset(name) { return (window.__ASSETS && window.__ASSETS[name]) || ('art/' + name); },
  loadTex(name) {
    return new Promise((res) => {
      const img = new Image();
      img.onload = () => {
        const t = new THREE.Texture(img);
        if (t.colorSpace !== undefined) t.colorSpace = THREE.SRGBColorSpace;
        t.minFilter = THREE.LinearMipmapLinearFilter; t.magFilter = THREE.LinearFilter;
        t.needsUpdate = true; this.tex[name] = t; res(t);
      };
      img.onerror = () => { console.error('tex fail', name); res(null); };
      img.src = this.asset(name);
    });
  },
  async init() {
    const canvas = $('gl');
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
    this.renderer.setClearColor(0x8ec8e8, 1);
    if (this.renderer.outputColorSpace !== undefined) this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x8ec8e8);
    this.scene.fog = new THREE.Fog(0x8aaa3a, 12, 28);
    this.camera = new THREE.PerspectiveCamera(40, 2, 0.1, 50);
    this.scene.add(new THREE.HemisphereLight(0xfff3d6, 0x4a6a32, 1.05));
    const sun = new THREE.DirectionalLight(0xffe7b0, 0.7); sun.position.set(5, 8, 3); this.scene.add(sun);
    this.resize();
    window.addEventListener('resize', () => this.resize());
    const names = [
      'picnic_ground_wide.jpg', 'logo.png',
      'knight_idle_0.png','knight_idle_1.png','knight_idle_2.png',
      'knight_idle_front.png','knight_idle_side.png','knight_idle_back34.png','knight_idle_back.png',
      'knight_run_1.png','knight_run_3.png',
      'knight_run_front_0.png','knight_run_front_1.png',
      'knight_run_side_0.png','knight_run_side_1.png',
      'knight_run_back_0.png','knight_run_back_1.png',
      'knight_run_back34_0.png','knight_run_back34_1.png',
      'knight_run_34front_a.png','knight_run_34front_b.png',
      'knight_slash_0.png','knight_slash_1.png','knight_slash_2.png',
      'knight_spin_0.png','knight_spin_1.png','knight_spin_2.png',
      'ant_walk_0.png','ant_walk_1.png','ant_walk_2.png','ant_walk_3.png',
      'ant_nibble.png','ant_bonk.png','ant_down_0.png','ant_down_1.png',
      'fx_puff_0.png','fx_puff_1.png','fx_stars.png',
      'sandwich_intact.png','sandwich_bitten.png',
      'basket_intact.png','basket_bitten.png','pie_intact.png','pie_bitten.png',
      'cookies_intact.png','cookies_bitten.png','watermelon_intact.png','watermelon_bitten.png',
      'sausage_links.png',
      'stormy_run_0.png','stormy_run_1.png','stormy_run_2.png','stormy_grab.png',
      'emma_run_0.png','emma_run_1.png','emma_run_2.png','emma_grab.png',
      'stormy_sausage_0.png','stormy_sausage_1.png','stormy_sausage_2.png',
      'emma_sausage_0.png','emma_sausage_1.png','emma_sausage_2.png',
      'beetle_walk_0.png','beetle_walk_1.png','beetle_nibble.png','beetle_bonk.png','beetle_down.png',
      'wasp_fly_0.png','wasp_fly_1.png','wasp_dive.png','wasp_bonk.png','wasp_down.png',
      'boss_walk_0.png','boss_tele.png','boss_charge.png','boss_hurt.png','boss_down.png',
      'watcher_woman_0.png','watcher_woman_1.png','watcher_woman_2.png',
      'watcher_man_0.png','watcher_man_1.png','watcher_man_2.png',
      'bear_pop.png','bear_shimmy_0.png','bear_shimmy_1.png','bear_shimmy_2.png','bear_duck.png'
    ];
    await Promise.all(names.map((n) => this.loadTex(n)));
    this.buildGround();
    this.knightSpr = this.makeSprite('knight_idle_back.png', KNIGHT_H);
    this.scene.add(this.knightSpr.mesh); this.scene.add(this.knightSpr.blob);
    this.foodSprs = [];
    this.decos = [];
    this.obstacles = [];
    FOOD_ITEMS.forEach((f) => {
      const s = this.makeSprite(f.intact, f.h);
      this.place(s, f.x, f.z); this.scene.add(s.mesh); this.scene.add(s.blob);
      s.foodId = f.id;
      this.foodSprs.push(s);
      this.obstacles.push({ x: f.x, z: f.z, r: f.r, id: f.id });
      if (f.id !== 'sandwich') this.decos.push(s);
    });
    this.foodSpr = this.foodSprs.find((s) => s.foodId === 'sandwich') || this.foodSprs[0];
    this.sausageSpr = this.makeSprite('sausage_links.png', SAUSAGE.h);
    this.place(this.sausageSpr, SAUSAGE.x, SAUSAGE.z);
    this.sausageSpr.mesh.visible = false; this.sausageSpr.blob.visible = false;
    this.scene.add(this.sausageSpr.mesh); this.scene.add(this.sausageSpr.blob);
    this.stormySpr = this.makeSprite('stormy_run_0.png', STORMY_H);
    this.emmaSpr = this.makeSprite('emma_run_0.png', EMMA_H);
    [this.stormySpr, this.emmaSpr].forEach((s) => {
      s.mesh.visible = false; s.blob.visible = false;
      this.scene.add(s.mesh); this.scene.add(s.blob);
    });
    this.watcherSpr = WATCHERS.map((w, i) => {
      const s = this.makeSprite(w.prefix + '0.png', w.h);
      s.mesh.renderOrder = -2;
      s.blob.renderOrder = -3;
      this.place(s, w.x, w.z, 0);
      this.scene.add(s.mesh); this.scene.add(s.blob);
      s._phase = i * 1.15;
      return s;
    });
    this.bearSpr = this.makeSprite('bear_pop.png', BEAR_H);
    this.bearSpr.mesh.visible = false; this.bearSpr.blob.visible = false;
    this.bearSpr.mesh.renderOrder = 2;
    this.scene.add(this.bearSpr.mesh); this.scene.add(this.bearSpr.blob);
    this.camHome();
    this.ready = true;
  },
  buildGround() {
    const tex = this.tex['picnic_ground_wide.jpg'];
    tex.wrapS = tex.wrapT = THREE.ClampToEdgeWrapping;
    const mat = new THREE.MeshStandardMaterial({ map: tex, roughness: 0.95, metalness: 0 });
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(WORLD, WORLD), mat);
    mesh.rotation.x = -Math.PI / 2; mesh.position.y = 0;
    this.scene.add(mesh); this.ground = mesh;
  },
  makeSprite(texName, h) {
    const tex = this.tex[texName];
    const aspect = (tex && tex.image) ? tex.image.width / tex.image.height : 1;
    const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, alphaTest: 0.12 });
    // THREE.Sprite's vertex shader takes length(modelMatrix[0]), so scale.x
    // sign is ignored. Pass a flip uniform so left/right facing actually mirrors.
    const uFlip = { value: 1 };
    mat.userData.uFlip = uFlip;
    // Don't flip scale.x in the sprite vertex shader: length() already drops the
    // sign, and a negative scale reverses triangle winding so the sprite is culled.
    // Mirror UVs instead.
    mat.onBeforeCompile = (shader) => {
      shader.uniforms.uFlip = uFlip;
      shader.vertexShader = 'uniform float uFlip;\n' + shader.vertexShader.replace(
        '#include <uv_vertex>',
        '#include <uv_vertex>\n#ifdef USE_MAP\nif ( uFlip < 0.0 ) vMapUv.x = 1.0 - vMapUv.x;\n#endif'
      );
    };
    mat.customProgramCacheKey = () => 'pk-sprite-uvflip';
    mat.side = THREE.DoubleSide;
    const mesh = new THREE.Sprite(mat);
    mesh.center.set(0.5, 0);
    mesh.scale.set(h * aspect, h, 1);
    mesh.userData.h = h;
    const g = new THREE.PlaneGeometry(h * 0.55, h * 0.28);
    const bmat = new THREE.MeshBasicMaterial({ color: 0x1a1408, transparent: true, opacity: 0.26, depthWrite: false });
    const blob = new THREE.Mesh(g, bmat); blob.rotation.x = -Math.PI / 2; blob.position.y = 0.012;
    return { mesh, blob, h, name: texName, blobBaseH: h };
  },
  setSpriteTex(spr, name) {
    if (spr.name === name) return;
    const tex = this.tex[name]; if (!tex) return;
    spr.mesh.material.map = tex; spr.mesh.material.needsUpdate = true;
    const aspect = tex.image.width / tex.image.height;
    const sign = spr.mesh.scale.x < 0 ? -1 : 1;
    spr.mesh.scale.set(Math.abs(spr.h * aspect) * sign, spr.h, 1);
    spr.name = name;
    this.syncBlob(spr);
  },
  syncBlob(spr) {
    if (!spr || !spr.blob) return;
    const base = spr.blobBaseH || spr.h;
    if (!base) return;
    const k = spr.h / base;
    spr.blob.scale.set(k, k, 1);
  },
  setSpriteH(spr, h) {
    if (!spr) return;
    spr.h = h;
    const tex = spr.mesh.material.map;
    const aspect = (tex && tex.image) ? tex.image.width / tex.image.height : 1;
    const sign = spr.mesh.scale.x < 0 ? -1 : 1;
    spr.mesh.scale.set(Math.abs(h * aspect) * sign, h, 1);
    this.syncBlob(spr);
  },
  place(spr, x, z, y) {
    spr.mesh.position.set(x, y || 0, z);
    spr.blob.position.set(x, 0.012, z);
  },
  flip(spr, face) {
    const s = Math.abs(spr.mesh.scale.x);
    spr.mesh.scale.x = face < 0 ? -s : s;
    const u = spr.mesh.material && spr.mesh.material.userData && spr.mesh.material.userData.uFlip;
    if (u) u.value = face < 0 ? -1 : 1;
    spr.face = face < 0 ? -1 : 1;
  },
  showSausage(on) {
    if (!this.sausageSpr) return;
    this.sausageSpr.mesh.visible = !!on;
    this.sausageSpr.blob.visible = !!on;
    if (on) this.place(this.sausageSpr, SAUSAGE.x, SAUSAGE.z);
  },
  hideDogs() {
    [this.stormySpr, this.emmaSpr].forEach((s) => {
      if (!s) return;
      s.mesh.visible = false; s.blob.visible = false;
    });
    this.hideTitleAnts();
  },
  ensureTitleAnts(n) {
    if (!this.titleAntSpr) this.titleAntSpr = [];
    while (this.titleAntSpr.length < n) {
      const s = this.makeSprite('ant_walk_0.png', ANT_H);
      s.mesh.visible = false; s.blob.visible = false;
      this.scene.add(s.mesh); this.scene.add(s.blob);
      this.titleAntSpr.push(s);
    }
  },
  hideTitleAnts() {
    (this.titleAntSpr || []).forEach((s) => {
      s.mesh.visible = false; s.blob.visible = false;
    });
  },
  lockStealCam() {
    this.camLock = 99;
    this.camYaw = 0; this.camYawTarget = 0;
    this.cam.x = -0.35;
    this.cam.y = 2.62;
    this.cam.z = 6.45;
    this.lookLock = { x: 0.05, y: 0.70, z: 0.80 };
    this.camera.position.set(this.cam.x, this.cam.y, this.cam.z);
    this.camera.lookAt(this.lookLock.x, this.lookLock.y, this.lookLock.z);
  },
  placeDogsForSteal(t, who, grabbed) {
    const st = stealPose(t, who, grabbed);
    if (this.stormySpr) this.setSpriteH(this.stormySpr, STORMY_H);
    if (this.emmaSpr) this.setSpriteH(this.emmaSpr, EMMA_H);
    this._applyDog(this.stormySpr, st.stormy, 'stormy');
    this._applyDog(this.emmaSpr, st.emma, 'emma');
  },
  _applyDog(spr, pose, name) {
    if (!spr || !pose) return;
    spr.mesh.visible = !!pose.visible;
    spr.blob.visible = !!pose.visible;
    if (!pose.visible) return;
    const tex = pose.tex;
    this.setSpriteTex(spr, tex);
    this.place(spr, pose.x, pose.z, pose.y || 0);
    this.flip(spr, pose.face >= 0 ? 1 : -1);
  },
  resize() {
    const w = window.innerWidth, h = window.innerHeight;
    const pr = Math.min(2, window.devicePixelRatio || 1);
    this.renderer.setPixelRatio(pr);
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / Math.max(1, h);
    this.camera.updateProjectionMatrix();
  },
  camHome() {
    // Title: miniature knight visible left of the logo, beside the giant pie
    const k = Game.knight;
    k.x = -2.35; k.z = 1.35; k.yaw = 1.05;
    this.camYaw = 0.15;
    this.cam.x = -0.2;
    this.cam.y = 2.55;
    this.cam.z = 4.55;
    this.camera.position.set(this.cam.x, this.cam.y, this.cam.z);
    this.camera.lookAt(-0.4, 0.55, 0.35);
  },
  snapCam() {
    const k = Game.knight;
    this.cam.x = k.x - Math.sin(this.camYaw) * CAM_DIST;
    this.cam.y = CAM_H;
    this.cam.z = k.z + Math.cos(this.camYaw) * CAM_DIST;
    this.camera.position.set(this.cam.x, this.cam.y, this.cam.z);
    this.camera.lookAt(k.x, CAM_LOOK_Y, k.z);
  },
  snapYaw45(a) {
    const step = Math.PI / 4;
    return Math.round(a / step) * step;
  },
  applyCamTurn(dt) {
    if (dt <= 1e-8) return;
    if (Game.state !== 'play') { Input.consumeCam(); return; }
    const t = Input.consumeCam();
    if (t.swipe) {
      this.camYawTarget += t.swipe;
      this.camYaw += t.swipe * 0.85;
    }
    if (Math.abs(t.rate) > 0.01) {
      const d = t.rate * CAM_TURN * dt;
      this.camYawTarget += d;
      this.camYaw += d;
    }
    if (t.snap) {
      const cur = this.snapYaw45(this.camYawTarget);
      this.camYawTarget = cur + t.snap * (Math.PI / 4);
    }
    if (t.release) this.camYawTarget = this.snapYaw45(this.camYawTarget);
    this.camYaw = dampAngle(this.camYaw, this.camYawTarget, 14, dt);
  },
  updateCam(dt) {
    const k = Game.knight;
    if (Game.state === 'title') {
      this.camHome();
      return;
    }
    if (this.camLock > 0) {
      this.camLock -= dt;
      this.camera.position.set(this.cam.x, this.cam.y, this.cam.z);
      if (this.lookLock) this.camera.lookAt(this.lookLock.x, this.lookLock.y, this.lookLock.z);
      else this.camera.lookAt(k.x, CAM_LOOK_Y, k.z);
      return;
    }
    this.applyCamTurn(dt);
    const tx = k.x - Math.sin(this.camYaw) * CAM_DIST;
    const ty = CAM_H;
    const tz = k.z + Math.cos(this.camYaw) * CAM_DIST;
    this.cam.x = damp(this.cam.x, tx, 5.2, dt);
    this.cam.y = damp(this.cam.y, ty, 5.2, dt);
    this.cam.z = damp(this.cam.z, tz, 5.2, dt);
    let lx = k.x + Math.sin(this.camYaw) * 0.18;
    let lz = k.z - Math.cos(this.camYaw) * 0.18;
    let x = this.cam.x, y = this.cam.y, z = this.cam.z;
    if (Game.shake > 0) {
      const fall = Game.shake / 0.16;
      const a = Game.shakeAmp * fall;
      x += Math.sin(Game.t * 74) * a;
      y += Math.cos(Game.t * 91) * a * 0.6;
      z += Math.sin(Game.t * 63) * a * 0.5;
    }
    this.camera.position.set(x, y, z);
    this.camera.lookAt(lx, CAM_LOOK_Y, lz);
  },
  reset() {
    if (this.foodSprs) {
      FOOD_ITEMS.forEach((f, i) => {
        const s = this.foodSprs[i];
        if (!s) return;
        this.setSpriteTex(s, f.intact);
        this.place(s, f.x, f.z);
        s.mesh.material.opacity = 1;
      });
    }
    this.antSpr.forEach((s) => { this.scene.remove(s.mesh); this.scene.remove(s.blob); });
    this.antSpr = [];
    this.fxSpr.forEach((s) => { this.scene.remove(s.mesh); if (s.blob) this.scene.remove(s.blob); });
    this.fxSpr = [];
    this.hideDogs();
    this.hideTitleAnts();
    this.showSausage(false);
    this.camLock = 0; this.lookLock = null;
  },
  ensureAnts(n) {
    while (this.antSpr.length < n) {
      const s = this.makeSprite('ant_walk_0.png', ANT_H);
      s.mesh.visible = false; s.blob.visible = false;
      this.scene.add(s.mesh); this.scene.add(s.blob); this.antSpr.push(s);
    }
  },
  ensureFx(n) {
    while (this.fxSpr.length < n) {
      const s = this.makeSprite('fx_puff_0.png', 0.55);
      s.blob.visible = false;
      s.mesh.visible = false;
      this.scene.add(s.mesh);
      this.fxSpr.push(s);
    }
  },
  updateArrow() {
    if (Game.state !== 'play') { UI.setArrow(false); return; }
    const eaten = [];
    for (const a of Game.ants) {
      if (a.alive && a.state === 'eat' && a.targetId) {
        const f = (Game.foods || []).find((x) => x.id === a.targetId) || FOOD;
        eaten.push(f);
      }
    }
    if (!eaten.length) { UI.setArrow(false); return; }
    const f = eaten[0];
    const v = new THREE.Vector3(f.x, f.h * 0.6, f.z).project(this.camera);
    const off = v.z > 1 || v.x < -0.55 || v.x > 0.55 || v.y < -0.50 || v.y > 0.50;
    const under = true;
    if (!off || !under) { UI.setArrow(false); return; }
    let side = 'left';
    const ax = Math.abs(v.x), ay = Math.abs(v.y);
    if (ax >= ay) side = v.x > 0 ? '' : 'left';
    else side = v.y > 0 ? 'top' : 'bottom';
    UI.setArrow(true, side, v.x, v.y);
  }
};

function faceDir(yaw) { return { x: Math.sin(yaw), z: -Math.cos(yaw) }; }

// Painted run/walk art faces screen-right (scale.x > 0). Flip so the sprite
// faces its motion as seen on screen, including after a camera orbit.
function screenFace(vx, vz, prev) {
  let sx = 0;
  const cam = World.camera;
  if (cam) {
    cam.updateMatrixWorld();
    const e = cam.matrixWorld.elements;
    sx = (vx || 0) * e[0] + (vz || 0) * e[2];
  } else {
    const yaw = World.camYaw || 0;
    sx = (vx || 0) * Math.cos(yaw) + (vz || 0) * Math.sin(yaw);
  }
  if (Math.abs(sx) < 1e-4) return prev == null ? 1 : prev;
  return sx >= 0 ? 1 : -1;
}

function projectScreen(x, y, z) {
  const v = new THREE.Vector3(x, y, z);
  v.project(World.camera);
  return { x: (v.x * 0.5 + 0.5) * window.innerWidth, y: (-v.y * 0.5 + 0.5) * window.innerHeight, nx: v.x, ny: v.y };
}

function viewFromCamera(k) {
  const toCamX = World.cam.x - k.x, toCamZ = World.cam.z - k.z;
  const toCamYaw = Math.atan2(toCamX, -toCamZ);
  const rel = angDiff(toCamYaw, k.yaw);
  const a = Math.abs(rel);
  let view = 'front';
  if (a < Math.PI * 0.125) view = 'front';
  else if (a < Math.PI * 0.375) view = 'front34';
  else if (a < Math.PI * 0.625) view = 'side';
  else if (a < Math.PI * 0.875) view = 'back34';
  else view = 'back';
  const face = rel < 0 ? -1 : 1;
  return { view, face, rel };
}

function collideKnight(k) {
  for (let i = 0; i < World.obstacles.length; i++) {
    const o = World.obstacles[i];
    const dx = k.x - o.x, dz = k.z - o.z;
    const d = Math.hypot(dx, dz);
    const min = KNIGHT_RAD + o.r;
    if (d < min) {
      if (d < 1e-5) { k.x += min; continue; }
      const s = min / d;
      k.x = o.x + dx * s;
      k.z = o.z + dz * s;
    }
  }
  const r = Math.hypot(k.x, k.z);
  if (r > PLAY_RADIUS) { k.x *= PLAY_RADIUS / r; k.z *= PLAY_RADIUS / r; }
}

function hitRadius(ent) {
  if (!ent) return ANT_HIT_R;
  if (ent.type === 'boss') return 0.38;
  if (ent.type === 'beetle') return 0.28;
  if (ent.type === 'wasp') return 0.26;
  return ANT_HIT_R;
}

function slashHits(ant, k) {
  const dx = ant.x - k.x, dz = ant.z - k.z;
  const d = Math.hypot(dx, dz);
  const r = hitRadius(ant);
  const y = ant.y || 0;
  if (y > 1.35) return false;
  if (d > SLASH_RANGE + r) return false;
  if (d < 0.02) return true;
  const ang = Math.abs(angDiff(k.yaw, Math.atan2(dx, -dz)));
  return ang <= SLASH_ARC * 0.5;
}

function spinHits(ant, k) {
  const d = Math.hypot(ant.x - k.x, ant.z - k.z);
  const y = ant.y || 0;
  if (y > 1.45) return false;
  return d <= SPIN_RANGE + hitRadius(ant);
}

function camMove(ix, iz) {
  const yaw = World.camYaw;
  return {
    x: ix * Math.cos(yaw) - iz * Math.sin(yaw),
    z: ix * Math.sin(yaw) + iz * Math.cos(yaw)
  };
}

function autoAim(k) {
  const reach = SLASH_RANGE + ANT_HIT_R + 0.06;
  const aimHalf = SLASH_ARC * 0.5 + 0.08;
  let best = null, bestD = reach;
  for (const a of Game.ants) {
    if (!a.alive) continue;
    const aimable = { walk:1, eat:1, hover:1, dive:1, climb:1, telegraph:1, charge:1, stagger:1, summon:1 };
    if (!aimable[a.state]) continue;
    const dx = a.x - k.x, dz = a.z - k.z;
    const d = Math.hypot(dx, dz);
    if (d > reach || d < 0.02) continue;
    const ang = Math.abs(angDiff(k.yaw, Math.atan2(dx, -dz)));
    if (ang <= aimHalf && d <= bestD) { best = a; bestD = d; }
  }
  if (best) {
    k.yaw = Math.atan2(best.x - k.x, -(best.z - k.z));
  }
}

function addFx(type, x, z, y, life, h, extra) {
  const f = Object.assign({ type, x, z, y: y || 0, t: 0, life: life || 0.4, h: h || 0.6, rot: 0, scale: 1 }, extra || {});
  Game.fx.push(f);
  return f;
}

function spawnScorePop(x, z, pts) {
  addFx('score', x, z, 0.55, 0.7, 0.42, { text: '+' + pts, vy: 1.15 });
}

function scoreTexture(text) {
  const key = 'score/' + text;
  if (World.tex[key]) return World.tex[key];
  const c = document.createElement('canvas');
  c.width = 256; c.height = 128;
  const g = c.getContext('2d');
  g.font = 'bold 72px Trebuchet MS, Arial, sans-serif';
  g.textAlign = 'center'; g.textBaseline = 'middle';
  g.lineWidth = 10; g.strokeStyle = '#3a1d08'; g.fillStyle = '#ffe566';
  g.strokeText(text, 128, 64); g.fillText(text, 128, 64);
  const t = new THREE.CanvasTexture(c);
  if (t.colorSpace !== undefined) t.colorSpace = THREE.SRGBColorSpace;
  t.needsUpdate = true;
  World.tex[key] = t;
  return t;
}

function burstAt(x, z, y) {
  addFx('stars', x, z, (y || 0) + 0.35, 0.38, 0.62);
  addFx('puff', x, z, (y || 0) + 0.2, 0.22, 0.48, { frame: 0 });
}

function killAnt(a, dirX, dirZ, outward) {
  killBug(a, dirX, dirZ, outward);
}

function updateFx(dt) {
  for (const f of Game.fx) {
    f.t += dt;
    if (f.type === 'score') { f.y += (f.vy || 1) * dt; f.vy = (f.vy || 1) * 0.96; }
    if (f.type === 'puff') f.scale = 0.7 + f.t / f.life * 1.1;
    if (f.type === 'stars') { f.scale = 1 + f.t * 1.6; f.rot += dt * 2; }
  }
  Game.fx = Game.fx.filter((f) => f.t < f.life);
}



function foodById(id) {
  return (Game.foods || []).find((f) => f.id === id) || null;
}
function livingFoods() {
  return (Game.foods || []).filter((f) => f.hp > 0);
}
function sumFood() {
  return (Game.foods || []).reduce((s, f) => s + Math.max(0, f.hp), 0);
}
function pickFoodTarget(a) {
  if (a.targetId) {
    const cur = foodById(a.targetId);
    if (cur && cur.hp > 0) return cur;
  }
  const list = livingFoods();
  if (!list.length) return null;
  let best = list[0], bd = 1e9;
  for (const f of list) {
    const d = Math.hypot(f.x - a.x, f.z - a.z) + Math.random() * 0.55;
    if (d < bd) { bd = d; best = f; }
  }
  a.targetId = best.id;
  return best;
}
function syncFoodSprites() {
  if (!World.foodSprs) return;
  FOOD_ITEMS.forEach((spec, i) => {
    const s = World.foodSprs[i];
    const f = foodById(spec.id) || spec;
    if (!s) return;
    const name = (f.hp < f.max * 0.72) ? spec.bitten : spec.intact;
    World.setSpriteTex(s, name);
    World.place(s, spec.x, spec.z);
  });
}

function bugHeight(a) {
  if (a.type === 'boss') return BOSS_H;
  if (a.type === 'beetle') return BEETLE_H;
  if (a.type === 'wasp') return WASP_H;
  return ANT_H;
}

function makeWaveQueue(wave, round, n) {
  const q = [];
  for (let i = 0; i < n; i++) {
    let kind = 'ant';
    if (wave >= 2 && i === n - 1) kind = 'beetle';
    else if (wave >= 3 && i === n - 2) kind = (wave + i) % 2 ? 'wasp' : 'beetle';
    else if (wave >= 4 && Math.random() < 0.18 + Math.min(0.2, (wave + round) * 0.03)) {
      kind = Math.random() < 0.5 ? 'wasp' : 'beetle';
    }
    if (wave === 1 && round === 1) kind = 'ant';
    q.push(kind);
  }
  return q;
}

function spawnBug(kind, x, z) {
  kind = kind || 'ant';
  if (x == null || z == null) {
    const ang = Math.random() * Math.PI * 2;
    const r = 5.3 + Math.random() * 1.1;
    x = Math.cos(ang) * r; z = Math.sin(ang) * r;
  }
  const a = {
    type: kind, x, z, y: kind === 'wasp' ? WASP_HOVER : 0,
    vx: 0, vz: 0, vy: 0, face: 1, at: Math.random(),
    state: kind === 'wasp' ? 'hover' : 'walk',
    alive: true, deadT: 0, spin: 0, flash: 0,
    targetId: null, hoverT: 0, diveOf: 0
  };
  if (kind === 'beetle') {
    a.hp = 2; a.hpMax = 2;
    a.speed = 0.36 + Game.wave * 0.026 + Game.round * 0.018 + Math.random() * 0.035;
  } else if (kind === 'wasp') {
    a.hp = 1; a.hpMax = 1;
    a.speed = 0.94 + Game.wave * 0.044 + Game.round * 0.026 + Math.random() * 0.07;
  } else if (kind === 'boss') {
    a.hp = bossHpForRound(Game.round);
    a.hpMax = a.hp;
    a.speed = 0.85 + Game.round * 0.07;
  } else {
    a.hp = 1; a.hpMax = 1;
    a.speed = 0.70 + Game.wave * 0.06 + Game.round * 0.035 + Math.random() * 0.07;
  }
  Game.ants.push(a);
  return a;
}

function spawnAnt() { return spawnBug('ant'); }

function makeAnt(x, z, extra) {
  const a = spawnBug((extra && extra.type) || 'ant', x, z);
  if (extra) Object.assign(a, extra);
  return a;
}

function bossHpForRound(round) {
  return 7 + (round - 1) * 2; // was 8 + (round-1)*3
}

function bugAliveState(st) {
  return st === 'walk' || st === 'eat' || st === 'hover' || st === 'dive' || st === 'climb' || st === 'telegraph' || st === 'charge' || st === 'stagger' || st === 'summon';
}

function nibbleRate(a) {
  if (a.type === 'beetle') return BEETLE_NIBBLE;
  if (a.type === 'wasp') return WASP_NIBBLE;
  if (a.type === 'boss') return 3.57; // was 4.2
  return ANT_HP_NIBBLE;
}

function eatFood(a, f, dt) {
  if (!f || f.hp <= 0) return false;
  const dmg = nibbleRate(a) * dt;
  f.hp = Math.max(0, f.hp - dmg);
  Game.food = sumFood();
  return true;
}

function titleDogPose(kind, t) {
  const period = 8.2;
  const emma = kind === 'emma';
  const lag = 0; // enter from opposite sides together, cross around the logo
  const u = ((t + lag) % period) / period;
  const right = !emma;
  const startX = right ? -8.4 : 8.4;
  const endX = right ? 8.4 : -8.4;
  const x = lerp(startX, endX, u);
  const z = emma ? 0.22 : -0.62;
  const vx = endX - startX;
  const face = screenFace(vx, 0, right ? 1 : -1);
  const tex = kind + '_sausage_' + (Math.floor((t + lag) * 8) % 3) + '.png';
  return { x, z, y: 0, face, visible: true, tex, vx, vz: 0 };
}

const TITLE_ANT_LANES = [
  { z: 1.58, dir: 1, n: 4, period: 11.6, phase: 0.00, span: 13.2 },
  { z: -1.12, dir: -1, n: 4, period: 10.4, phase: 0.18, span: 13.0 },
  { z: 0.72, dir: 1, n: 4, period: 12.2, phase: 0.08, span: 13.6 }
];

function updateTitle(dt) {
  Game.titleT = (Game.titleT || 0) + dt;
  const st = { stormy: titleDogPose('stormy', Game.titleT), emma: titleDogPose('emma', Game.titleT) };
  World._titleMovers = [];
  if (World.stormySpr) {
    World.setSpriteH(World.stormySpr, STORMY_H * 0.86);
    World._applyDog(World.stormySpr, st.stormy, 'stormy');
    World._titleMovers.push(Object.assign({ kind: 'stormy' }, st.stormy));
  }
  if (World.emmaSpr) {
    World.setSpriteH(World.emmaSpr, EMMA_H * 0.86);
    World._applyDog(World.emmaSpr, st.emma, 'emma');
    World._titleMovers.push(Object.assign({ kind: 'emma' }, st.emma));
  }
  let count = 0;
  TITLE_ANT_LANES.forEach((lane) => { count += lane.n; });
  World.ensureTitleAnts(count);
  let i = 0;
  for (const lane of TITLE_ANT_LANES) {
    for (let k = 0; k < lane.n; k++) {
      const spr = World.titleAntSpr[i++];
      const u = (Game.titleT / lane.period + k / lane.n + lane.phase) % 1;
      const x0 = -lane.span * 0.5, x1 = lane.span * 0.5;
      const x = lane.dir > 0 ? lerp(x0, x1, u) : lerp(x1, x0, u);
      const vx = lane.dir > 0 ? 1 : -1;
      const face = screenFace(vx, 0, lane.dir);
      const tex = 'ant_walk_' + (Math.floor(Math.abs(x) * 3.2 + k) % 4) + '.png';
      World.setSpriteTex(spr, tex);
      World.place(spr, x, lane.z, 0);
      World.flip(spr, face);
      spr.mesh.visible = true;
      spr.blob.visible = true;
      World._titleMovers.push({ kind: 'ant', x, z: lane.z, y: 0, face, vx, vz: 0, visible: true });
    }
  }
}

function startBoss() {
  if (Game.boss && Game.boss.alive) return Game.boss;
  const ang = Math.random() * Math.PI * 2;
  const a = spawnBug('boss', Math.cos(ang) * 5.6, Math.sin(ang) * 5.6);
  a.state = 'walk';
  a.summonT = 2.4;
  a.teleT = 0;
  Game.boss = a;
  Game.bossDone = false;
  UI.showBanner(true, 'ANT CAPTAIN!');
  Game.bannerT = 1.6;
  if (Snd.bossHorn) Snd.bossHorn();
  UI.hud();
  return a;
}

function killBug(a, dirX, dirZ, outward) {
  if (!a.alive) return;
  a.alive = false;
  a.state = 'launch';
  a.at = 0; a.flash = 0.2; a.spin = 0; a.y = Math.max(a.y || 0, 0.05);
  const d = Math.hypot(dirX, dirZ) || 1;
  const power = outward ? 1.95 : 1.35;
  const side = (Math.random() - 0.5) * 0.7;
  a.vx = (dirX / d) * power + (-dirZ / d) * side;
  a.vz = (dirZ / d) * power + (dirX / d) * side;
  a.vy = outward ? 4.4 : 4.15;
  let pts = 10 + Game.wave * 2;
  if (a.type === 'beetle') pts = 20 + Game.wave * 3;
  if (a.type === 'wasp') pts = 18 + Game.wave * 3;
  if (a.type === 'boss') {
    pts = 150 + Game.round * 50;
    a.vy = 5.1;
    a.vx *= 0.7; a.vz *= 0.7;
    Game.bossDone = true;
    burstAt(a.x, a.z, 0.3);
    addFx('stars', a.x, a.z, 0.8, 0.7, 1.05);
    addFx('stars', a.x + 0.2, a.z - 0.1, 0.55, 0.55, 0.8, { rot: 0.4 });
    if (Snd.bossDown) Snd.bossDown();
    UI.showBanner(true, 'CAPTAIN DOWN!');
    Game.bannerT = 1.8;
  } else if (a.type === 'wasp') {
    if (Snd.waspHit) Snd.waspHit(); else Snd.bonk();
  } else {
    Snd.bonk();
  }
  Game.score += pts;
  spawnScorePop(a.x, a.z, pts);
  burstAt(a.x, a.z, a.y || 0.1);
  Game.hitStop = Math.max(Game.hitStop, a.type === 'boss' ? 0.16 : HITSTOP);
  Game.shake = a.type === 'boss' ? 0.28 : 0.16;
  Game.shakeAmp = outward || a.type === 'boss' ? 0.08 : 0.05;
  UI.hud();
}

function hurtBug(a, dirX, dirZ, outward, dmg) {
  if (!a.alive) return;
  if (Game.strikeId && a.struck === Game.strikeId) return;
  a.struck = Game.strikeId || 0;
  if (a.type === 'beetle' && a.hp > dmg) {
    a.hp -= dmg;
    a.flash = 0.22;
    a.state = 'stagger'; a.at = 0;
    if (Snd.armor) Snd.armor(); else Snd.bonk();
    Game.hitStop = Math.max(Game.hitStop, 0.045);
    return;
  }
  if (a.type === 'boss' && a.hp > dmg) {
    a.hp -= dmg;
    a.flash = 0.2;
    a.state = (a.state === 'charge') ? 'stagger' : a.state;
    a.staggerT = 0.28;
    if (Snd.bossHit) Snd.bossHit(); else Snd.bonk();
    Game.hitStop = Math.max(Game.hitStop, 0.06);
    Game.shake = 0.12; Game.shakeAmp = 0.05;
    UI.hud();
    return;
  }
  killBug(a, dirX, dirZ, outward);
}

function updateWasp(a, dt, k) {
  if (a.speed === 0 && a.state !== 'dive') { a.at += dt; return; }
  a.hoverT = (a.hoverT || 0) + dt;
  const f = pickFoodTarget(a);
  const diveKnight = f && Math.hypot(k.x - a.x, k.z - a.z) < 2.1 && Math.random() < 0.003 + Game.round * 0.001;
  if (a.state === 'hover' || a.state === 'climb') {
    const tx = f ? f.x : 0, tz = f ? f.z : 0;
    const dx = tx - a.x, dz = tz - a.z, d = Math.hypot(dx, dz) || 1;
    a.y = WASP_HOVER + Math.sin(a.hoverT * 5.2) * 0.08;
    if (a.state === 'climb') {
      a.y += 0.55 * dt;
      if (a.y >= WASP_HOVER - 0.02) { a.state = 'hover'; a.y = WASP_HOVER; }
    }
    a.vx = (dx / d) * a.speed * 0.72;
    a.vz = (dz / d) * a.speed * 0.72;
    a.x += a.vx * dt; a.z += a.vz * dt;
    a.at += dt * 10;
    if (d < (f ? f.eatR + 0.85 : 1.1) || diveKnight) {
      a.state = 'dive';
      a.diveOf = 0;
      a.diveTarget = diveKnight ? 'knight' : 'food';
    }
    if (Game.t - (Game.lastBuzzSnd || 0) > 0.9 && Snd.buzz) { Snd.buzz(); Game.lastBuzzSnd = Game.t; }
  } else if (a.state === 'dive') {
    a.diveOf += dt;
    const destX = a.diveTarget === 'knight' ? k.x : (f ? f.x : a.x);
    const destZ = a.diveTarget === 'knight' ? k.z : (f ? f.z : a.z);
    const destY = a.diveTarget === 'knight' ? 0.45 : 0.18;
    const dx = destX - a.x, dz = destZ - a.z, d = Math.hypot(dx, dz);
    const sp = a.speed * 1.55;
    if (d > 0.02) { a.vx = (dx / d) * sp; a.vz = (dz / d) * sp; a.x += a.vx * dt; a.z += a.vz * dt; }
    else { a.vx = 0; a.vz = 0; }
    a.y = lerp(a.y, destY, 1 - Math.exp(-6 * dt));
    a.at += dt * 12;
    if (d < ((f && a.diveTarget !== 'knight') ? f.eatR : 0.38) && a.y < 0.38) {
      if (a.diveTarget === 'knight') {
        a.state = 'climb';
      } else {
        a.state = 'eat'; a.at = 0;
      }
    }
    if (a.diveOf > 2.4) a.state = 'climb';
  } else if (a.state === 'eat') {
    a.y = lerp(a.y, 0.16, 1 - Math.exp(-8 * dt));
    a.at += dt;
    if (f) eatFood(a, f, dt);
    if (!f || f.hp <= 0 || a.at > 1.15) { a.state = 'climb'; a.targetId = null; }
  }
}

function updateBossAI(a, dt, k) {
  if (!a.alive) return;
  if (a.staggerT > 0) {
    a.staggerT -= dt; a.at += dt;
    if (a.staggerT <= 0 && a.state === 'stagger') a.state = 'walk';
    return;
  }
  a.summonT = (a.summonT || 0) - dt;
  a.teleT = (a.teleT || 0) + dt;
  if (a.state === 'summon') {
    a.at += dt;
    if (a.at > 0.55) {
      const n = 2; // was 2, or 3 from round 3
      for (let i = 0; i < n; i++) {
        const ang = Math.random() * Math.PI * 2;
        spawnBug('ant', a.x + Math.cos(ang) * 0.7, a.z + Math.sin(ang) * 0.7);
      }
      a.state = 'walk'; a.summonT = 5.5 - Math.min(1.5, Game.round * 0.2);
    }
    return;
  }
  if (a.state === 'telegraph') {
    a.at += dt;
    if (a.at > 0.55) {
      a.state = 'charge';
      a.at = 0;
      const dx = k.x - a.x, dz = k.z - a.z, d = Math.hypot(dx, dz) || 1;
      a.cx = dx / d; a.cz = dz / d;
      a.chargeT = 0.85;
    }
    return;
  }
  if (a.state === 'charge') {
    a.chargeT -= dt;
    a.vx = a.cx * 3.4; a.vz = a.cz * 3.4;
    a.x += a.vx * dt;
    a.z += a.vz * dt;
    a.at += dt * 8;
    if (a.chargeT <= 0) a.state = 'walk';
    return;
  }
  // walk toward knight, sometimes food
  const f = pickFoodTarget(a);
  const goFood = f && Math.hypot(f.x - a.x, f.z - a.z) < Math.hypot(k.x - a.x, k.z - a.z) * 0.7;
  const tx = goFood ? f.x : k.x, tz = goFood ? f.z : k.z;
  const dx = tx - a.x, dz = tz - a.z, d = Math.hypot(dx, dz) || 1;
  if (goFood && d < f.eatR + 0.15) {
    a.state = 'eat'; a.vx = 0; a.vz = 0; a.at += dt;
    eatFood(a, f, dt);
  } else {
    a.state = 'walk';
    a.vx = (dx / d) * a.speed; a.vz = (dz / d) * a.speed;
    a.x += a.vx * dt; a.z += a.vz * dt;
    a.at += dt * (a.speed / 1.1);
  }
  if (a.summonT <= 0) { a.state = 'summon'; a.at = 0; }
  else if (a.teleT > 3.2 && d < 4.5 && d > 0.8) { a.state = 'telegraph'; a.at = 0; a.teleT = 0; }
}


function maybeStartBoss() {
  if (Game.state !== 'play') return false;
  if (Game.bossDone || (Game.boss && Game.boss.alive)) return false;
  if (Game.timeLeft > BOSS_WINDOW || Game.timeLeft <= 0) return false;
  startBoss();
  return true;
}


function easeInOut(u) {
  u = clamp(u, 0, 1);
  return u * u * (3 - 2 * u);
}

function stealPose(t, who, grabbed) {
  // Enter from the left lawn (art faces right), snatch at ~1.9s, bolt off to the right.
  // The stealer takes the near-camera lane; the pal stays left and further back so both read clearly.
  const grabT = 1.90;
  const boltT = 2.35;
  const endT = STEAL_DUR;
  const sX = SAUSAGE.x, sZ = SAUSAGE.z;
  const startX = -6.4, endX = 8.6;
  function dogAt(kind) {
    const isStealer = kind === who;
    const nearZ = sZ + 0.48;
    const farZ = sZ - 0.62;
    const laneZ = isStealer ? nearZ : farZ;
    const startZ = isStealer ? 2.15 : 0.25;
    let x, z, y = 0, visible = t > 0.04, tex;
    let vx = 1, vz = 0;
    const arrive = grabT - (isStealer ? 0 : 0.16);
    if (t < arrive) {
      const u = easeInOut(t / Math.max(0.01, arrive));
      const destX = isStealer ? (sX - 0.12) : (sX - 2.15);
      const fromX = startX - (isStealer ? 0 : 0.55);
      x = lerp(fromX, destX, u);
      z = lerp(startZ, laneZ, u);
      vx = destX - fromX;
      vz = laneZ - startZ;
      tex = kind + '_run_' + (Math.floor(t * 9) % 3) + '.png';
    } else if (t < boltT) {
      const u = (t - arrive) / Math.max(0.01, boltT - arrive);
      if (isStealer) {
        x = sX - 0.04 + Math.sin(u * Math.PI) * 0.10;
        z = nearZ;
        y = Math.sin(u * Math.PI) * 0.16;
        vx = 1; vz = 0; // hop in place, keep facing the bolt
        tex = kind + '_grab.png';
      } else {
        x = (sX - 2.15) + u * 0.65;
        z = farZ;
        vx = 0.65; vz = 0;
        tex = kind + '_run_' + (Math.floor(t * 9) % 3) + '.png';
      }
    } else {
      const u = easeInOut((t - boltT) / Math.max(0.01, endT - 0.15 - boltT));
      const fromX = isStealer ? (sX + 0.28) : (sX - 1.50);
      const toX = endX + (isStealer ? 0.15 : -0.55);
      const fromZ = isStealer ? nearZ : farZ;
      const toZ = isStealer ? 1.75 : 0.28;
      x = lerp(fromX, toX, u);
      z = lerp(fromZ, fromZ + (toZ - fromZ) * 0.45, u);
      vx = toX - fromX;
      vz = (toZ - fromZ) * 0.45;
      tex = isStealer
        ? (kind + '_sausage_' + (Math.floor(t * 10) % 3) + '.png')
        : (kind + '_run_' + (Math.floor(t * 10) % 3) + '.png');
      if (x > 7.7) visible = false;
    }
    const face = screenFace(vx, vz, 1);
    return { x, z, y, face, visible, tex, stealer: isStealer, vx, vz };
  }
  return { stormy: dogAt('stormy'), emma: dogAt('emma'), sausageOn: !(grabbed || t >= grabT) };
}

function updateSteal(dt) {
  const st = Game.steal;
  if (!st) return;
  st.t += dt;
  const grabT = 1.90;
  if (!st.scampered && st.t > 0.12) { st.scampered = true; }
  if (!st.grabbed && st.t >= grabT) {
    st.grabbed = true;
    st.sausageOn = false;
    World.showSausage(false);
    const pose = stealPose(st.t, st.who, true);
    const d = pose[st.who];
    const sizeK = (st.who === 'stormy') ? (STORMY_H / EMMA_H) : 1;
    addFx('puff', d.x, d.z, 0.22 * sizeK, 0.55, 0.7 * sizeK, { frame: 0 });
    addFx('puff', d.x + 0.25 * sizeK, d.z + 0.1 * sizeK, 0.18 * sizeK, 0.42, 0.55 * sizeK, { frame: 1 });
    addFx('puff', d.x - 0.2 * sizeK, d.z - 0.08 * sizeK, 0.16 * sizeK, 0.38, 0.5 * sizeK, { frame: 0 });
    Game.shake = 0.16; Game.shakeAmp = 0.07;
    if (Snd.bark) Snd.bark(st.who);
    st.barked = true;
  }
  if (st.grabbed && st.t > 2.38 && st.t < 2.5 && Snd.scamper) {
    if (!st.bolted) { st.bolted = true; Snd.scamper(); }
  }
  const pose = stealPose(st.t, st.who, st.grabbed);
  World.showSausage(!!pose.sausageOn);
  World.placeDogsForSteal(st.t, st.who, st.grabbed);
  World.lockStealCam();
  const k = Game.knight;
  k.anim = 'idle'; k.at += dt * 0.8;
  k.yaw = -0.85;
  // startled hop when they snatch
  if (st.grabbed && st.t < grabT + 0.45) k.at += dt * 2;
  if (st.t >= st.dur) UI.endSteal();
}

function updatePlay(dt) {
  const inp = Input.poll();
  const k = Game.knight;
  if (Game.bannerT > 0) {
    Game.bannerT -= dt;
    if (Game.bannerT <= 0) { Game.bannerT = 0; UI.showBanner(false); }
  }
  Game.timeLeft = Math.max(0, Game.timeLeft - dt);
  if (Game.bear && Game.bear.on) updateBear(dt);
  if (Game.timeLeft <= 0) { UI.roundClear(); return; }
  if (k.spinCd > 0) k.spinCd = Math.max(0, k.spinCd - dt);

  if (k.slashT <= 0 && k.spinT <= 0) {
    const mag = Math.hypot(inp.x, inp.z);
    const dir = camMove(inp.x, inp.z);
    let wantVx = 0, wantVz = 0, t = 0;
    if (mag > 1e-4) {
      t = Math.pow(clamp(mag, 0, 1), 1.4);
      const spd = KNIGHT_RUN * t;
      wantVx = (dir.x / mag) * spd;
      wantVz = (dir.z / mag) * spd;
      const tyaw = Math.atan2(dir.x, -dir.z);
      k.yaw = dampAngle(k.yaw, tyaw, 14, dt);
    }
    const accK = -Math.log(0.05) / MOVE_ACCEL_T;
    k.vx = damp(k.vx, wantVx, accK, dt);
    k.vz = damp(k.vz, wantVz, accK, dt);
    if (Math.hypot(k.vx, k.vz) < 0.03 && mag < 1e-4) { k.vx = 0; k.vz = 0; }
    k.speed = Math.hypot(k.vx, k.vz);
    k.x += k.vx * dt;
    k.z += k.vz * dt;
    collideKnight(k);
    if (k.speed > 0.10) {
      k.anim = k.speed < KNIGHT_WALK * 1.15 ? 'walk' : 'run';
      k.at += dt * (5.2 + k.speed * 4.2);
    } else {
      k.anim = 'idle'; k.at += dt;
    }
  }

  if (inp.slashEdge && k.slashT <= 0 && k.spinT <= 0) {
    autoAim(k);
    k.slashT = SLASH_TIME; k.anim = 'slash'; k.at = 0;
    Game.strikeId = (Game.strikeId || 0) + 1;
    Snd.slash();
  }
  if (inp.spinEdge && k.spinT <= 0 && k.spinCd <= 0) {
    k.spinT = SPIN_TIME; k.spinCd = SPIN_CD; k.anim = 'spin'; k.at = 0;
    Game.strikeId = (Game.strikeId || 0) + 1;
    Snd.spin();
  }
  if (k.slashT > 0) { k.slashT -= dt; k.anim = 'slash'; k.at = 1 - k.slashT / SLASH_TIME; if (k.slashT <= 0) { k.slashT = 0; k.anim = 'idle'; k.at = 0; } }
  if (k.spinT > 0) { k.spinT -= dt; k.anim = 'spin'; k.at = 1 - k.spinT / SPIN_TIME; if (k.spinT <= 0) { k.spinT = 0; k.anim = 'idle'; k.at = 0; } }

  maybeStartBoss();
  Game.waveT -= dt;
  if (Game.spawnLeft > 0 && Game.waveT <= 0) {
    const kind = (Game.spawnQueue && Game.spawnQueue.length) ? Game.spawnQueue.shift() : 'ant';
    spawnBug(kind);
    Game.spawnLeft = Game.spawnQueue ? Game.spawnQueue.length : Math.max(0, Game.spawnLeft - 1);
    Game.waveT = Math.max(0.34, 0.78 - Game.wave * 0.035);
  }
  const living = Game.ants.filter((a) => a.alive && a.type !== 'boss').length;
  const leftover = Game.ants.some((a) => !a.alive && (a.state === 'launch' || a.state === 'down' || a.state === 'poof'));
  const bossBusy = !!(Game.boss && Game.boss.alive);
  if (!bossBusy && living === 0 && Game.spawnLeft === 0 && !leftover) {
    if (!Game._nextArm) Game._nextArm = 0.85;
    else { Game._nextArm -= dt; if (Game._nextArm <= 0) { Game._nextArm = 0; Game.ants = Game.ants.filter((a) => a.type === 'boss'); UI.nextWave(); } }
  } else Game._nextArm = 0;

  let nibbling = false;
  for (const a of Game.ants) {
    if (a.flash > 0) a.flash -= dt;
    if (!a.alive) {
      if (a.state === 'launch') {
        a.vy -= 10.8 * dt;
        a.x += a.vx * dt; a.z += a.vz * dt; a.y += a.vy * dt;
        a.spin += 14 * dt;
        a.at += dt;
        if (a.y <= 0 && a.vy < 0) {
          a.y = 0; a.vy *= -0.28;
          if (Math.abs(a.vy) < 1.4) { a.state = 'down'; a.at = 0; a.spin = 0; a.y = 0; }
        }
      } else if (a.state === 'down') {
        a.at += dt;
        const hold = a.type === 'boss' ? 1.15 : 0.72;
        if (a.at > hold) { a.state = 'poof'; a.at = 0; addFx('puff', a.x, a.z, 0.15, 0.38, 0.72, { frame: 0 }); addFx('puff', a.x, a.z, 0.2, 0.32, 0.55, { frame: 1, delay: 0 }); Snd.poof && Snd.poof(); }
      } else if (a.state === 'poof') {
        a.at += dt;
      }
      continue;
    }
    if (a.type === 'boss') {
      updateBossAI(a, dt, k);
    } else if (a.type === 'wasp') {
      updateWasp(a, dt, k);
      if (a.state === 'eat') nibbling = true;
    } else if (a.state === 'stagger') {
      a.at += dt;
      if (a.at > 0.28) a.state = 'walk';
    } else {
      const f = pickFoodTarget(a);
      if (!f) {
        a.state = 'walk'; a.vx = 0; a.vz = 0; a.at += dt;
      } else {
        const dx = f.x - a.x, dz = f.z - a.z, d = Math.hypot(dx, dz);
        if (d < f.eatR) {
          a.state = 'eat'; a.vx = 0; a.vz = 0; a.at += dt;
          if (eatFood(a, f, dt)) nibbling = true;
        } else {
          a.state = 'walk';
          a.vx = (dx / d) * a.speed; a.vz = (dz / d) * a.speed;
          a.x += a.vx * dt; a.z += a.vz * dt;
          a.yaw = Math.atan2(a.vx, -a.vz);
          a.at += dt * (a.speed / 1.4);
        }
      }
    }
    if (k.spinT > 0 && spinHits(a, k)) {
      const ox = a.x - k.x, oz = a.z - k.z;
      hurtBug(a, ox, oz, true, 2);
    } else if (k.slashT > 0 && k.at > 0.06 && k.at < 0.92 && slashHits(a, k)) {
      const fdir = faceDir(k.yaw);
      hurtBug(a, fdir.x, fdir.z, false, 1);
    }
  }
  if (nibbling && Game.t - Game.lastNibbleSnd > 0.22) { Snd.nibble(); Game.lastNibbleSnd = Game.t; }
  Game.food = sumFood();
  Game.ants = Game.ants.filter((a) => a.alive || a.state !== 'poof' || a.at < 0.28);
  if (Game.boss && !Game.boss.alive && Game.boss.state === 'poof' && Game.boss.at >= 0.28) Game.boss = Game.boss;
  updateFx(dt);
  if (Game.shake > 0) Game.shake = Math.max(0, Game.shake - dt);
  UI.hud();
  if (Game.food <= 0) UI.lose();
}

function animFrame(list, t, fps) {
  const i = Math.floor(t * fps) % list.length;
  return list[i];
}

function knightTex(k) {
  const v = k.view || 'front34';
  if (k.anim === 'slash') {
    const i = k.at < 0.28 ? 0 : k.at < 0.7 ? 1 : 2;
    return ['knight_slash_0.png', 'knight_slash_1.png', 'knight_slash_2.png'][i];
  }
  if (k.anim === 'spin') {
    const i = k.at < 0.28 ? 0 : k.at < 0.72 ? 1 : 2;
    return ['knight_spin_0.png', 'knight_spin_1.png', 'knight_spin_2.png'][i];
  }
  if (k.anim === 'run' || k.anim === 'walk') {
    const runs = {
      front: ['knight_run_front_0.png', 'knight_run_front_1.png'],
      front34: ['knight_run_34front_a.png', 'knight_run_34front_b.png'],
      side: ['knight_run_side_0.png', 'knight_run_side_1.png'],
      back34: ['knight_run_back34_0.png', 'knight_run_back34_1.png'],
      back: ['knight_run_back_0.png', 'knight_run_back_1.png']
    };
    return animFrame(runs[v] || runs.front34, k.at, 1);
  }
  const idles = {
    front: ['knight_idle_front.png'],
    front34: ['knight_idle_0.png', 'knight_idle_1.png', 'knight_idle_2.png'],
    side: ['knight_idle_side.png'],
    back34: ['knight_idle_back34.png'],
    back: ['knight_idle_back.png']
  };
  const list = idles[v] || idles.front34;
  return list.length > 1 ? animFrame(list, k.at, 3) : list[0];
}

function fadeIfOccluding(spr, fx, fz, fr, fh) {
  const cam = World.cam, k = Game.knight;
  const abx = k.x - cam.x, abz = k.z - cam.z;
  const len2 = abx * abx + abz * abz;
  let amount = 0;
  if (len2 > 1e-6) {
    const t = clamp(((fx - cam.x) * abx + (fz - cam.z) * abz) / len2, 0, 1);
    if (t > 0.06 && t < 0.92) {
      const px = cam.x + abx * t, pz = cam.z + abz * t;
      const dist = Math.hypot(fx - px, fz - pz);
      const rad = (fr || 0.4) + 0.18;
      if (dist < rad + 0.22) {
        const along = 1 - Math.abs(t - 0.55) * 1.4;
        const across = 1 - clamp((dist - rad * 0.15) / (rad + 0.22), 0, 1);
        amount = clamp(Math.max(along, 0.35) * across, 0, 1);
        if ((fh || 0.6) < 0.55) amount *= 0.75;
      }
    }
  }
  const op = lerp(1, 0.26, amount);
  spr.mesh.material.transparent = true;
  spr.mesh.material.opacity = op;
  spr.mesh.material.depthWrite = false;
  if (spr.blob && spr.blob.material) spr.blob.material.opacity = 0.26 * (0.3 + 0.7 * op);
  spr._fade = amount;
}

function fadeWatcher(spr, x, z) {
  const cam = World.camera ? World.camera.position : World.cam;
  let lookX, lookZ;
  if (Game.state === 'title') { lookX = -0.4; lookZ = 0.35; }
  else if (Game.state === 'steal' && World.lookLock) { lookX = World.lookLock.x; lookZ = World.lookLock.z; }
  else { lookX = Game.knight.x; lookZ = Game.knight.z; }
  const lx = lookX - cam.x, lz = lookZ - cam.z;
  const llen = Math.hypot(lx, lz) || 1;
  const vx = x - cam.x, vz = z - cam.z;
  const along = (vx * lx + vz * lz) / llen;
  const t = along / llen; // 0 at camera, 1 at the look point
  let fade = 0;
  // Only fade when the figure actually sits in the central play view.
  const mid = new THREE.Vector3(x, 1.15, z).project(World.camera);
  const inPlayCone = Math.abs(mid.x) < 0.58 && mid.y < 0.18 && mid.y > -0.95;
  if (inPlayCone && t < 1.02) fade = clamp((1.02 - t) / 0.4, 0, 1);
  const dCam = Math.hypot(vx, vz);
  if (dCam < 2.5) fade = Math.max(fade, 1 - dCam / 2.5);
  const op = lerp(1, 0, clamp(fade, 0, 1));
  spr.mesh.material.transparent = true;
  spr.mesh.material.opacity = op;
  spr.mesh.material.depthWrite = false;
  spr.mesh.visible = op > 0.04;
  if (spr.blob) {
    spr.blob.visible = op > 0.08;
    if (spr.blob.material) spr.blob.material.opacity = 0.22 * op;
  }
  spr._fade = fade;
}

function basketSpec() {
  return FOOD_ITEMS.find((f) => f.id === 'basket') || { x: 1.75, z: -1.50, h: BASKET_H };
}

function hitPicnicBasket(sx, sy) {
  if (Game.state !== 'play') return false;
  const spec = basketSpec();
  if (!World.camera) return false;
  const spr = (World.foodSprs || []).find((s) => s.foodId === 'basket');
  const h = spec.h, w = spr ? Math.abs(spr.mesh.scale.x) : h;
  const corners = [
    [spec.x - w * 0.55, 0, spec.z],
    [spec.x + w * 0.55, 0, spec.z],
    [spec.x - w * 0.55, h, spec.z],
    [spec.x + w * 0.55, h, spec.z]
  ];
  let minx = 1e9, miny = 1e9, maxx = -1e9, maxy = -1e9;
  for (const p of corners) {
    const v = new THREE.Vector3(p[0], p[1], p[2]).project(World.camera);
    const x = (v.x * 0.5 + 0.5) * window.innerWidth;
    const y = (-v.y * 0.5 + 0.5) * window.innerHeight;
    if (x < minx) minx = x; if (x > maxx) maxx = x;
    if (y < miny) miny = y; if (y > maxy) maxy = y;
  }
  const pad = 14;
  return sx >= minx - pad && sx <= maxx + pad && sy >= miny - pad && sy <= maxy + pad;
}

function registerBasketTap() {
  if (Game.state !== 'play') return;
  if (Game.bear && Game.bear.on) return;
  const now = Game.t || 0;
  Game.basketTaps = (Game.basketTaps || []).filter((t) => now - t < 2.8);
  Game.basketTaps.push(now);
  if (Game.basketTaps.length >= 5) {
    Game.basketTaps = [];
    startBearDance();
  }
}

function startBearDance() {
  Game.bear = { on: true, t: 0 };
  if (Snd.bearPop) Snd.bearPop();
}

function hideBear() {
  if (Game.bear) Game.bear.on = false;
  if (World.bearSpr) {
    World.bearSpr.mesh.visible = false;
    World.bearSpr.blob.visible = false;
  }
}

function updateBear(dt) {
  if (!Game.bear || !Game.bear.on) {
    if (World.bearSpr) {
      World.bearSpr.mesh.visible = false;
      World.bearSpr.blob.visible = false;
    }
    return;
  }
  Game.bear.t += dt;
  const t = Game.bear.t;
  const total = BEAR_POP + BEAR_DANCE + BEAR_DUCK;
  if (t >= total) { hideBear(); return; }
  const spec = basketSpec();
  const spr = World.bearSpr;
  if (!spr) return;
  let name = 'bear_pop.png', y = 0.18, h = BEAR_H, vis = true;
  if (t < BEAR_POP) {
    const u = easeInOut(t / BEAR_POP);
    y = lerp(0.06, 0.40, u);
    h = BEAR_H * lerp(0.45, 1, u);
    name = 'bear_pop.png';
  } else if (t < BEAR_POP + BEAR_DANCE) {
    const u = t - BEAR_POP;
    y = 0.40 + Math.sin(u * 10) * 0.03;
    h = BEAR_H;
    const seq = ['bear_shimmy_0.png', 'bear_shimmy_1.png', 'bear_shimmy_2.png', 'bear_shimmy_1.png'];
    name = seq[Math.floor(u * 8) % 4];
  } else {
    const u = easeInOut((t - BEAR_POP - BEAR_DANCE) / BEAR_DUCK);
    y = lerp(0.40, 0.05, u);
    h = BEAR_H * lerp(1, 0.4, u);
    name = 'bear_duck.png';
  }
  World.setSpriteH(spr, h);
  World.setSpriteTex(spr, name);
  World.place(spr, spec.x, spec.z, y);
  spr.mesh.visible = vis;
  spr.blob.visible = false; // sitting in the basket, no extra ground blob
  spr.mesh.material.opacity = 1;
  spr.mesh.material.transparent = true;
  spr.mesh.renderOrder = 2;
}

function updateWatchers() {
  if (!World.watcherSpr) return;
  const t = Game.t || Game.titleT || 0;
  WATCHERS.forEach((w, i) => {
    const spr = World.watcherSpr[i];
    if (!spr) return;
    const seq = [0, 1, 2, 1];
    const frame = seq[Math.floor((t + (spr._phase || 0)) * 1.05) % 4];
    World.setSpriteH(spr, w.h);
    World.setSpriteTex(spr, w.prefix + frame + '.png');
    const bob = Math.sin((t + (spr._phase || 0)) * 1.4) * 0.03;
    World.place(spr, w.x, w.z, bob);
    // Face the picnic (origin) in screen space so they appear to watch the battle.
    const face = screenFace(-w.x, -w.z, 1);
    World.flip(spr, face);
    fadeWatcher(spr, w.x, w.z);
  });
}

function syncSprites() {
  updateWatchers();
  if (Game.bear && Game.bear.on) updateBear(0);
  else if (World.bearSpr) { World.bearSpr.mesh.visible = false; World.bearSpr.blob.visible = false; }
  const k = Game.knight;
  const vis = viewFromCamera(k);
  k.view = vis.view; k.face = vis.face;
  World.setSpriteTex(World.knightSpr, knightTex(k));
  World.place(World.knightSpr, k.x, k.z, 0);
  if (k.anim === 'slash') {
    const f = faceDir(k.yaw);
    const side = f.x * Math.cos(World.camYaw) + f.z * Math.sin(World.camYaw);
    World.flip(World.knightSpr, side >= 0 ? 1 : -1);
  } else {
    World.flip(World.knightSpr, k.face);
  }
  World.knightSpr.mesh.material.rotation = 0;
  World.knightSpr.mesh.center.set(0.5, 0);

  if (World.foodSprs) {
    FOOD_ITEMS.forEach((spec, i) => {
      const s = World.foodSprs[i];
      const f = foodById(spec.id) || spec;
      if (!s) return;
      const name = (f.hp < f.max * 0.72) ? spec.bitten : spec.intact;
      World.setSpriteTex(s, name);
      World.place(s, spec.x, spec.z);
      fadeIfOccluding(s, spec.x, spec.z, spec.r, spec.h);
    });
  }
  if (World.sausageSpr) {
    const on = !!(Game.steal && Game.steal.sausageOn);
    World.sausageSpr.mesh.visible = on;
    World.sausageSpr.blob.visible = on;
    if (on) {
      World.place(World.sausageSpr, SAUSAGE.x, SAUSAGE.z);
      fadeIfOccluding(World.sausageSpr, SAUSAGE.x, SAUSAGE.z, SAUSAGE.r, SAUSAGE.h);
    }
  }
  if (Game.state === 'steal' && Game.steal) {
    World.placeDogsForSteal(Game.steal.t, Game.steal.who, Game.steal.grabbed);
  } else if (Game.state === 'title') {
    // dogs and title ants placed in updateTitle
  } else if (World.stormySpr) {
    World.hideDogs();
  }
  if (Game.state !== 'title') World.hideTitleAnts();

  World.ensureAnts(Game.ants.length);
  for (let i = 0; i < World.antSpr.length; i++) {
    const s = World.antSpr[i], a = Game.ants[i];
    if (!a || a.state === 'poof') { s.mesh.visible = false; s.blob.visible = false; continue; }
    s.mesh.visible = true;
    s.blob.visible = (a.y || 0) < 0.18;
    s.h = bugHeight(a);
    let an = 'ant_walk_0.png';
    let rot = 0, y = a.y || 0, mid = false;
    const typ = a.type || 'ant';
    if (a.state === 'launch') {
      an = typ === 'beetle' ? 'beetle_bonk.png' : typ === 'wasp' ? 'wasp_bonk.png' : typ === 'boss' ? 'boss_hurt.png' : 'ant_walk_0.png';
      rot = a.spin;
      mid = true;
    } else if (a.state === 'down') {
      if (typ === 'beetle') an = 'beetle_down.png';
      else if (typ === 'wasp') an = 'wasp_down.png';
      else if (typ === 'boss') an = 'boss_down.png';
      else an = (Math.floor(a.at * 8) % 2 === 0) ? 'ant_down_0.png' : 'ant_down_1.png';
    } else if (typ === 'beetle') {
      if (a.state === 'eat') an = 'beetle_nibble.png';
      else if (a.state === 'stagger') an = 'beetle_bonk.png';
      else an = animFrame(['beetle_walk_0.png', 'beetle_walk_1.png'], a.at, 6);
    } else if (typ === 'wasp') {
      if (a.state === 'dive') an = 'wasp_dive.png';
      else if (a.state === 'eat') an = 'wasp_dive.png';
      else an = animFrame(['wasp_fly_0.png', 'wasp_fly_1.png'], a.at, 8);
    } else if (typ === 'boss') {
      if (a.state === 'telegraph' || a.state === 'summon') an = 'boss_tele.png';
      else if (a.state === 'charge') an = 'boss_charge.png';
      else if (a.state === 'stagger') an = 'boss_hurt.png';
      else if (a.state === 'eat') an = 'boss_walk_0.png';
      else an = 'boss_walk_0.png';
    } else if (a.state === 'eat') an = 'ant_nibble.png';
    else an = animFrame(['ant_walk_0.png', 'ant_walk_1.png', 'ant_walk_2.png', 'ant_walk_3.png'], a.at, 8);
    World.setSpriteTex(s, an);
    if (mid) {
      s.mesh.center.set(0.5, 0.5);
      s.mesh.position.set(a.x, y + bugHeight(a) * 0.5, a.z);
    } else {
      s.mesh.center.set(0.5, 0);
      World.place(s, a.x, a.z, y);
    }
    s.mesh.material.rotation = rot;
    const flash = a.flash > 0 ? 1 + a.flash * 18 : 1;
    s.mesh.material.color.setRGB(flash, flash, flash);
    a.face = screenFace(a.vx || 0, a.vz || 0, a.face);
    World.flip(s, a.face);
    World.syncBlob(s);
    s.blob.position.set(a.x, 0.012, a.z);
  }

  World.ensureFx(Game.fx.length + 2);
  for (let i = 0; i < World.fxSpr.length; i++) {
    const s = World.fxSpr[i], f = Game.fx[i];
    if (!f) { s.mesh.visible = false; continue; }
    s.mesh.visible = true;
    if (f.type === 'score') {
      const tex = scoreTexture(f.text || '+10');
      if (s.mesh.material.map !== tex) { s.mesh.material.map = tex; s.mesh.material.needsUpdate = true; s.name = 'score'; }
      s.h = f.h; s.mesh.scale.set(f.h * 2, f.h, 1);
      s.mesh.center.set(0.5, 0.5);
      s.mesh.position.set(f.x, f.y, f.z);
      s.mesh.material.rotation = 0;
      const fade = 1 - f.t / f.life;
      s.mesh.material.opacity = fade;
      s.mesh.material.color.setRGB(1, 1, 1);
    } else {
      const name = f.type === 'stars' ? 'fx_stars.png' : (f.frame === 1 ? 'fx_puff_1.png' : 'fx_puff_0.png');
      World.setSpriteTex(s, name);
      const sc = (f.scale || 1);
      s.h = (f.h || 0.55) * sc;
      const tex = World.tex[name];
      const aspect = tex.image.width / tex.image.height;
      s.mesh.scale.set(s.h * aspect, s.h, 1);
      s.mesh.center.set(0.5, 0.5);
      s.mesh.position.set(f.x, f.y, f.z);
      s.mesh.material.rotation = f.rot || 0;
      const fade = 1 - Math.max(0, (f.t / f.life) * 1.1 - 0.1);
      s.mesh.material.opacity = clamp(fade, 0, 1);
      s.mesh.material.color.setRGB(1, 1, 1);
    }
    s.mesh.material.transparent = true;
    s.mesh.material.alphaTest = 0.05;
  }
}

function loop(now) {
  requestAnimationFrame(loop);
  if (!World.ready) return;
  const t = now * 0.001;
  let dt = t - (loop._t || t); loop._t = t;
  dt = Math.min(1 / 30, Math.max(0, dt));
  if (loop.frozen) {
    syncSprites();
    World.updateCam(0);
    World.updateArrow();
    World.renderer.render(World.scene, World.camera);
    return;
  }
  if (Game.state === 'steal') {
    Game.t += dt;
    Input.poll();
    updateSteal(dt);
  } else if (Game.state === 'play') {
    if (Game.hitStop > 0) {
      Game.hitStop -= dt;
      syncSprites();
      World.updateCam(dt);
      World.updateArrow();
      World.renderer.render(World.scene, World.camera);
      return;
    }
    Game.t += dt;
    updatePlay(dt);
  } else if (Game.state === 'title') {
    Input.poll();
    updateTitle(dt);
  } else Input.poll();
  if (Game.state === 'play' || Game.state === 'pause' || Game.state === 'lose' || Game.state === 'steal' || Game.state === 'clear') {
    syncSprites();
    World.updateCam(dt);
    World.updateArrow();
  } else {
    Game.knight.anim = 'idle'; Game.knight.at += dt;
    Game.knight.yaw = 0.85;
    if (Game.state === 'title') updateTitle(0);
    syncSprites();
    World.updateCam(dt);
  }
  World.renderer.render(World.scene, World.camera);
}

async function boot() {
  UI.init();
  Input.init();
  try { await World.init(); }
  catch (e) { console.error(e); }
  UI.show('loading', false);
  Game.state = 'title';
  UI.resetKnight();
  UI.resetFoods();
  Game.knight.yaw = 0.85;
  Game.titleT = 0;
  UI.refreshBest();
  UI.show('title', true);
  window.__game = {
    get state() { return Game.state; },
    get score() { return Game.score; },
    get foodHp() { return Game.food; },
    get foodMax() { return FOOD_MAX; },
    get wave() { return Game.wave; },
    get ready() { return World.ready; },
    ants() { return Game.ants.map((a) => ({ x: a.x, z: a.z, y: a.y, alive: a.alive, state: a.state, flash: a.flash, spin: a.spin, type: a.type || 'ant', hp: a.hp, hpMax: a.hpMax, targetId: a.targetId || null })); },
    foods() { return (Game.foods || []).map((f) => ({ id: f.id, x: f.x, z: f.z, hp: f.hp, max: f.max, r: f.r, eatR: f.eatR, h: f.h })); },
    get best() { return store.get('best', 0); },
    get boss() { const b = Game.boss; return b ? { x: b.x, z: b.z, y: b.y, alive: b.alive, state: b.state, hp: b.hp, hpMax: b.hpMax } : null; },
    get lastBonus() { return Game.lastBonus; },
    bear() { const b = Game.bear; return b ? { on: !!b.on, t: b.t } : { on: false, t: 0 }; },
    startBear() { startBearDance(); updateBear(0); syncSprites(); World.updateCam(0); World.renderer.render(World.scene, World.camera); },
    basketTap() { registerBasketTap(); },
    watchers() {
      return (World.watcherSpr || []).map((spr, i) => {
        const w = WATCHERS[i];
        const mid = new THREE.Vector3(w.x, w.h * 0.5, w.z).project(World.camera);
        const feet = new THREE.Vector3(w.x, 0, w.z).project(World.camera);
        const head = new THREE.Vector3(w.x, w.h, w.z).project(World.camera);
        return {
          id: w.id, x: w.x, z: w.z, h: w.h,
          opacity: spr.mesh.material.opacity,
          visible: !!(spr.mesh.visible && spr.mesh.material.opacity > 0.08),
          mid: { x: mid.x, y: mid.y },
          feet: { x: feet.x, y: feet.y },
          head: { x: head.x, y: head.y }
        };
      });
    },
    setWatcher(i, x, z, h) {
      if (!WATCHERS[i]) return;
      if (x != null) WATCHERS[i].x = x;
      if (z != null) WATCHERS[i].z = z;
      if (h != null) WATCHERS[i].h = h;
      updateWatchers();
      World.updateCam(0);
      World.renderer.render(World.scene, World.camera);
    },
    knight() { const k = Game.knight; return { x: k.x, z: k.z, yaw: k.yaw, view: k.view, face: k.face, anim: k.anim, speed: k.speed, vx: k.vx, vz: k.vz }; },
    input() { return { x: Input.x, z: Input.z, padX: Input.padX, padZ: Input.padZ }; },
    screenPos() {
      const k = Game.knight;
      const v = new THREE.Vector3(k.x, 0.35, k.z);
      v.project(World.camera);
      return { x: (v.x * 0.5 + 0.5) * window.innerWidth, y: (-v.y * 0.5 + 0.5) * window.innerHeight, nx: v.x, ny: v.y };
    },
    freeze(on) { loop.frozen = !!on; if (!on) loop._t = performance.now() * 0.001; },
    step(dt) {
      dt = Math.max(0, Math.min(1 / 30, dt));
      if (Game.state === 'steal') { Game.t += dt; updateSteal(dt); }
      else if (Game.state === 'play') {
        if (Game.hitStop > 0) Game.hitStop = Math.max(0, Game.hitStop - dt);
        else { Game.t += dt; updatePlay(dt); }
      } else if (Game.state === 'title') { updateTitle(dt); }
      syncSprites();
      World.updateCam(dt);
      World.updateArrow();
      World.renderer.render(World.scene, World.camera);
    },
    syncNow() {
      syncSprites();
      World.updateCam(0);
      World.updateArrow();
      World.renderer.render(World.scene, World.camera);
    },
    get stormyH() { return STORMY_H; },
    get emmaH() { return EMMA_H; },
    setAntVel(i, vx, vz) {
      const a = Game.ants[i];
      if (!a) return;
      a.vx = vx; a.vz = vz;
      a.speed = Math.hypot(vx, vz);
    },
    movers() {
      const out = [];
      const push = (kind, spr, rec) => {
        if (!spr || !spr.mesh || !spr.mesh.visible) return;
        const p = spr.mesh.position;
        const scr = projectScreen(p.x, p.y + (spr.h || 0) * 0.35, p.z);
        out.push({
          kind, x: p.x, z: p.z, y: p.y,
          vx: rec && rec.vx != null ? rec.vx : 0,
          vz: rec && rec.vz != null ? rec.vz : 0,
          face: rec && rec.face != null ? rec.face : (spr.face != null ? spr.face : (spr.mesh.scale.x < 0 ? -1 : 1)),
          scaleX: (spr.mesh.material.userData.uFlip ? spr.mesh.material.userData.uFlip.value : (spr.mesh.scale.x < 0 ? -1 : 1)) * Math.abs(spr.mesh.scale.x),
          h: spr.h,
          sx: scr.x, sy: scr.y
        });
      };
      if (Game.state === 'title') {
        const recs = World._titleMovers || [];
        recs.forEach((r) => {
          let spr = null;
          if (r.kind === 'stormy') spr = World.stormySpr;
          else if (r.kind === 'emma') spr = World.emmaSpr;
          else if (r.kind === 'ant') {
            spr = (World.titleAntSpr || []).find((s) => s.mesh.visible && Math.abs(s.mesh.position.x - r.x) < 0.001 && Math.abs(s.mesh.position.z - r.z) < 0.001);
          }
          if (spr) push(r.kind, spr, r);
        });
      } else if (Game.state === 'steal' && Game.steal) {
        const pose = stealPose(Game.steal.t, Game.steal.who, Game.steal.grabbed);
        push('stormy', World.stormySpr, pose.stormy);
        push('emma', World.emmaSpr, pose.emma);
      } else {
        (Game.ants || []).forEach((a, i) => {
          const spr = World.antSpr[i];
          if (spr && a && a.state !== 'poof') push(a.type || 'ant', spr, a);
        });
      }
      return out;
    },
    camYaw() { return World.camYaw; },
    camYawTarget() { return World.camYawTarget; },
    setCamYaw(y, snapPos) {
      World.camYaw = y; World.camYawTarget = y;
      if (snapPos !== false) World.snapCam();
    },
    setCamRate(r) { Input.kbYaw = r; Input._qDown = r < 0 ? 1 : 0; Input._eDown = r > 0 ? 1 : 0; Input._qT = Input._eT = 0; },
    foodFade() {
      const list = [{ name: 'sandwich', fade: World.foodSpr._fade || 0, opacity: World.foodSpr.mesh.material.opacity }];
      (World.decos || []).forEach((s, i) => list.push({ name: DECOS[i][0], fade: s._fade || 0, opacity: s.mesh.material.opacity }));
      return list;
    },
    start() { UI.startFromTitle(); },
    slash() { Input.slashEdge = true; Input.slashFromTouch = false; },
    spin() { Input.spinEdge = true; },
    setMove(x, z) { Input.kbX = x; Input.kbZ = z; },
    setYaw(y) { Game.knight.yaw = y; },
    camUnlock() { World.camLock = 0; World.lookLock = null; },
    lockCamView(px, py, pz, lx, ly, lz) {
      World.camLock = 8;
      World.lookLock = { x: lx, y: ly, z: lz };
      World.cam.x = px; World.cam.y = py; World.cam.z = pz;
      World.camera.position.set(px, py, pz);
      World.camera.lookAt(lx, ly, lz);
    },
    setPos(x, z) {
      Game.knight.x = x; Game.knight.z = z;
      Game.knight.vx = 0; Game.knight.vz = 0; Game.knight.speed = 0;
      World.camLock = 0; World.lookLock = null;
      World.snapCam();
    },
    clearBaddies() { Game.ants = []; Game.spawnLeft = 0; Game.spawnQueue = []; Game.waveT = 99; Game._nextArm = 99; Game.boss = null; },
    freezeAnts() { Game.ants.forEach((a) => { a.speed = 0; a.vx = 0; a.vz = 0; }); },
    readySpin() { const k = Game.knight; k.spinCd = 0; k.spinT = 0; k.slashT = 0; k.anim = 'idle'; k.at = 0; },
    poseScale() {
      const k = Game.knight;
      k.x = FOOD.x + 0.88; k.z = FOOD.z + 0.08; k.yaw = Math.PI * 0.5; k.anim = 'idle'; k.at = 0;
      Input.kbX = 0; Input.kbZ = 0;
      World.camLock = 8;
      World.camYaw = Math.PI;
      World.camYawTarget = Math.PI;
      World.cam.x = (k.x + FOOD.x) * 0.5;
      World.cam.y = 1.65;
      World.cam.z = k.z + 2.85;
      World.camera.position.set(World.cam.x, World.cam.y, World.cam.z);
      World.camera.lookAt((k.x + FOOD.x) * 0.5, 0.42, (k.z + FOOD.z) * 0.5);
    },
    poseWalk(dirx, dirz) {
      Input.kbX = dirx; Input.kbZ = dirz;
      const dir = camMove(dirx, dirz);
      Game.knight.yaw = Math.atan2(dir.x, -dir.z);
      World.camLock = 0;
      World.snapCam();
    },
    spawnAntAt(x, z) { makeAnt(x, z, { type: 'ant' }); return Game.ants.length - 1; },
    spawnBugAt(kind, x, z) { spawnBug(kind || 'ant', x, z); return Game.ants.length - 1; },
    setAntPos(i, x, z, y) {
      const a = Game.ants[i];
      if (!a) return;
      a.x = x; a.z = z;
      if (y != null) a.y = y;
    },
    setAntHp(i, hp) { const a = Game.ants[i]; if (a) { a.hp = hp; if (a.hpMax == null || a.hpMax < hp) a.hpMax = hp; } },
    startBoss() { return startBoss(); },
    setTitleT(v) { Game.state = 'title'; Game.titleT = Math.max(0, v); updateTitle(0); UI.show('title', true); document.body.classList.remove('inplay','steal','pause','lose','clear'); },
    resetFoods() { UI.resetFoods(); },
    setFoodHp(id, v) {
      if (typeof id === 'number' && (v == null || v === undefined)) {
        const foods = Game.foods || [];
        if (!foods.length) { Game.food = Math.max(0, id); }
        else {
          let left = Math.max(0, id);
          for (const f of foods) {
            f.hp = Math.min(f.max, left);
            left = Math.max(0, left - f.hp);
          }
        }
      } else {
        const f = foodById(id);
        if (f) f.hp = Math.max(0, v);
      }
      Game.food = sumFood();
      UI.hud();
      if (Game.food <= 0 && Game.state === 'play') UI.lose();
    },
    pause() { UI.togglePause(); },
    get timeLeft() { return Game.timeLeft; },
    get round() { return Game.round; },
    get bannerT() { return Game.bannerT; },
    steal() { const s = Game.steal; return s ? { t: s.t, who: s.who, grabbed: s.grabbed, sausageOn: s.sausageOn, dur: s.dur } : null; },
    startSteal() { UI.startSteal(); },
    skipSteal() { UI.skipSteal(); },
    setTimeLeft(v) { Game.timeLeft = Math.max(0, v); UI.hud(); if (Game.timeLeft <= 0 && Game.state === 'play') UI.roundClear(); },
    ensurePlay() {
      if (Game.state === 'steal') UI.endSteal();
      if (Game.state === 'clear' || Game.state === 'lose' || Game.state === 'pause') {
        Game.state = 'play';
        document.body.classList.remove('clear','lose','pause','steal');
        document.body.classList.add('inplay');
        UI.show('clear', false); UI.show('lose', false); UI.show('pause', false);
        UI.showBanner(false);
      }
      if (Game.state === 'play' && Game.timeLeft < 60) Game.timeLeft = ROUND_TIME;
      UI.hud();
    },
    endRound() { UI.roundClear(); },
    nextRound() { UI.nextRound(); },
    poseSteal(who) {
      if (Game.state !== 'steal') {
        if (Game.state === 'title' || Game.state === 'boot') UI.beginPlay();
        else UI.startSteal();
      }
      if (who) Game.steal.who = who;
      Game.steal.t = 2.02;
      Game.steal.grabbed = true;
      Game.steal.sausageOn = false;
      World.showSausage(false);
      World.placeDogsForSteal(Game.steal.t, Game.steal.who, true);
      const k = Game.knight;
      k.x = 1.15; k.z = 2.18; k.yaw = -0.85; k.anim = 'idle';
      World.lockStealCam();
      loop.frozen = true;
      UI.hud();
      syncSprites();
      World.updateCam(0);
      World.renderer.render(World.scene, World.camera);
    }
  };
  requestAnimationFrame(loop);
}
boot();
