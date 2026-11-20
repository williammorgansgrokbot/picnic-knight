#!/usr/bin/env python3
"""Picnic Knight — 75% sandwich QA: ant visible over it, clips, console."""
import time, json
from pathlib import Path
from playwright.sync_api import sync_playwright

SHOTS = Path('/workspace/picnic-knight/shots')
SHOTS.mkdir(exist_ok=True)
URL = 'http://127.0.0.1:8767/index.html'
SIZES = [(844, 390), (932, 430), (667, 375)]
FX, FZ = -1.15, -0.25
EAT_R = 0.435

def collect_clip(page):
    return page.evaluate('''() => {
      const ids = ['pad','slashBtn','spinBtn','topLeft','meterWrap','topRight','timerPanel','timerNum',
        'btnPlay','logo','btnPause','btnMute','waveNum','scoreNum','arrow','banner','skipHint','cNext','cTitle'];
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
        const clip = r.left < -2 || r.top < -2 || r.right > w+2 || r.bottom > h+2;
        if (clip) out.push({id, left:r.left, top:r.top, right:r.right, bottom:r.bottom, w, h});
      }
      return out;
    }''')

def ev(page, js):
    return page.evaluate(js)

def boot(page):
    page.goto(URL, wait_until='networkidle', timeout=30000)
    page.wait_for_function('window.__game && window.__game.ready === true', timeout=20000)

def start_play(page):
    ev(page, '''() => {
      if (window.__game.state === "title" || window.__game.state === "boot") window.__game.start();
      if (window.__game.state === "steal") window.__game.skipSteal();
      if (window.__game.ensurePlay) window.__game.ensurePlay();
      window.__game.clearBaddies();
      window.__game.freeze(true);
      window.__game.setTimeLeft(180);
      const el = document.getElementById("banner");
      if (el) el.classList.remove("show");
    }''')
    page.wait_for_function('window.__game.state === "play"', timeout=8000)

def pose_default(page, kx=None, kz=None):
    kx = FX if kx is None else kx
    kz = 1.20 if kz is None else kz
    ev(page, f'''() => {{
      window.__game.setMove(0,0);
      window.__game.setPos({kx}, {kz});
      window.__game.setYaw(0);
      window.__game.setCamYaw(0);
      window.__game.camUnlock();
    }}''')
    ev(page, '() => window.__game.step(0)')

def run():
    errs = []
    clips_all = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=['--use-gl=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--autoplay-policy=no-user-gesture-required'])
        ctx = b.new_context(viewport={'width':844,'height':390}, device_scale_factor=1, has_touch=True)
        page = ctx.new_page()
        pe = []
        page.on('console', lambda m: (m.type=='error' and (pe.append('console:'+m.text), print('ERR', m.text))))
        page.on('pageerror', lambda e: (pe.append('page:'+str(e)), print('PAGE', e)))
        boot(page)
        start_play(page)
        pose_default(page)

        ev(page, f'''() => {{
          window.__game.clearBaddies();
          window.__game.spawnAntAt({FX}, {FZ - 0.45});
          window.__game.spawnAntAt({FX}, {FZ - 0.70});
          window.__game.spawnAntAt({FX}, {FZ - 1.00});
          window.__game.spawnAntAt({FX - 0.15}, {FZ - 0.55});
          window.__game.freezeAnts();
        }}''')
        ev(page, '() => window.__game.step(0)')
        time.sleep(0.12)
        print('MULTI ants', ev(page, '() => window.__game.ants()'))
        page.screenshot(path=str(SHOTS/'844x390_sandwich_ants_behind_multi.png'))

        ev(page, f'''() => {{
          window.__game.clearBaddies();
          window.__game.spawnAntAt({FX}, {FZ - 0.55});
          window.__game.freezeAnts();
        }}''')
        ev(page, '() => window.__game.step(0)')
        time.sleep(0.12)
        print('ONE 0.55', ev(page, '() => window.__game.ants()'))
        page.screenshot(path=str(SHOTS/'844x390_sandwich_ant_over.png'))

        ev(page, f'''() => {{
          window.__game.clearBaddies();
          window.__game.spawnAntAt({FX}, {FZ - 0.85});
          window.__game.freezeAnts();
        }}''')
        ev(page, '() => window.__game.step(0)')
        time.sleep(0.1)
        print('ONE 0.85', ev(page, '() => window.__game.ants()'))
        page.screenshot(path=str(SHOTS/'844x390_sandwich_ant_over_far.png'))

        ev(page, f'''() => {{
          window.__game.clearBaddies();
          window.__game.spawnAntAt({FX}, {FZ - EAT_R + 0.02});
          window.__game.freezeAnts();
        }}''')
        ev(page, '() => window.__game.step(0.05)')
        time.sleep(0.1)
        print('EAT behind', ev(page, '() => window.__game.ants()'))
        page.screenshot(path=str(SHOTS/'844x390_sandwich_ant_eat_behind.png'))

        ev(page, f'''() => {{
          window.__game.clearBaddies();
          window.__game.setPos(0.45, 1.90);
          window.__game.setYaw(0);
          window.__game.setCamYaw(0);
          window.__game.spawnAntAt({FX + 0.35}, {FZ - 0.35});
          window.__game.spawnAntAt({FX - 0.50}, {FZ + 0.20});
          window.__game.freezeAnts();
        }}''')
        ev(page, '() => window.__game.step(0)')
        time.sleep(0.1)
        page.screenshot(path=str(SHOTS/'844x390_sandwich_gameplay.png'))

        clips = collect_clip(page)
        if clips:
            print('CLIP 844', clips)
            clips_all += [{'where':'844-play', **c} for c in clips]
        errs.extend(pe)
        ctx.close()

        for w, h in SIZES:
            tag = f'{w}x{h}'
            c = b.new_context(viewport={'width':w,'height':h}, device_scale_factor=1, has_touch=True)
            pg = c.new_page()
            pe2 = []
            pg.on('console', lambda m: (m.type=='error' and pe2.append('console:'+m.text)))
            pg.on('pageerror', lambda e: pe2.append('page:'+str(e)))
            boot(pg)
            start_play(pg)
            ev(pg, f'''() => {{
              window.__game.setMove(0,0);
              window.__game.setPos(0.45, 1.90);
              window.__game.setYaw(0);
              window.__game.setCamYaw(0);
              window.__game.clearBaddies();
              window.__game.spawnAntAt({FX}, {FZ - 0.55});
              window.__game.freezeAnts();
            }}''')
            ev(pg, '() => window.__game.step(0)')
            time.sleep(0.08)
            pg.screenshot(path=str(SHOTS / f'{tag}_sandwich_play.png'))
            cl = collect_clip(pg)
            if cl:
                print('CLIP', tag, cl)
                clips_all += [{'where':tag+'-play', **x} for x in cl]
            if pe2:
                print('ERR', tag, pe2)
                errs.extend([tag+':'+e for e in pe2])
            c.close()
        b.close()

    if clips_all:
        print('CLIPS FOUND', json.dumps(clips_all, indent=2))
        errs.append('HUD clipped: ' + ', '.join(c['where']+':'+c['id'] for c in clips_all))
    print('RESULT', 'FAIL' if errs else 'PASS')
    for e in errs:
        print(' -', e)
    return 0 if not errs else 1

if __name__ == '__main__':
    raise SystemExit(run())
