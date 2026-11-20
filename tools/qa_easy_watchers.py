#!/usr/bin/env python3
"""90s timer, spectators, bear easter egg: console, clips, official shots."""
import json, math
from pathlib import Path
from playwright.sync_api import sync_playwright

SHOTS = Path('/workspace/picnic-knight/shots')
SHOTS.mkdir(exist_ok=True)
URL = 'http://127.0.0.1:8767/index.html'
SIZES = [(844, 390), (932, 430), (667, 375)]
NOISE = ('ReadPixels', 'GPU stall', 'swiftshader')

def ev(page, js):
    return page.evaluate(js)

def collect_clip(page):
    return ev(page, '''() => {
      const ids = ['pad','slashBtn','spinBtn','topLeft','meterWrap','topRight','timerPanel','timerNum',
        'btnPlay','logo','btnPause','btnMute','btnMuteTitle','waveNum','scoreNum','arrow','banner',
        'bestScore','perks'];
      const w = window.innerWidth, h = window.innerHeight;
      const out = [];
      for (const id of ids) {
        const el = document.getElementById(id);
        if (!el) continue;
        const st = getComputedStyle(el);
        if (st.display === 'none' || st.visibility === 'hidden' || Number(st.opacity) === 0) continue;
        const screen = el.closest('.screen');
        if (screen && !screen.classList.contains('show')) continue;
        const r = el.getBoundingClientRect();
        if (!r.width && !r.height) continue;
        if (r.left < -2 || r.top < -2 || r.right > w+2 || r.bottom > h+2)
          out.push({id, left:r.left, top:r.top, right:r.right, bottom:r.bottom, w, h});
      }
      return out;
    }''')

def boot(page):
    page.goto(URL, wait_until='networkidle', timeout=45000)
    page.wait_for_function('window.__game && window.__game.ready === true', timeout=25000)

def attach(page, bucket):
    page.on('console', lambda m: (m.type in ('error','assert') and not any(k.lower() in (m.text or '').lower() for k in NOISE) and bucket.append('console:'+m.text)))
    page.on('pageerror', lambda e: bucket.append('page:'+str(e)))

def hide_banner(page):
    ev(page, '''() => {
      const b = document.getElementById("banner");
      if (b) { b.classList.remove("show"); b.style.display = "none"; }
    }''')

def to_play(page):
    ev(page, '''() => {
      if (window.__game.state === "title" || window.__game.state === "boot") window.__game.start();
      if (window.__game.state === "steal") window.__game.skipSteal();
      if (window.__game.ensurePlay) window.__game.ensurePlay();
      window.__game.clearBaddies();
      window.__game.freeze(true);
      window.__game.setTimeLeft(90);
      if (window.__game.setPos) window.__game.setPos(0.2, 0.4);
    }''')
    hide_banner(page)

def sync(page):
    ev(page, '() => window.__game.syncNow ? window.__game.syncNow() : window.__game.step(0)')

def run():
    errs, clips, info = [], [], {}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--use-gl=swiftshader','--ignore-gpu-blocklist'], headless=True)
        pe = []
        ctx = browser.new_context(viewport={'width':844,'height':390}, device_scale_factor=1, has_touch=True)
        page = ctx.new_page(); attach(page, pe)
        boot(page)
        ev(page, '() => window.__game.freeze(true)')
        ev(page, '() => { window.__game.setTitleT(2.85); window.__game.syncNow && window.__game.syncNow(); }')
        page.screenshot(path=str(SHOTS/'844x390_easy_title.png'))

        to_play(page)
        ev(page, '() => window.__game.setTimeLeft(90)')
        ev(page, '''() => {
          window.__game.clearBaddies();
          window.__game.spawnAntAt(-1.6, 1.1);
          window.__game.spawnAntAt(1.2, 0.6);
          window.__game.spawnBugAt && window.__game.spawnBugAt("beetle", 0.4, -1.1);
        }''')
        ev(page, '() => window.__game.setCamYaw(0)')
        sync(page)
        hud = ev(page, '''() => {
          const t = document.getElementById("timerNum");
          return { state: window.__game.state, timeLeft: window.__game.timeLeft, timerText: t && t.textContent };
        }''')
        info['hud'] = hud
        print('HUD', hud)
        if hud.get('timerText') != '1:30':
            errs.append('Timer HUD is %r, expected 1:30' % hud.get('timerText'))
        page.screenshot(path=str(SHOTS/'844x390_easy_timer.png'))

        for name, yaw in [('yaw0', 0.0), ('yaw90', math.pi/2), ('yaw180', math.pi)]:
            ev(page, f'''() => {{
              window.__game.setPos(0.2, 0.4);
              window.__game.setCamYaw({yaw});
            }}''')
            sync(page)
            path = SHOTS / f'844x390_easy_watchers_{name}.png'
            page.screenshot(path=str(path))
            print('shot', path)

        # bear mid-shimmy: pop 0.42 + ~0.9s of dance
        ev(page, '''() => {
          window.__game.setCamYaw(0);
          window.__game.setPos(0.2, 0.4);
          window.__game.setTimeLeft(90);
          window.__game.freeze(false);
          window.__game.startBear();
          window.__game.freeze(true);
        }''')
        ev(page, '''() => { for (let i = 0; i < 36; i++) window.__game.step(1/30); }''')  # 1.2s
        hide_banner(page)
        sync(page)
        bear = ev(page, '() => window.__game.bear && window.__game.bear()')
        info['bear'] = bear
        print('bear', bear)
        page.screenshot(path=str(SHOTS/'844x390_easy_bear_shimmy.png'))
        if not (bear and bear.get('on') and bear.get('t', 0) > 0.4):
            errs.append('Bear was not mid-shimmy: %r' % bear)

        cl = collect_clip(page)
        if cl: clips += [{'where':'844-play', **c} for c in cl]
        if pe: errs += pe
        ctx.close()

        for w,h in SIZES:
            pe2=[]
            ctx=browser.new_context(viewport={'width':w,'height':h}, device_scale_factor=1, has_touch=True)
            pg=ctx.new_page(); attach(pg, pe2)
            boot(pg)
            ev(pg, '() => window.__game.freeze(true)')
            ev(pg, '() => { window.__game.setTitleT(2.85); window.__game.syncNow && window.__game.syncNow(); }')
            cl=collect_clip(pg)
            if cl: clips += [{'where':f'{w}x{h}-title', **c} for c in cl]
            to_play(pg)
            ev(pg, '() => { window.__game.setTimeLeft(90); window.__game.setCamYaw(0); }')
            sync(pg)
            cl=collect_clip(pg)
            if cl: clips += [{'where':f'{w}x{h}-play', **c} for c in cl]
            pg.screenshot(path=str(SHOTS/f'{w}x{h}_easy_play.png'))
            if pe2: errs += [f'{w}x{h}:'+e for e in pe2]
            ctx.close()
        browser.close()

    if clips:
        print('CLIPS', json.dumps(clips, indent=2))
        errs.append('HUD clipped: '+', '.join(c['where']+':'+c['id'] for c in clips))
    out={'info':info, 'clips':clips, 'errs':errs}
    Path('/tmp/pk-easy-watchers-qa.json').write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    if errs:
        print('FAIL'); return 1
    print('PASS'); return 0

if __name__ == '__main__':
    raise SystemExit(run())
