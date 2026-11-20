#!/usr/bin/env python3
import time, json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

SHOTS = Path('/workspace/picnic-knight/shots')
SHOTS.mkdir(exist_ok=True)
URL = 'http://127.0.0.1:8767/index.html'
SIZES = [(844, 390), (932, 430), (667, 375)]

def collect_clip(page):
    return page.evaluate('''() => {
      const ids = ['pad','slashBtn','spinBtn','topLeft','meterWrap','topRight','timerPanel','timerNum','btnPlay','logo','btnPause','btnMute','waveNum','scoreNum','arrow','banner','skipHint','cNext','cTitle'];
      const w = window.innerWidth, h = window.innerHeight;
      const out = [];
      for (const id of ids) {
        const el = document.getElementById(id);
        if (!el) continue;
        const st = getComputedStyle(el);
        if (st.display === 'none' || st.visibility === 'hidden' || st.opacity === '0') continue;
        if (el.closest('.screen') && !el.closest('.screen').classList.contains('show')) continue;
        const r = el.getBoundingClientRect();
        if (!r.width && !r.height) continue;
        const clip = r.left < -2 || r.top < -2 || r.right > w+2 || r.bottom > h+2;
        if (clip) out.push({id, left:r.left, top:r.top, right:r.right, bottom:r.bottom, w, h});
      }
      return out;
    }''')

def run():
    errs_all = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=['--use-gl=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--autoplay-policy=no-user-gesture-required'])
        for w,h in SIZES:
            tag = f'{w}x{h}'
            errs = []
            ctx = b.new_context(viewport={'width':w,'height':h}, device_scale_factor=1, has_touch=True)
            page = ctx.new_page()
            page.on('console', lambda m: (m.type=='error' and (errs.append('console:'+m.text), print('ERR', m.text))))
            page.on('pageerror', lambda e: (errs.append('page:'+str(e)), print('PAGE', e)))
            page.goto(URL, wait_until='networkidle', timeout=30000)
            page.wait_for_function('window.__game && window.__game.ready === true', timeout=20000)
            time.sleep(0.3)
            page.screenshot(path=str(SHOTS / f'{tag}_title.png'))
            clips = collect_clip(page)

            page.click('#btnPlay', force=True)
            page.wait_for_function('window.__game && (window.__game.state === "steal" || window.__game.state === "play")', timeout=8000)
            page.evaluate('() => { if (window.__game.state === "steal") window.__game.skipSteal(); }')
            page.wait_for_function('window.__game.state === "play"', timeout=8000)
            time.sleep(0.35)
            page.screenshot(path=str(SHOTS / f'{tag}_play.png'))
            clips += collect_clip(page)

            # scale shot
            page.evaluate('() => window.__game.poseScale()')
            time.sleep(0.15)
            page.screenshot(path=str(SHOTS / f'{tag}_scale.png'))

            # diagonal movement: knight should turn
            page.evaluate('() => { window.__game.setMove(0,0); window.__game.setPos(0.4, 1.8); window.__game.setYaw(0); window.__game.camUnlock(); }')
            before = page.evaluate('() => window.__game.knight()')
            page.evaluate('() => window.__game.setMove(0.75, -0.75)')
            time.sleep(0.45)
            after = page.evaluate('() => window.__game.knight()')
            turned = abs((after['yaw'] - before['yaw'])) > 0.3
            moved = (abs(after['x']-before['x']) + abs(after['z']-before['z'])) > 0.15
            print(tag, 'diag', before, '->', after, 'turned', turned, 'moved', moved)
            page.screenshot(path=str(SHOTS / f'{tag}_walk.png'))
            if not turned: errs.append('knight did not turn on diagonal move')
            if not moved: errs.append('knight did not move on diagonal input')

            # walk-away back view
            page.evaluate('() => { window.__game.setMove(0,0); window.__game.setPos(0.5, 2.2); window.__game.poseWalk(0, -1); }')
            time.sleep(0.5)
            wv = page.evaluate('() => window.__game.knight()')
            print(tag, 'walk back', wv)
            page.screenshot(path=str(SHOTS / f'{tag}_walk_back.png'))

            # slash kill + sequence
            page.evaluate('''() => {
              window.__game.setMove(0,0);
              window.__game.setPos(0.25, 1.15);
              window.__game.setYaw(Math.PI);
              window.__game.lockCamView(0.25, 1.78, 1.15 + 3.45, 0.25, 0.38, 1.05);
              window.__game.spawnAntAt(0.25, 1.15 + 0.60);
            }''')
            time.sleep(0.06)
            before = page.evaluate('() => ({score: window.__game.score, ants: window.__game.ants().filter(a=>a.alive).length})')
            page.keyboard.press('Space')
            # wait for a dead/launching ant or score bump
            seq = {'launch': False, 'down': False, 'poof': False}
            t0 = time.time()
            launch_shot = False
            while time.time() - t0 < 2.4:
                info = page.evaluate('() => ({score: window.__game.score, ants: window.__game.ants()})')
                for a in info['ants']:
                    if a['state'] == 'launch': seq['launch'] = True
                    if a['state'] == 'down': seq['down'] = True
                    if a['state'] == 'poof': seq['poof'] = True
                if seq['launch'] and not launch_shot:
                    page.screenshot(path=str(SHOTS / f'{tag}_kill_launch.png'))
                    launch_shot = True
                if seq['launch'] and seq['down']:
                    break
                time.sleep(0.04)
            # if poof already happened that's ok — launch must have occurred
            after = page.evaluate('() => ({score: window.__game.score, ants: window.__game.ants()})')
            killed = after['score'] > before['score'] or seq['launch'] or seq['down'] or seq['poof']
            print(tag, 'slash', before, 'seq', seq, 'killed', killed, 'score', after['score'])
            if not killed: errs.append('slash did not start a kill sequence')
            if not (seq['launch'] or seq['down'] or seq['poof'] or after['score'] > before['score']):
                errs.append('kill sequence did not play')

            # bite meter
            page.evaluate('() => window.__game.spawnAntAt(-1.15, -0.25)')
            hp0 = page.evaluate('() => window.__game.foodHp')
            time.sleep(0.8)
            hp1 = page.evaluate('() => window.__game.foodHp')
            drained = hp1 < hp0
            print(tag, 'bite', hp0, '->', hp1, 'drained', drained)
            if not drained: errs.append('bite meter did not drop')

            # lose
            page.evaluate('() => { window.__game.camUnlock(); window.__game.setPos(0.3, 1.3); window.__game.setFoodHp(0); }')
            page.wait_for_function('window.__game.state === "lose"', timeout=4000)
            time.sleep(0.2)
            page.screenshot(path=str(SHOTS / f'{tag}_lose.png'))
            clips += collect_clip(page)

            if clips: errs.append('clipping: '+json.dumps(clips))
            print(tag, 'clips', clips, 'errors', errs)
            errs_all.extend([tag+': '+e for e in errs])
            ctx.close()
        b.close()
    if errs_all:
        print('FAIL')
        for e in errs_all: print(' -', e)
        sys.exit(1)
    print('PASS')

if __name__ == '__main__':
    run()
