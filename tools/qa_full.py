#!/usr/bin/env python3
"""Full-game QA: clips, console, wasp/boss/beetle hits, official shots + title GIF."""
import math, time, json
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

SHOTS = Path('/workspace/picnic-knight/shots')
SHOTS.mkdir(exist_ok=True)
URL = 'http://127.0.0.1:8767/index.html'
SIZES = [(844, 390), (932, 430), (667, 375)]

def ev(page, js):
    return page.evaluate(js)

def collect_clip(page):
    return page.evaluate('''() => {
      const ids = ['pad','slashBtn','spinBtn','topLeft','meterWrap','topRight','timerPanel','timerNum',
        'btnPlay','logo','btnPause','btnMute','waveNum','scoreNum','arrow','banner','skipHint','cNext','cTitle',
        'bestScore','bossWrap','perks'];
      const w = window.innerWidth, h = window.innerHeight;
      const out = [];
      for (const id of ids) {
        const el = document.getElementById(id);
        if (!el) continue;
        const st = getComputedStyle(el);
        if (st.display === 'none' || st.visibility === 'hidden' || Number(st.opacity) === 0) continue;
        if (el.classList.contains('hidden')) continue;
        const screen = el.closest('.screen');
        if (screen && !screen.classList.contains('show')) continue;
        const r = el.getBoundingClientRect();
        if (!r.width && !r.height) continue;
        const clip = r.left < -2 || r.top < -2 || r.right > w+2 || r.bottom > h+2;
        if (clip) out.push({id, left:r.left, top:r.top, right:r.right, bottom:r.bottom, w, h});
      }
      return out;
    }''')

def boot(page):
    page.goto(URL, wait_until='networkidle', timeout=45000)
    page.wait_for_function('window.__game && window.__game.ready === true', timeout=25000)

def to_play(page):
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

def step_for(page, seconds, dt=1/60):
    n = int(round(seconds / dt))
    ev(page, f'() => {{ for (let i = 0; i < {n}; i++) window.__game.step({dt}); }}')

def fire_spin(page, dt=1/60):
    ev(page, '() => { if (window.__game.readySpin) window.__game.readySpin(); window.__game.spin(); }')
    step_for(page, 0.50, dt)

def fire_slash(page, dt=1/60):
    ev(page, '() => { if (window.__game.readySpin) window.__game.readySpin(); window.__game.slash(); }')
    step_for(page, 0.40, dt)

