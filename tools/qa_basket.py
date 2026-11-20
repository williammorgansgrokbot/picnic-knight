#!/usr/bin/env python3
"""Picnic Knight — larger basket QA: clip, walk-around, comparison shots."""
import math, time, json
from pathlib import Path
from playwright.sync_api import sync_playwright

SHOTS = Path('/workspace/picnic-knight/shots')
SHOTS.mkdir(exist_ok=True)
URL = 'http://127.0.0.1:8767/index.html'
SIZES = [(844, 390), (932, 430), (667, 375)]
BASKET = (1.75, -1.50)
BASKET_R = 0.80
KNIGHT_RAD = 0.16
MIN_DIST = BASKET_R + KNIGHT_RAD  # 0.96

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
      window.__game.setTimeLeft(9999);
      const el = document.getElementById("banner");
      if (el) el.classList.remove("show");
    }''')
    page.wait_for_function('window.__game.state === "play"', timeout=8000)

def step_to(page, seconds, dt=1/60):
    remain = seconds
    while remain > 1e-6:
        chunk = min(dt, remain, 1/30)
        ev(page, f'() => window.__game.step({chunk})')
        remain -= chunk

def run():
    errs = []
    clips_all = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=['--use-gl=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--autoplay-policy=no-user-gesture-required'])

        # --- 844 hero shots + walk-around ---
        ctx = b.new_context(viewport={'width':844,'height':390}, device_scale_factor=1, has_touch=True)
        page = ctx.new_page()
        pe = []
        page.on('console', lambda m: (m.type=='error' and (pe.append('console:'+m.text), print('ERR', m.text))))
        page.on('pageerror', lambda e: (pe.append('page:'+str(e)), print('PAGE', e)))
        boot(page)
        time.sleep(0.2)
        page.screenshot(path=str(SHOTS/'844x390_basket_title.png'))

        start_play(page)
        # Default follow camera, knight at the usual start so pie (left) and basket (back-right) share the frame
        ev(page, '''() => {
          window.__game.setMove(0,0);
          window.__game.setPos(0.45, 1.90);
          window.__game.setYaw(0);
          window.__game.setCamYaw(0);
          window.__game.camUnlock();
        }''')
        ev(page, '() => window.__game.step(0)')
        time.sleep(0.12)
        page.screenshot(path=str(SHOTS/'844x390_basket_pie_default.png'))
        print('default shot saved')

        # Rotated angle: 90° so we look across the blanket, pie and basket both readable
        ev(page, '''() => {
          window.__game.setPos(0.15, 0.35);
          window.__game.setYaw(0);
          window.__game.setCamYaw(Math.PI * 0.5);
        }''')
        ev(page, '() => window.__game.step(0)')
        time.sleep(0.12)
        page.screenshot(path=str(SHOTS/'844x390_basket_pie_rotated.png'))
        print('rotated shot saved')

        # also a 180° view from the far side, useful if 90° hides one of them
        ev(page, '''() => {
          window.__game.setPos(0.2, -0.15);
          window.__game.setYaw(Math.PI);
          window.__game.setCamYaw(Math.PI);
        }''')
        ev(page, '() => window.__game.step(0)')
        time.sleep(0.12)
        page.screenshot(path=str(SHOTS/'844x390_basket_pie_rotated_180.png'))

        clips = collect_clip(page)
        if clips:
            print('CLIP 844 play', clips)
            clips_all += [{'where':'844-play', **c} for c in clips]

        # Walk around the basket: start outside, walk inward+tangent in 16 headings
        ev(page, '() => { window.__game.setCamYaw(0); window.__game.camUnlock(); }')
        bx, bz = BASKET
        # Circle orbit: place at 1.35 from center, walk toward a slightly inward tangent for 0.45s
        too_close = []
        blocked = []
        circled = []
        for i in range(16):
            ang = i * math.pi / 8
            start_r = 1.40
            sx = bx + math.cos(ang) * start_r
            sz = bz + math.sin(ang) * start_r
            ev(page, f'''() => {{
              window.__game.setMove(0,0);
              window.__game.setPos({sx}, {sz});
              window.__game.setCamYaw(0);
            }}''')
            # Walk toward the basket (should be stopped by collision)
            inward_x = bx - sx
            inward_z = bz - sz
            inv = math.hypot(inward_x, inward_z) or 1
            ev(page, f'() => window.__game.setMove({inward_x/inv}, {inward_z/inv})')
            # setMove is camera-relative (cam yaw 0: +x is right, +z is toward camera / world +Z? 
            # camMove: worldX = ix*cos - iz*sin; worldZ = ix*sin + iz*cos. yaw 0: worldX=ix, worldZ=iz.
            # Keyboard: ArrowDown / S sets kbZ = +1, which is world +Z when camYaw=0.
            # We want world direction (inward_x, inward_z), so setMove(inward_x, inward_z) at camYaw 0. Good.
            ev(page, '() => window.__game.setYaw(0)')  # don't care
            step_to(page, 0.70, 1/60)
            ev(page, '() => window.__game.setMove(0,0)')
            k = ev(page, '() => window.__game.knight()')
            d = math.hypot(k['x']-bx, k['z']-bz)
            moved = math.hypot(k['x']-sx, k['z']-sz)
            print(f'  inward {i:2d} ang={ang*180/math.pi:6.1f} start_d={start_r:.2f} end_d={d:.3f} moved={moved:.3f} pos=({k["x"]:.2f},{k["z"]:.2f})')
            if d < MIN_DIST - 0.04:
                too_close.append((i, d, k))
            if moved < 0.08:
                blocked.append((i, d, k))

        # Full clockwise lap just outside the collider
        ev(page, f'''() => {{
          window.__game.setMove(0,0);
          window.__game.setPos({bx + 1.25}, {bz});
          window.__game.setCamYaw(0);
        }}''')
        # Walk a 12-waypoint ring
        ring_r = 1.25
        positions = []
        for i in range(13):
            ang = -i * math.pi / 6  # clockwise
            tx = bx + math.cos(ang) * ring_r
            tz = bz + math.sin(ang) * ring_r
            # move toward waypoint for up to 0.8s
            for _ in range(24):
                k = ev(page, '() => window.__game.knight()')
                dx, dz = tx - k['x'], tz - k['z']
                dist = math.hypot(dx, dz)
                if dist < 0.12:
                    break
                ev(page, f'() => window.__game.setMove({dx}, {dz})')
                step_to(page, 1/30, 1/30)
            ev(page, '() => window.__game.setMove(0,0)')
            k = ev(page, '() => window.__game.knight()')
            d = math.hypot(k['x']-bx, k['z']-bz)
            positions.append((k['x'], k['z'], d))
        ev(page, '() => window.__game.setMove(0,0)')
        # Did we visit all four quadrants around the basket?
        xs = [p[0]-bx for p in positions]
        zs = [p[1]-bz for p in positions]
        quads = {
            'east': any(x > 0.5 for x in xs),
            'west': any(x < -0.5 for x in xs),
            'north': any(z > 0.5 for z in zs),
            'south': any(z < -0.5 for z in zs),
        }
        min_ring = min(p[2] for p in positions)
        max_ring = max(p[2] for p in positions)
        print('ring quads', quads, 'd range', round(min_ring,3), round(max_ring,3), 'pts', [(round(p[0],2),round(p[1],2),round(p[2],2)) for p in positions])
        if not all(quads.values()):
            errs.append('walk ring did not reach all four sides of the basket: ' + json.dumps(quads))
        if min_ring < MIN_DIST - 0.06:
            errs.append(f'walk ring penetrated basket collider (min d={min_ring:.3f}, need >= {MIN_DIST:.2f})')
        if too_close:
            errs.append(f'inward walks penetrated collider: {too_close}')
        # inward walks should have moved closer and then been stopped near MIN_DIST
        if blocked:
            errs.append(f'inward walks barely moved, maybe stuck: {blocked}')

        # Shot of knight walking beside the larger basket (default cam)
        ev(page, f'''() => {{
          window.__game.setMove(0,0);
          window.__game.setPos({bx - 1.15}, {bz + 0.15});
          window.__game.setYaw({-math.pi/2});
          window.__game.setCamYaw(0);
        }}''')
        ev(page, '() => window.__game.step(0)')
        time.sleep(0.08)
        page.screenshot(path=str(SHOTS/'844x390_basket_walk.png'))

        errs.extend(pe)
        ctx.close()

        # --- clip + console at all 3 sizes ---
        for w, h in SIZES:
            tag = f'{w}x{h}'
            c = b.new_context(viewport={'width':w,'height':h}, device_scale_factor=1, has_touch=True)
            pg = c.new_page()
            pe = []
            pg.on('console', lambda m: (m.type=='error' and pe.append('console:'+m.text)))
            pg.on('pageerror', lambda e: pe.append('page:'+str(e)))
            boot(pg)
            time.sleep(0.1)
            pg.screenshot(path=str(SHOTS / f'{tag}_basket_title.png'))
            cl = collect_clip(pg)
            if cl:
                print('CLIP', tag, 'title', cl)
                clips_all += [{'where':tag+'-title', **x} for x in cl]
            start_play(pg)
            ev(pg, '''() => {
              window.__game.setMove(0,0);
              window.__game.setPos(0.45, 1.90);
              window.__game.setYaw(0);
              window.__game.setCamYaw(0);
              window.__game.camUnlock();
            }''')
            ev(pg, '() => window.__game.step(0)')
            time.sleep(0.08)
            pg.screenshot(path=str(SHOTS / f'{tag}_basket_play.png'))
            cl = collect_clip(pg)
            if cl:
                print('CLIP', tag, 'play', cl)
                clips_all += [{'where':tag+'-play', **x} for x in cl]
            if pe:
                print('ERR', tag, pe)
                errs.extend([tag+':'+e for e in pe])
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
