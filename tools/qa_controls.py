#!/usr/bin/env python3
"""Touch-emulated iPhone 844x390 control QA: screen-relative stick, speed, frame independence."""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

SHOTS = Path('/workspace/picnic-knight/shots')
SHOTS.mkdir(exist_ok=True)
URL = 'http://127.0.0.1:8767/index.html'
W, H = 844, 390
ORIGIN = (180, 300)
DIRS = {
    'up':    (180, 240),
    'right': (240, 300),
    'down':  (180, 360),
    'left':  (120, 300),
}

RESET_JS = """() => {
  window.__game.setMove(0,0);
  window.__game.setPos(0, 2.45);
  window.__game.setYaw(0);
  const yaw = window.__game.camYaw();
  const dist = 3.25, h = 2.22, lookY = 0.48;
  const k = window.__game.knight();
  const cx = k.x - Math.sin(yaw) * dist;
  const cz = k.z + Math.cos(yaw) * dist;
  window.__game.lockCamView(cx, h, cz, k.x + Math.sin(yaw)*0.18, lookY, k.z - Math.cos(yaw)*0.18);
}"""

def cdp_touch(cdp, typ, x=None, y=None):
    pts = [] if typ == 'touchEnd' else [{'x': float(x), 'y': float(y), 'id': 1}]
    cdp.send('Input.dispatchTouchEvent', {'type': typ, 'touchPoints': pts})

def ev(page, js):
    return page.evaluate(js)

def step_for(page, seconds, dt):
    n = int(round(seconds / dt))
    ev(page, f'() => {{ for (let i = 0; i < {n}; i++) window.__game.step({dt}); }}')
    return n