def run():
    errs = []
    clips_all = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=['--use-gl=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--autoplay-policy=no-user-gesture-required'])
        ctx = b.new_context(viewport={'width':844,'height':390}, device_scale_factor=1, has_touch=True)
        page = ctx.new_page()
        pe = []
        def on_con(m):
            t = m.text or ''
            if m.type=='error' and not any(k in t for k in ('ReadPixels','GPU stall','swiftshader')):
                pe.append('console:'+t); print('ERR', t)
        page.on('console', on_con)
        page.on('pageerror', lambda e: (pe.append('page:'+str(e)), print('PAGE', e)))
        boot(page)

        # ---- title frames + GIF ----
        gif_frames = []
        # pick times where both dogs are on screen: period 8.2, emma lag 0.48*8.2≈3.94
        times = [0.9, 1.3, 1.7, 2.1, 2.5, 2.9, 3.3, 4.8, 5.2, 5.6]
        for i, tt in enumerate(times):
            ev(page, f'() => window.__game.setTitleT({tt})')
            ev(page, '() => window.__game.step(0)')
            time.sleep(0.05)
            path = SHOTS / f'844x390_full_title_t{i}.png'
            page.screenshot(path=str(path))
            gif_frames.append(Image.open(path).convert('P', palette=Image.ADAPTIVE, colors=64))
        # official title: choose a mid frame later; save last as working, we'll copy the best
        page.screenshot(path=str(SHOTS/'844x390_full_title.png'))
        print('title frames', len(times))

        # mid-run dog close-ups use the title frames; also dedicated ones
        ev(page, '() => window.__game.setTitleT(1.7)')
        ev(page, '() => window.__game.step(0)')
        time.sleep(0.05)
        page.screenshot(path=str(SHOTS/'844x390_full_dogs_run_a.png'))
        ev(page, '() => window.__game.setTitleT(2.5)')
        ev(page, '() => window.__game.step(0)')
        time.sleep(0.05)
        page.screenshot(path=str(SHOTS/'844x390_full_dogs_run_b.png'))

        # ---- play shots ----
        to_play(page)

        # lineup: ant, beetle, wasp, boss in a row in front of default cam
        ev(page, '''() => {
          window.__game.clearBaddies();
          window.__game.setMove(0,0);
          window.__game.setPos(0.2, 2.15);
          window.__game.setYaw(0);
          window.__game.setCamYaw(0);
          window.__game.camUnlock && window.__game.camUnlock();
          window.__game.spawnBugAt("ant", -1.35, 0.55);
          window.__game.spawnBugAt("beetle", -0.45, 0.55);
          window.__game.spawnBugAt("wasp", 0.45, 0.55);
          window.__game.spawnBugAt("boss", 1.55, 0.35);
          window.__game.freezeAnts();
        }''')
        ev(page, '() => window.__game.step(0)')
        time.sleep(0.08)
        print('lineup', ev(page, '() => window.__game.ants()'))
        page.screenshot(path=str(SHOTS/'844x390_full_bug_lineup.png'))

        ev(page, '''() => {
          window.__game.clearBaddies();
          window.__game.setPos(0.15, 1.9);
          window.__game.setYaw(0);
          window.__game.setCamYaw(0);
          window.__game.startBoss();
          const i = window.__game.ants().length - 1;
          window.__game.setAntPos(i, -0.2, 0.25, 0);
          window.__game.spawnBugAt("ant", -0.95, 0.45);
          window.__game.spawnBugAt("ant", 0.85, 0.15);
          window.__game.freezeAnts();
          const el = document.getElementById("banner");
          if (el) { el.textContent = "ANT CAPTAIN!"; el.classList.add("show"); }
        }''')
        ev(page, '() => window.__game.step(0)')
        print('boss hook', ev(page, '() => window.__game.boss'))
        page.screenshot(path=str(SHOTS/'844x390_full_boss_fight.png'))
        ev(page, '() => { const el=document.getElementById("banner"); if(el) el.classList.remove("show"); }')

        # eaten foods
        ev(page, '''() => {
          window.__game.clearBaddies();
          window.__game.setPos(0.35, 2.0);
          window.__game.setYaw(0); window.__game.setCamYaw(0);
          (window.__game.foods() || []).forEach(f => window.__game.setFoodHp(f.id, 0));
        }''')
        ev(page, '() => window.__game.step(0)')
        time.sleep(0.05)
        print('eaten', ev(page, '() => window.__game.foods()'))
        # if lose triggered, go back
        ev(page, '''() => {
          if (window.__game.state !== "play" && window.__game.ensurePlay) {
            window.__game.ensurePlay();
            window.__game.setTimeLeft(180);
            (window.__game.foods() || []).forEach(f => window.__game.setFoodHp(f.id, 0));
          }
        }''')
        ev(page, '() => window.__game.step(0)')
        page.screenshot(path=str(SHOTS/'844x390_full_foods_eaten.png'))

        # busy gameplay
        ev(page, '''() => {
          if (window.__game.ensurePlay) window.__game.ensurePlay();
          window.__game.resetFoods && window.__game.resetFoods();
          window.__game.setTimeLeft(180);
          window.__game.clearBaddies();
          window.__game.setPos(0.25, 1.85);
          window.__game.setYaw(0); window.__game.setCamYaw(0);
          window.__game.spawnBugAt("ant", -1.35, -0.15);
          window.__game.spawnBugAt("ant", -0.7, 0.35);
          window.__game.spawnBugAt("beetle", 0.55, 0.15);
          window.__game.spawnBugAt("wasp", -0.2, -0.55);
          window.__game.spawnBugAt("wasp", 1.1, 0.7);
          window.__game.freezeAnts();
          const el = document.getElementById("banner");
          if (el) el.classList.remove("show");
        }''')
        ev(page, '() => window.__game.step(0)')
        time.sleep(0.08)
        page.screenshot(path=str(SHOTS/'844x390_full_gameplay.png'))

        # ---- hit tests at 60 and 120 ----
        hit_errs = []
        for dt, lab in ((1/60, '60fps'), (1/120, '120fps')):
            # wasp slash
            ev(page, '''() => {
              if (window.__game.ensurePlay) window.__game.ensurePlay();
              window.__game.setTimeLeft(9999);
              window.__game.clearBaddies();
              window.__game.setMove(0,0);
              window.__game.setPos(0, 3.05);
              window.__game.setYaw(0);
              window.__game.setCamYaw(0);
              window.__game.spawnBugAt("wasp", 0, 3.05-0.70);
              window.__game.freezeAnts();
            }''')
            ev(page, '() => window.__game.step(0)')
            fire_slash(page, dt)
            r = ev(page, '''() => {
              const a = window.__game.ants()[0];
              return {dead: !a || !a.alive || a.state==="launch" || a.state==="down" || a.state==="poof", a};
            }''')
            print(lab, 'wasp slash', r)
            if not r.get('dead'):
                hit_errs.append(lab+' wasp slash missed')

            # wasp spin
            ev(page, '''() => {
              window.__game.clearBaddies();
              window.__game.setPos(0, 3.05);
              window.__game.setYaw(0); window.__game.setCamYaw(0);
              window.__game.spawnBugAt("wasp", 0.4, 3.05-0.6);
              window.__game.freezeAnts();
            }''')
            ev(page, '() => window.__game.step(0)')
            fire_spin(page, dt)
            r = ev(page, '''() => {
              const a = window.__game.ants()[0];
              return {dead: !a || !a.alive || ["launch","down","poof"].includes(a.state), a};
            }''')
            print(lab, 'wasp spin', r)
            if not r.get('dead'):
                hit_errs.append(lab+' wasp spin missed')

            # beetle: one slash lives, two slashes or spin dies
            ev(page, '''() => {
              window.__game.clearBaddies();
              window.__game.setPos(0, 3.05);
              window.__game.setYaw(0); window.__game.setCamYaw(0);
              window.__game.spawnBugAt("beetle", 0, 3.05-0.70);
              window.__game.freezeAnts();
            }''')
            ev(page, '() => window.__game.step(0)')
            fire_slash(page, dt)
            r1 = ev(page, '''() => { const a=window.__game.ants()[0]; return {alive: !!(a&&a.alive), hp:a&&a.hp, state:a&&a.state}; }''')
            print(lab, 'beetle slash1', r1)
            if not r1.get('alive') or r1.get('hp') != 1:
                hit_errs.append(lab+' beetle should survive first slash with hp 1: '+json.dumps(r1))
            fire_slash(page, dt)
            r2 = ev(page, '''() => { const a=window.__game.ants()[0]; return {dead: !a || !a.alive || ["launch","down","poof"].includes(a.state), a}; }''')
            print(lab, 'beetle slash2', r2)
            if not r2.get('dead'):
                hit_errs.append(lab+' beetle second slash missed')

            ev(page, '''() => {
              window.__game.clearBaddies();
              window.__game.setPos(0, 3.05);
              window.__game.setYaw(0);
              window.__game.spawnBugAt("beetle", 0, 3.05-0.70);
              window.__game.freezeAnts();
            }''')
            ev(page, '() => window.__game.step(0)')
            fire_spin(page, dt)
            r = ev(page, '''() => { const a=window.__game.ants()[0]; return {dead:!a||!a.alive||["launch","down","poof"].includes(a.state), a}; }''')
            print(lab, 'beetle spin', r)
            if not r.get('dead'):
                hit_errs.append(lab+' beetle spin missed')

            # boss: set hp 2 via startBoss then... can't set hp. slash shouldn't one-shot 8hp. spin 2 dmg.
            ev(page, '''() => {
              window.__game.clearBaddies();
              window.__game.setPos(0, 3.05);
              window.__game.setYaw(0); window.__game.setCamYaw(0);
              window.__game.startBoss();
            }''')
            ev(page, '() => window.__game.step(0)')
            # teleport boss in front — without hook, walk it? freeze then we can't move it.
            # spawnBugAt boss does not set Game.boss; startBoss does but at edge.
            # Add a quick eval that uses startBoss then we slash only if in range.
            # I'll expose setPos on last ant through a new hook in a minute if needed.
            print(lab, 'boss before', ev(page, '() => window.__game.boss'))


            # boss slash/spin with placed captain
            ev(page, '''() => {
              window.__game.clearBaddies();
              window.__game.setPos(0, 3.05);
              window.__game.setYaw(0); window.__game.setCamYaw(0);
              window.__game.startBoss();
              const i = window.__game.ants().length - 1;
              window.__game.setAntPos(i, 0, 3.05-0.85, 0);
              window.__game.setAntHp(i, 2);
              window.__game.freezeAnts();
            }''')
            ev(page, '() => window.__game.step(0)')
            print(lab, 'boss placed', ev(page, '() => window.__game.boss'))
            fire_slash(page, dt)
            r1 = ev(page, '() => window.__game.boss')
            print(lab, 'boss slash1', r1)
            if not r1 or not r1.get('alive') or r1.get('hp') != 1:
                hit_errs.append(lab+' boss should survive first slash with hp 1: '+json.dumps(r1))
            fire_slash(page, dt)
            r2 = ev(page, '() => window.__game.boss')
            print(lab, 'boss slash2', r2)
            dead = (not r2) or (not r2.get('alive'))
            if not dead:
                hit_errs.append(lab+' boss second slash missed: '+json.dumps(r2))

            ev(page, '''() => {
              window.__game.clearBaddies();
              window.__game.setPos(0, 3.05);
              window.__game.setYaw(0);
              window.__game.startBoss();
              const i = window.__game.ants().length - 1;
              window.__game.setAntPos(i, 0, 3.05-0.85, 0);
              window.__game.setAntHp(i, 2);
              window.__game.freezeAnts();
            }''')
            ev(page, '() => window.__game.step(0)')
            fire_spin(page, dt)
            r = ev(page, '() => window.__game.boss')
            print(lab, 'boss spin', r)
            if r and r.get('alive'):
                hit_errs.append(lab+' boss spin should defeat 2hp captain: '+json.dumps(r))

                print('HIT', 'FAIL' if hit_errs else 'PASS', hit_errs)

        # size clip checks
        ctx.close()
        for w,h in SIZES:
            tag=f'{w}x{h}'
            c=b.new_context(viewport={'width':w,'height':h}, device_scale_factor=1, has_touch=True)
            pg=c.new_page()
            pe2=[]
            pg.on('console', lambda m: (m.type=='error' and not any(k in (m.text or '') for k in ('ReadPixels','GPU stall','swiftshader')) and pe2.append('console:'+m.text)))
            pg.on('pageerror', lambda e: pe2.append('page:'+str(e)))
            boot(pg)
            ev(pg, '() => window.__game.setTitleT(1.8)')
            ev(pg, '() => window.__game.step(0)')
            time.sleep(0.05)
            pg.screenshot(path=str(SHOTS/f'{tag}_full_title.png'))
            cl=collect_clip(pg)
            if cl:
                print('CLIP title', tag, cl)
                clips_all += [{'where':tag+'-title', **x} for x in cl]
            to_play(pg)
            ev(pg, '''() => {
              window.__game.setPos(0.25, 1.85);
              window.__game.setYaw(0); window.__game.setCamYaw(0);
              window.__game.spawnBugAt("ant", -0.8, -0.2);
              window.__game.spawnBugAt("beetle", 0.6, 0.2);
              window.__game.freezeAnts();
              const el=document.getElementById("banner"); if(el) el.classList.remove("show");
            }''')
            ev(pg, '() => window.__game.step(0)')
            pg.screenshot(path=str(SHOTS/f'{tag}_full_play.png'))
            cl=collect_clip(pg)
            if cl:
                print('CLIP play', tag, cl)
                clips_all += [{'where':tag+'-play', **x} for x in cl]
            if pe2:
                print('ERR', tag, pe2)
                errs.extend([tag+':'+e for e in pe2])
            c.close()
        b.close()

    # write gif from selected title frames (even indices)
    try:
        frames = [Image.open(SHOTS / f'844x390_full_title_t{i}.png').convert('P', palette=Image.ADAPTIVE, colors=48) for i in range(len(times))]
        frames[0].save(SHOTS/'844x390_full_title.gif', save_all=True, append_images=frames[1:], duration=140, loop=0, optimize=True)
        print('gif', SHOTS/'844x390_full_title.gif', (SHOTS/'844x390_full_title.gif').stat().st_size)
    except Exception as e:
        print('gif fail', e)
        errs.append('gif: '+str(e))

    if clips_all:
        print('CLIPS', json.dumps(clips_all, indent=2))
        errs.append('HUD clipped: '+', '.join(c['where']+':'+c['id'] for c in clips_all))
    errs.extend(pe)
    errs.extend(hit_errs)
    print('RESULT', 'FAIL' if errs else 'PASS')
    for e in errs:
        print(' -', e)
    return 0 if not errs else 1

if __name__ == '__main__':
    raise SystemExit(run())
