#!/usr/bin/env python3
"""Slash hit-rate QA: every 15° around the knight, 8 facings, 4 camera headings."""
import json, math, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

SHOTS = Path('/workspace/picnic-knight/shots')
SHOTS.mkdir(exist_ok=True)
URL = 'http://127.0.0.1:8767/index.html'
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else '/tmp/pk-slash-qa.json')
RANGE = 0.70  # inside current and new reach
ARC_HALF = math.radians(150) / 2  # expected generous arc after fix; also used to classify "behind"
FPS_LIST = [1/60, 1/120]

def ev(page, js):
    return page.evaluate(js)

def step_for(page, seconds, dt):
    n = int(round(seconds / dt))
    ev(page, f'() => {{ for (let i = 0; i < {n}; i++) window.__game.step({dt}); }}')

def setup(page):
    ev(page, '() => { document.body.classList.add("touch"); }')
    ev(page, '() => { if (window.__game.state !== "play" && window.__game.state !== "steal") window.__game.start(); if (window.__game.state === "steal") window.__game.skipSteal(); }')
    page.wait_for_function('window.__game.state === "play"', timeout=8000)
    ev(page, '''() => {
      window.__game.freeze(true);
      window.__game.clearBaddies();
      window.__game.setMove(0,0);
      if (window.__game.ensurePlay) window.__game.ensurePlay();
      window.__game.setTimeLeft(9999);
    }''')

def place(page, kx, kz, kyaw, cyaw, ax, az):
    ev(page, f'''() => {{
      window.__game.clearBaddies();
      window.__game.setMove(0,0);
      window.__game.setPos({kx}, {kz});
      window.__game.setYaw({kyaw});
      window.__game.setCamYaw({cyaw});
      if (window.__game.ensurePlay) window.__game.ensurePlay();
      window.__game.setTimeLeft(9999);
      window.__game.spawnAntAt({ax}, {az});
      window.__game.freezeAnts();
    }}''')

def fire_slash(page, dt):
    ev(page, '() => window.__game.slash()')
    step_for(page, 0.40, dt)
    return ev(page, '''() => {
      const ants = window.__game.ants();
      const k = window.__game.knight();
      const dead = ants.some(a => !a.alive || a.state === "launch" || a.state === "down" || a.state === "poof");
      return {dead, score: window.__game.score, ants, k};
    }''')