def run():
    errs = []
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--use-gl=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--autoplay-policy=no-user-gesture-required'])
        ctx = browser.new_context(
            viewport={'width': W, 'height': H},
            device_scale_factor=1,
            has_touch=True,
            is_mobile=True,
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        )
        page = ctx.new_page()
        page.on('console', lambda m: (m.type == 'error' and (errs.append('console:' + m.text), print('ERR', m.text))))
        page.on('pageerror', lambda e: (errs.append('page:' + str(e)), print('PAGE', e)))
        page.goto(URL, wait_until='networkidle', timeout=30000)
        page.wait_for_function('window.__game && window.__game.ready === true', timeout=20000)
        ev(page, '() => { document.body.classList.add("touch"); }')
        page.click('#btnPlay', force=True)
        page.wait_for_function('window.__game && (window.__game.state === "steal" || window.__game.state === "play")', timeout=8000)
        page.evaluate('() => { if (window.__game.state === "steal") window.__game.skipSteal(); }')
        page.wait_for_function('window.__game.state === "play"', timeout=8000)
        time.sleep(0.2)
        ev(page, '''() => {
          window.__game.freeze(true);
          window.__game.clearBaddies();
          window.__game.setMove(0,0);
          window.__game.setPos(0, 2.45);
          window.__game.setYaw(0);
        }''')
        cdp = page.context.new_cdp_session(page)

        for name, (tx, ty) in DIRS.items():
            ev(page, RESET_JS)
            ev(page, '() => window.__game.step(0)')
            before = ev(page, '() => ({k: window.__game.knight(), s: window.__game.screenPos(), cam: window.__game.camYaw()})')
            cdp_touch(cdp, 'touchStart', ORIGIN[0], ORIGIN[1])
            time.sleep(0.03)
            cdp_touch(cdp, 'touchMove', tx, ty)
            time.sleep(0.03)
            mid = ev(page, '''() => ({
              inp: window.__game.input(),
              pad: document.getElementById("pad").classList.contains("show"),
              prect: (() => { const r = document.getElementById("pad").getBoundingClientRect();
                return {l:r.left,t:r.top,w:r.width,h:r.height,cx:r.left+r.width/2,cy:r.top+r.height/2}; })()
            })''')
            step_for(page, 0.45, 1/60)
            after = ev(page, '() => ({k: window.__game.knight(), s: window.__game.screenPos(), cam: window.__game.camYaw()})')
            if name in ('up', 'right'):
                page.screenshot(path=str(SHOTS / f'844x390_stick_{name}.png'))
            cdp_touch(cdp, 'touchEnd')
            time.sleep(0.02)
            ev(page, '() => { window.__game.setMove(0,0); window.__game.camUnlock(); window.__game.step(0); }')

            dsx = after['s']['x'] - before['s']['x']
            dsy = after['s']['y'] - before['s']['y']
            results[name] = {
                'dsx': dsx, 'dsy': dsy,
                'before': before, 'after': after,
                'inp': mid['inp'], 'pad': mid['pad'], 'prect': mid['prect'],
                'cam_before': before['cam'], 'cam_after': after['cam'],
            }
            print(f'DIR {name}: screen d=({dsx:.1f},{dsy:.1f}) inp={mid["inp"]} pad={mid["pad"]} cam {before["cam"]}->{after["cam"]} world ({before["k"]["x"]:.3f},{before["k"]["z"]:.3f})->({after["k"]["x"]:.3f},{after["k"]["z"]:.3f}) start_s=({before["s"]["x"]:.1f},{before["s"]["y"]:.1f}) end_s=({after["s"]["x"]:.1f},{after["s"]["y"]:.1f})')

            if not mid['pad']:
                errs.append(f'{name}: joystick base did not appear')
            if abs(mid['prect']['w'] - 120) > 8 or abs(mid['prect']['h'] - 120) > 8:
                errs.append(f'{name}: pad size {mid["prect"]} not ~120px')
            if mid['prect']['l'] < -2 or mid['prect']['t'] < -2 or mid['prect']['l']+mid['prect']['w'] > W+2 or mid['prect']['t']+mid['prect']['h'] > H+2:
                errs.append(f'{name}: pad clipped {mid["prect"]}')
            dist_origin = ((mid['prect']['cx']-ORIGIN[0])**2 + (mid['prect']['cy']-ORIGIN[1])**2) ** 0.5
            if dist_origin > 8:
                errs.append(f'{name}: pad center {mid["prect"]["cx"]:.1f},{mid["prect"]["cy"]:.1f} not at first touch {ORIGIN} (d={dist_origin:.1f})')

            slop = 12
            if name == 'up':
                if dsy >= -18: errs.append(f'up: expected screen y to decrease, dsy={dsy:.1f}')
                if abs(dsx) > abs(dsy) * 0.45 + slop: errs.append(f'up: too much horizontal drift dsx={dsx:.1f}')
            elif name == 'down':
                if dsy <= 18: errs.append(f'down: expected screen y to increase, dsy={dsy:.1f}')
                if abs(dsx) > abs(dsy) * 0.45 + slop: errs.append(f'down: too much horizontal drift dsx={dsx:.1f}')
            elif name == 'right':
                if dsx <= 18: errs.append(f'right: expected screen x to increase, dsx={dsx:.1f}')
                if abs(dsy) > abs(dsx) * 0.45 + slop: errs.append(f'right: too much vertical drift dsy={dsy:.1f}')
            elif name == 'left':
                if dsx >= -18: errs.append(f'left: expected screen x to decrease, dsx={dsx:.1f}')
                if abs(dsy) > abs(dsx) * 0.45 + slop: errs.append(f'left: too much vertical drift dsy={dsy:.1f}')

            if abs(after['cam']) > 0.01:
                errs.append(f'{name}: camera yaw drifted to {after["cam"]}')

        # speed (follow cam ok; measure world distance)
        ev(page, '() => { window.__game.camUnlock(); window.__game.setMove(0,0); window.__game.setPos(0, 2.45); window.__game.setYaw(0); }')
        ev(page, '() => window.__game.setMove(0, -1)')
        step_for(page, 0.25, 1/60)
        k0 = ev(page, '() => window.__game.knight()')
        step_for(page, 0.50, 1/60)
        k1 = ev(page, '() => window.__game.knight()')
        dist = ((k1['x']-k0['x'])**2 + (k1['z']-k0['z'])**2) ** 0.5
        speed = dist / 0.50
        results['speed'] = {'dist': dist, 'speed': speed, 'instant': k1['speed'], 'a': k0, 'b': k1}
        print(f'SPEED 0.5s after accel: {speed:.3f} u/s (instant {k1["speed"]:.3f}) target 1.34-1.68 (~45% of 3.35)')
        if not (1.34 <= speed <= 1.68):
            errs.append(f'speed {speed:.3f} not in 1.34-1.68')
        ev(page, '() => window.__game.setMove(0,0)')

        def travel(label, dts):
            ev(page, '() => { window.__game.camUnlock(); window.__game.setMove(0,0); window.__game.setPos(0, 2.45); window.__game.setYaw(0); }')
            ev(page, '() => window.__game.setMove(0, -1)')
            total = 0.0
            for dt in dts:
                ev(page, f'() => window.__game.step({dt})')
                total += dt
            k = ev(page, '() => window.__game.knight()')
            ev(page, '() => window.__game.setMove(0,0)')
            d = ((k['x']-0)**2 + (k['z']-2.45)**2) ** 0.5
            print(f'FRAMERATE {label}: t={total:.3f}s dist={d:.4f} speed={k["speed"]:.3f}')
            return d

        d60 = travel('60fps', [1/60] * 60)
        d120 = travel('120fps', [1/120] * 120)
        mixed, acc, seq, i = [], 0.0, [1/60, 1/120, 1/90, 1/45, 1/75], 0
        while acc < 1.0 - 1e-9:
            dt = min(seq[i % len(seq)], 1.0 - acc)
            mixed.append(dt)
            acc += dt
            i += 1
        dmix = travel('mixed', mixed)
        results['framerate'] = {'d60': d60, 'd120': d120, 'dmix': dmix}

        def close(a, b, tol=0.04):
            return abs(a-b) <= tol * max(abs(a), abs(b), 1e-6)
        if not close(d60, d120, 0.03):
            errs.append(f'60 vs 120 fps travel mismatch: {d60:.4f} vs {d120:.4f}')
        if not close(d60, dmix, 0.04):
            errs.append(f'60 vs mixed-dt travel mismatch: {d60:.4f} vs {dmix:.4f}')

        ev(page, '() => window.__game.freeze(false)')
        ctx.close()
        browser.close()

    Path('/tmp/pk-controls-qa.json').write_text(json.dumps(results, indent=2, default=str))
    if errs:
        print('FAIL')
        for e in errs: print(' -', e)
        sys.exit(1)
    print('PASS')

if __name__ == '__main__':
    run()
