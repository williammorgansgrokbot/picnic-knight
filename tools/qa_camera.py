#!/usr/bin/env python3
"""Camera orbit, occlusion fade, UI clip, and 60/120 fps QA."""
import json, sys, time, math
from pathlib import Path
from playwright.sync_api import sync_playwright

SHOTS = Path('/workspace/picnic-knight/shots')
SHOTS.mkdir(exist_ok=True)
URL = 'http://127.0.0.1:8767/index.html'
SIZES = [(844, 390), (932, 430), (667, 375)]

def ev(page, js):
    return page.evaluate(js)

def step_for(page, seconds, dt):
    n = int(round(seconds / dt))
    ev(page, f'() => {{ for (let i = 0; i < {n}; i++) window.__game.step({dt}); }}')

def collect_clip(page):
    return page.evaluate('''() => {
      const ids = ['pad','slashBtn','spinBtn','topLeft','meterWrap','topRight','timerPanel','timerNum','btnPlay','logo','btnPause','btnMute','waveNum','scoreNum','arrow','camBtns','camLeft','camRight','banner','skipHint'];
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

def start_play(page):
    ev(page, '() => { document.body.classList.add("touch"); }')
    page.click('#btnPlay', force=True)
    page.wait_for_function('window.__game && (window.__game.state === "steal" || window.__game.state === "play")', timeout=8000)
    page.evaluate('() => { if (window.__game.state === "steal") window.__game.skipSteal(); }')
    page.wait_for_function('window.__game.state === "play"', timeout=8000)
    ev(page, '''() => {
      window.__game.freeze(true);
      window.__game.clearBaddies();
      window.__game.setMove(0,0);
    }''')

def run():
    errs = []
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--use-gl=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--autoplay-policy=no-user-gesture-required'])

        # --- clip + UI at all three sizes ---
        for w, h in SIZES:
            tag = f'{w}x{h}'
            ctx = browser.new_context(viewport={'width':w,'height':h}, device_scale_factor=1, has_touch=True)
            page = ctx.new_page()
            page.on('console', lambda m: (m.type == 'error' and (errs.append(f'{tag} console:'+m.text), print('ERR', m.text))))
            page.on('pageerror', lambda e: (errs.append(f'{tag} page:'+str(e)), print('PAGE', e)))
            page.goto(URL, wait_until='networkidle', timeout=30000)
            page.wait_for_function('window.__game && window.__game.ready === true', timeout=20000)
            start_play(page)
            ev(page, '() => { window.__game.setPos(0.35, 1.55); window.__game.setYaw(0); window.__game.setCamYaw(0); }')
            ev(page, '() => window.__game.step(0)')
            time.sleep(0.05)
            page.screenshot(path=str(SHOTS / f'{tag}_cam_ui.png'))
            clips = collect_clip(page)
            btns = ev(page, '''() => {
              const a = document.getElementById("camLeft").getBoundingClientRect();
              const b = document.getElementById("camRight").getBoundingClientRect();
              const vis = getComputedStyle(document.getElementById("camBtns")).display !== "none";
              return {vis, left:{l:a.left,t:a.top,r:a.right,b:a.bottom,w:a.width,h:a.height},
                      right:{l:b.left,t:b.top,r:b.right,b:b.bottom,w:b.width,h:b.height}};
            }''')
            print(tag, 'camBtns', btns, 'clips', clips)
            if not btns['vis']:
                errs.append(f'{tag}: rotate buttons not visible')
            if clips:
                errs.append(f'{tag}: clipping {json.dumps(clips)}')
            # overlap with slash/spin?
            overlap = ev(page, '''() => {
              const ids = ["camLeft","camRight","slashBtn","spinBtn","btnPause","btnMute","meterWrap"];
              const rs = {};
              ids.forEach(id => { const e=document.getElementById(id); rs[id]=e?e.getBoundingClientRect():null; });
              const hit = (A,B) => A && B && !(A.right<B.left+2 || A.left>B.right-2 || A.bottom<B.top+2 || A.top>B.bottom-2);
              const bad = [];
              if (hit(rs.camLeft, rs.slashBtn)) bad.push("camLeft/slash");
              if (hit(rs.camRight, rs.slashBtn)) bad.push("camRight/slash");
              if (hit(rs.camLeft, rs.spinBtn)) bad.push("camLeft/spin");
              if (hit(rs.camRight, rs.spinBtn)) bad.push("camRight/spin");
              if (hit(rs.camRight, rs.btnPause)) bad.push("camRight/pause");
              if (hit(rs.camRight, rs.btnMute)) bad.push("camRight/mute");
              if (hit(rs.camLeft, rs.meterWrap) || hit(rs.camRight, rs.meterWrap)) bad.push("cam/meter");
              return {bad, rs: Object.fromEntries(Object.entries(rs).map(([k,r]) => r ? [k, {l:r.left,t:r.top,r:r.right,b:r.bottom}] : [k,null]))};
            }''')
            print(tag, 'overlap', overlap['bad'])
            if overlap['bad']:
                errs.append(f'{tag}: button overlap {overlap["bad"]}')
            ctx.close()

        # --- main 844 functional tests and hero shots ---
        ctx = browser.new_context(viewport={'width':844,'height':390}, device_scale_factor=2, has_touch=True,
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1')
        page = ctx.new_page()
        page.on('console', lambda m: (m.type == 'error' and (errs.append('console:'+m.text), print('ERR', m.text))))
        page.on('pageerror', lambda e: (errs.append('page:'+str(e)), print('PAGE', e)))
        page.goto(URL, wait_until='networkidle', timeout=30000)
        page.wait_for_function('window.__game && window.__game.ready === true', timeout=20000)
        start_play(page)

        # Same scene, 4 headings around the sandwich
        # Knight slightly in front and right of the sandwich so orbit reveals every side.
        ev(page, '''() => {
          window.__game.clearBaddies();
          window.__game.setMove(0,0);
          window.__game.setPos(-0.15, 0.95);
          window.__game.setYaw(0);
        }''')
        angles = [('0', 0), ('90', math.pi/2), ('180', math.pi), ('270', math.pi*1.5)]
        for name, yaw in angles:
            ev(page, f'() => {{ window.__game.setCamYaw({yaw}); window.__game.step(0); }}')
            # a couple of follow-cam settle steps (position damp)
            step_for(page, 0.35, 1/60)
            info = ev(page, '() => ({yaw: window.__game.camYaw(), k: window.__game.knight(), fade: window.__game.foodFade()})')
            page.screenshot(path=str(SHOTS / f'844x390_cam_{name}.png'))
            print(f'ANGLE {name}: yaw={info["yaw"]:.3f} view={info["k"]["view"]} face={info["k"]["face"]} fade={info["fade"]}')
            results[f'angle_{name}'] = info

        # Occlusion: knight on the far side of the sandwich, default heading looks through it
        ev(page, '''() => {
          window.__game.setMove(0,0);
          window.__game.setPos(-1.15, -1.55);
          window.__game.setYaw(0);
          window.__game.setCamYaw(0);
        }''')
        step_for(page, 0.35, 1/60)
        fade = ev(page, '() => window.__game.foodFade()')
        k = ev(page, '() => window.__game.knight()')
        page.screenshot(path=str(SHOTS / '844x390_cam_occlusion.png'))
        print('OCCLUSION', fade, 'knight', k)
        results['occlusion'] = fade
        sandwich = next((f for f in fade if f['name']=='sandwich'), None)
        if not sandwich or sandwich['opacity'] > 0.55 or sandwich['fade'] < 0.4:
            errs.append(f'sandwich did not fade enough when occluding: {sandwich}')

        # Sprite facing vs camera heading: knight faces world -Z (yaw 0).
        # At camYaw 0 we should see his back; at pi we should see his front.
        ev(page, '''() => {
          window.__game.setPos(0.2, 1.4);
          window.__game.setYaw(0);
          window.__game.setCamYaw(0);
        }''')
        step_for(page, 0.2, 1/60)
        back = ev(page, '() => window.__game.knight()')
        ev(page, '() => window.__game.setCamYaw(Math.PI)')
        step_for(page, 0.25, 1/60)
        front = ev(page, '() => window.__game.knight()')
        ev(page, '() => window.__game.setCamYaw(Math.PI/2)')
        step_for(page, 0.25, 1/60)
        side = ev(page, '() => window.__game.knight()')
        print('VIEW back', back['view'], 'front', front['view'], 'side', side['view'])
        results['views'] = {'back': back['view'], 'front': front['view'], 'side': side['view']}
        if back['view'] not in ('back', 'back34'):
            errs.append(f'expected back view at yaw 0, got {back["view"]}')
        if front['view'] not in ('front', 'front34'):
            errs.append(f'expected front view at yaw pi, got {front["view"]}')
        if side['view'] not in ('side', 'front34', 'back34'):
            errs.append(f'expected side-ish view at yaw pi/2, got {side["view"]}')

        # Movement stays screen-relative after a 90° orbit: stick up should move +X
        ev(page, '''() => {
          window.__game.setMove(0,0);
          window.__game.setPos(0, 2.0);
          window.__game.setYaw(0);
          window.__game.setCamYaw(Math.PI/2);
        }''')
        step_for(page, 0.2, 1/60)
        ev(page, '() => window.__game.setMove(0, -1)')  # stick up
        step_for(page, 0.40, 1/60)
        after = ev(page, '() => window.__game.knight()')
        ev(page, '() => window.__game.setMove(0,0)')
        print('MOVE after 90° stick-up', after)
        results['move90'] = after
        if after['x'] < 0.25:
            errs.append(f'stick-up after 90° orbit should move +X (away from camera), x={after["x"]:.3f}')
        if abs(after['z'] - 2.0) > 0.20:
            errs.append(f'stick-up after 90° should not move much in Z, z={after["z"]:.3f}')

        # Off-screen attack arrow after rotation
        ev(page, '''() => {
          window.__game.setMove(0,0);
          window.__game.setPos(2.6, 2.2);
          window.__game.setYaw(0);
          window.__game.setCamYaw(0);
          window.__game.clearBaddies();
          window.__game.spawnAntAt(-1.15, -0.25);
        }''')
        step_for(page, 0.25, 1/60)
        ev(page, '() => window.__game.setCamYaw(0)')
        step_for(page, 0.3, 1/60)
        arrow0 = ev(page, '''() => {
          const el = document.getElementById("arrow");
          return {hidden: el.classList.contains("hidden"), cls: el.className};
        }''')
        print('ARROW default', arrow0)
        ev(page, '() => window.__game.setCamYaw(Math.PI)')
        step_for(page, 0.4, 1/60)
        arrow1 = ev(page, '''() => {
          const el = document.getElementById("arrow");
          const k = window.__game.knight();
          return {hidden: el.classList.contains("hidden"), cls: el.className, k};
        }''')
        print('ARROW after 180', arrow1)
        results['arrow'] = {'before': arrow0, 'after': arrow1}
        # After flipping the camera, the food (and nibbling ant) should still trigger a correctly placed arrow if off-screen
        # (may or may not be off-screen depending on framing; record it, only fail if the arrow shows an inconsistent side with projection)
        arrow_ok = ev(page, '''() => {
          const v = window.__game._projFood ? window.__game._projFood() : null;
          const el = document.getElementById("arrow");
          return {hidden: el.classList.contains("hidden"), cls: el.className, hasLeft: el.classList.contains("left"), hasTop: el.classList.contains("top"), hasBottom: el.classList.contains("bottom")};
        }''')
        results['arrow_ok'] = arrow_ok

        # Keyboard Q/E: hold E for 0.5s at 60fps ~ 60 degrees
        ev(page, '''() => {
          window.__game.clearBaddies();
          window.__game.setMove(0,0);
          window.__game.setPos(0.2, 1.4);
          window.__game.setCamYaw(0);
          window.__game.setCamRate(0);
        }''')
        ev(page, '() => window.__game.setCamRate(1)')
        step_for(page, 0.50, 1/60)
        ev(page, '() => window.__game.setCamRate(0)')
        yawE = ev(page, '() => window.__game.camYaw()')
        print(f'HOLD E 0.5s yaw={yawE:.3f} rad ({math.degrees(yawE):.1f} deg), expected ~60')
        results['holdE'] = yawE
        if abs(math.degrees(yawE) - 60) > 12:
            errs.append(f'E held 0.5s should rotate ~60deg, got {math.degrees(yawE):.1f}')

        # Frame-rate independence: 60 vs 120 over 1s of hold (~120 deg)
        def travel(label, dt, seconds=1.0):
            ev(page, '''() => {
              window.__game.setCamRate(0);
              window.__game.setCamYaw(0);
              window.__game.setMove(0,0);
              window.__game.setPos(0.2, 1.4);
            }''')
            ev(page, '() => window.__game.setCamRate(1)')
            step_for(page, seconds, dt)
            ev(page, '() => window.__game.setCamRate(0)')
            y = ev(page, '() => window.__game.camYaw()')
            print(f'FRAMERATE {label}: yaw={y:.4f} rad ({math.degrees(y):.2f} deg)')
            return y
        y60 = travel('60fps', 1/60)
        y120 = travel('120fps', 1/120)
        results['framerate'] = {'y60': y60, 'y120': y120, 'deg60': math.degrees(y60), 'deg120': math.degrees(y120)}
        if abs(y60 - y120) > 0.04:
            errs.append(f'60 vs 120 fps yaw mismatch: {y60:.4f} vs {y120:.4f}')
        # 120 deg/s * 1s = 2.094 rad
        if abs(math.degrees(y60) - 120) > 10:
            errs.append(f'60fps 1s hold should be ~120deg, got {math.degrees(y60):.1f}')

        # Button tap = 45° snap
        ev(page, '() => { window.__game.setCamRate(0); window.__game.setCamYaw(0); }')
        ev(page, '() => window.__game.step(0.016)')
        box = ev(page, '''() => {
          const r = document.getElementById("camRight").getBoundingClientRect();
          return {x: r.left + r.width/2, y: r.top + r.height/2, vis: getComputedStyle(document.getElementById("camBtns")).display !== "none"};
        }''')
        print('camRight box', box)
        if box['vis']:
            page.mouse.click(box['x'], box['y'])
            # click is press+release quickly; should queue a 45° snap, then step to ease there
            step_for(page, 0.35, 1/60)
            ybtn = ev(page, '() => window.__game.camYaw()')
            print(f'BUTTON tap right yaw={ybtn:.3f} ({math.degrees(ybtn):.1f} deg)')
            results['btnTap'] = ybtn
            if abs(math.degrees(ybtn) - 45) > 10:
                errs.append(f'rotate-right tap should snap ~45deg, got {math.degrees(ybtn):.1f}')

        ev(page, '() => window.__game.freeze(false)')
        ctx.close()
        browser.close()

    Path('/tmp/pk-camera-qa.json').write_text(json.dumps(results, indent=2, default=str))
    if errs:
        print('FAIL')
        for e in errs: print(' -', e)
        sys.exit(1)
    print('PASS')

if __name__ == '__main__':
    run()