def run():
    errs = []
    results = {'facing': {}, 'plain': {}, 'spin': {}, 'console': []}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--use-gl=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'])
        ctx = browser.new_context(viewport={'width':844,'height':390}, device_scale_factor=1, has_touch=True)
        page = ctx.new_page()
        page.on('console', lambda m: (m.type=='error' and (errs.append('console:'+m.text), results['console'].append(m.text), print('ERR', m.text))))
        page.on('pageerror', lambda e: (errs.append('page:'+str(e)), print('PAGE', e)))
        page.goto(URL, wait_until='networkidle', timeout=30000)
        page.wait_for_function('window.__game && window.__game.ready === true', timeout=20000)
        page.click('#btnPlay', force=True)
        setup(page)

        kx, kz = 0.0, 3.05
        cam_heads = [0, math.pi/2, math.pi, math.pi*1.5]
        facings = [i * math.pi/4 for i in range(8)]
        ant_angs = [i * 15 for i in range(24)]  # degrees

        # --- A) slash while the knight faces the ant ---
        for dt, label in ((1/60, '60fps'), (1/120, '120fps')):
            hits = misses = 0
            miss_ex = []
            for cyaw in cam_heads:
                for deg in ant_angs:
                    rad = math.radians(deg)
                    # ant placed in world: faceDir convention, angle 0 is -Z
                    ax = kx + math.sin(rad) * RANGE
                    az = kz + (-math.cos(rad)) * RANGE
                    kyaw = math.atan2(ax - kx, -(az - kz))
                    place(page, kx, kz, kyaw, cyaw, ax, az)
                    ev(page, '() => window.__game.step(0)')
                    info = fire_slash(page, dt)
                    if info['dead']:
                        hits += 1
                    else:
                        misses += 1
                        if len(miss_ex) < 8:
                            miss_ex.append({'deg': deg, 'cam': round(math.degrees(cyaw)), 'yaw': kyaw, 'info': info})
            total = hits + misses
            rate = hits / total if total else 0
            results['facing'][label] = {'hits': hits, 'misses': misses, 'total': total, 'rate': rate, 'examples': miss_ex}
            print(f'FACING-THE-ANT {label}: {hits}/{total} = {rate*100:.1f}%  misses={misses} ex={miss_ex[:3]}')
            if rate < 1.0:
                errs.append(f'facing-the-ant {label} hit rate {rate*100:.1f}% (goal 100%)')

        # --- B) plain slash, knight stays at each of 8 facings, no pre-turn (auto-aim may still snap) ---
        dt = 1/60
        in_hits = in_miss = out_hits = out_miss = 0
        out_hit_ex = []
        in_miss_ex = []
        for cyaw in cam_heads:
            for kyaw in facings:
                for deg in ant_angs:
                    rad = math.radians(deg)
                    ax = kx + math.sin(rad) * RANGE
                    az = kz + (-math.cos(rad)) * RANGE
                    # world angle of ant relative to knight facing
                    ant_yaw = math.atan2(ax - kx, -(az - kz))
                    rel = ant_yaw - kyaw
                    while rel > math.pi: rel -= 2*math.pi
                    while rel < -math.pi: rel += 2*math.pi
                    in_arc = abs(rel) <= ARC_HALF + 1e-6
                    place(page, kx, kz, kyaw, cyaw, ax, az)
                    ev(page, '() => window.__game.step(0)')
                    info = fire_slash(page, dt)
                    if in_arc:
                        if info['dead']:
                            in_hits += 1
                        else:
                            in_miss += 1
                            if len(in_miss_ex) < 8:
                                in_miss_ex.append({'deg': deg, 'cam': round(math.degrees(cyaw)), 'kyaw': round(math.degrees(kyaw)), 'rel': round(math.degrees(rel),1)})
                    else:
                        if info['dead']:
                            out_hits += 1
                            if len(out_hit_ex) < 8:
                                out_hit_ex.append({'deg': deg, 'cam': round(math.degrees(cyaw)), 'kyaw': round(math.degrees(kyaw)), 'rel': round(math.degrees(rel),1)})
                        else:
                            out_miss += 1
        in_total = in_hits + in_miss
        out_total = out_hits + out_miss
        results['plain'] = {
            'in_arc': {'hits': in_hits, 'misses': in_miss, 'total': in_total, 'rate': in_hits/in_total if in_total else 0},
            'out_arc': {'hits': out_hits, 'misses': out_miss, 'total': out_total, 'rate': out_hits/out_total if out_total else 0},
            'in_miss_ex': in_miss_ex, 'out_hit_ex': out_hit_ex
        }
        print(f'PLAIN in-arc: {in_hits}/{in_total} = {in_hits/in_total*100:.1f}%  misses={in_miss} ex={in_miss_ex[:4]}')
        print(f'PLAIN out-arc (should be 0 hits): {out_hits}/{out_total} = {out_hits/out_total*100:.1f}%  ex={out_hit_ex[:4]}')
        if in_hits / in_total < 1.0:
            errs.append(f'plain slash in-arc {in_hits/in_total*100:.1f}% (goal 100%)')
        if out_hits != 0:
            errs.append(f'plain slash hit {out_hits} ants behind/outside the 150° arc')

        # --- C) spin hits 360° (one ant behind at each camera) ---
        spin_hits = spin_miss = 0
        for cyaw in cam_heads:
            ax = kx + 0
            az = kz + 0.70  # behind a yaw-0 knight (toward +Z / camera at heading 0)
            place(page, kx, kz, 0, cyaw, ax, az)
            ev(page, '() => { window.__game.readySpin && window.__game.readySpin(); window.__game.step(0); }')
            ev(page, '() => window.__game.spin()')
            step_for(page, 0.50, 1/60)
            info = ev(page, '() => ({dead: window.__game.ants().some(a => !a.alive || a.state!=="walk"&&a.state!=="eat"), ants: window.__game.ants()})')
            if info['dead']:
                spin_hits += 1
            else:
                spin_miss += 1
                print('SPIN MISS', cyaw, info)
        results['spin'] = {'hits': spin_hits, 'misses': spin_miss}
        print(f'SPIN behind at 4 cams: {spin_hits}/4')
        if spin_miss:
            errs.append(f'spin missed {spin_miss} behind-the-knight ants')


        # --- screenshots: kills from different camera headings ---
        # Use a follow-cam view around the picnic, ant in front of the knight.
        shot_cams = [('90', math.pi/2), ('180', math.pi), ('270', math.pi*1.5), ('0', 0.0)]
        for name, cyaw in shot_cams:
            # knight a bit in front of the sandwich; ant further along his facing
            kx2, kz2 = -0.15, 0.95
            kyaw = 0.0
            ax = kx2 + math.sin(kyaw) * 0.62
            az = kz2 + (-math.cos(kyaw)) * 0.62
            place(page, kx2, kz2, kyaw, cyaw, ax, az)
            ev(page, '() => window.__game.step(0.05)')
            ev(page, '() => window.__game.slash()')
            # step into the launch window (~windup 0.06-0.15 plus a beat of hang time)
            step_for(page, 0.14, 1/60)
            info = ev(page, '() => ({ants: window.__game.ants(), k: window.__game.knight(), yaw: window.__game.camYaw(), score: window.__game.score})')
            path = str(SHOTS / f'844x390_slash_{name}.png')
            page.screenshot(path=path)
            print(f'SHOT slash_{name}', path, 'ants', info['ants'], 'view', info['k'].get('view'), 'cam', info['yaw'])
            results.setdefault('shots', {})[name] = info

        ev(page, '() => window.__game.freeze(false)')
        ctx.close(); browser.close()

    OUT.write_text(json.dumps(results, indent=2, default=str))
    print('wrote', OUT)
    # The script always prints rates. Exit 0 for the BEFORE run even if rates are low;
    # pass --strict to fail on goals.
    if '--strict' in sys.argv and (errs or results['console']):
        print('FAIL')
        for e in errs: print(' -', e)
        sys.exit(1)
    if results['console']:
        print('CONSOLE ERRORS', results['console'])
        sys.exit(1)
    print('DONE')

if __name__ == '__main__':
    run()
