#!/usr/bin/env python3
"""Picnic Knight — Stormy/Emma steal cinematic, timer, Round Clear QA."""
import math, time, json, hashlib
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

SHOTS = Path('/workspace/picnic-knight/shots')
SHOTS.mkdir(exist_ok=True)
URL = 'http://127.0.0.1:8767/index.html'
SIZES = [(844, 390), (932, 430), (667, 375)]

def collect_clip(page):
    return page.evaluate('''() => {
      const ids = ['pad','slashBtn','spinBtn','topLeft','meterWrap','topRight','timerPanel','timerNum',
        'btnPlay','logo','btnPause','btnMute','waveNum','scoreNum','arrow','banner','skipHint','cNext','cTitle','clearScore','clearPicnic'];
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

def step_to(page, seconds, dt):
    # Advance with the game's own step hook (dt capped at 1/30 inside).
    remain = seconds
    while remain > 1e-6:
        chunk = min(dt, remain, 1/30)
        ev(page, f'() => window.__game.step({chunk})')
        remain -= chunk

def boot(page):
    page.goto(URL, wait_until='networkidle', timeout=30000)
    page.wait_for_function('window.__game && window.__game.ready === true', timeout=20000)
    time.sleep(0.15)

def start_steal(page):
    ev(page, '() => { if (window.__game.state === "title" || window.__game.state === "boot") window.__game.start(); else window.__game.startSteal(); }')
    page.wait_for_function('window.__game.state === "steal"', timeout=8000)

def run():
    errs = []
    clips_all = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=['--use-gl=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--autoplay-policy=no-user-gesture-required'])

        # ---- 844 mid-steal, lineup already saved, HUD, clear, gif ----
        ctx = b.new_context(viewport={'width':844,'height':390}, device_scale_factor=1, has_touch=True)
        page = ctx.new_page()
        page_errs = []
        page.on('console', lambda m: (m.type=='error' and (page_errs.append('console:'+m.text), print('ERR', m.text))))
        page.on('pageerror', lambda e: (page_errs.append('page:'+str(e)), print('PAGE', e)))
        boot(page)

        # Mid-steal (Stormy grabs) + skip hint + timer at 3:00
        start_steal(page)
        ev(page, '() => window.__game.poseSteal("stormy")')
        time.sleep(0.12)
        page.screenshot(path=str(SHOTS / '844x390_steal_mid.png'))
        st = ev(page, '() => window.__game.steal()')
        print('poseSteal', st)
        if not st or st.get('who') != 'stormy' or not st.get('grabbed'):
            errs.append('poseSteal did not land mid-grab for Stormy')
        hud = ev(page, '''() => ({
          timer: document.getElementById('timerNum').textContent,
          skip: getComputedStyle(document.getElementById('skipHint')).display,
          state: window.__game.state
        })''')
        print('hud mid-steal', hud)
        if hud['timer'] != '3:00':
            errs.append('timer should hold 3:00 during steal, got ' + str(hud['timer']))
        clips = collect_clip(page)
        if clips:
            print('CLIP steal', clips)
            clips_all += [{'where':'steal844', **c} for c in clips]

        # Frame strip + GIF of a full steal, using step()
        ev(page, '() => { window.__game.freeze(true); window.__game.startSteal(); window.__game.freeze(true); }')
        frames = []
        times = [0.15, 0.55, 1.00, 1.45, 1.90, 2.10, 2.50, 3.10, 3.80, 4.50]
        prev = 0
        for i, t in enumerate(times):
            step_to(page, t - prev, 1/60)
            prev = t
            path = SHOTS / f'steal_frame_{i:02d}.png'
            page.screenshot(path=str(path))
            frames.append(Image.open(path).convert('RGB'))
            info = ev(page, '() => ({state: window.__game.state, steal: window.__game.steal(), t: window.__game.timeLeft})')
            print('frame', i, t, info)

        # After last frame we may have auto-ended into play. Capture banner if so.
        # Horizontal strip
        fw, fh = frames[0].size
        pad = 4
        strip = Image.new('RGB', (fw * len(frames) + pad * (len(frames)+1), fh + pad*2), (30, 36, 22))
        x = pad
        for im in frames:
            strip.paste(im, (x, pad))
            x += fw + pad
        # downscale strip height for a manageable file, keep readable
        target_h = 195
        sc = target_h / strip.height
        strip_sm = strip.resize((max(1,int(strip.width*sc)), target_h), Image.LANCZOS)
        strip_sm.save(SHOTS / '844x390_steal_strip.png', optimize=True)
        # GIF
        gif_frames = [im.resize((844, 390), Image.LANCZOS) for im in frames]
        gif_frames[0].save(SHOTS / '844x390_steal.gif', save_all=True, append_images=gif_frames[1:],
                           duration=380, loop=0, optimize=True)
        print('strip+gif saved')

        # If steal already ended, start play HUD with a mid-round timer
        ev(page, '''() => {
          if (window.__game.state === "steal") window.__game.skipSteal();
          if (window.__game.state !== "play") { window.__game.start(); if (window.__game.state === "steal") window.__game.skipSteal(); }
          window.__game.clearBaddies();
          window.__game.freeze(true);
          window.__game.setTimeLeft(125.4);
          document.getElementById("banner").classList.remove("show");
        }''')
        page.wait_for_function('window.__game.state === "play"', timeout=8000)
        time.sleep(0.12)
        page.screenshot(path=str(SHOTS / '844x390_hud_timer.png'))
        timer = ev(page, '() => document.getElementById("timerNum").textContent')
        print('hud timer', timer)
        if timer not in ('2:06', '2:05'):
            errs.append('expected timer around 2:06, got ' + str(timer))
        clips = collect_clip(page)
        if clips:
            print('CLIP hud', clips)
            clips_all += [{'where':'hud844', **c} for c in clips]

        # ROUND START banner shot
        ev(page, '() => { window.__game.skipSteal && 0; }')
        # force banner visible
        ev(page, '''() => {
          const el = document.getElementById('banner');
          el.textContent = 'ROUND START';
          el.classList.add('show');
        }''')
        time.sleep(0.08)
        page.screenshot(path=str(SHOTS / '844x390_round_start.png'))
        ev(page, '() => document.getElementById("banner").classList.remove("show")')

        # Round Clear
        ev(page, '() => { window.__game.setFoodHp(72); window.__game.endRound(); }')
        page.wait_for_function('window.__game.state === "clear"', timeout=5000)
        time.sleep(0.15)
        page.screenshot(path=str(SHOTS / '844x390_round_clear.png'))
        clear = ev(page, '''() => ({
          score: document.getElementById('clearScore').textContent,
          picnic: document.getElementById('clearPicnic').textContent,
          title: document.querySelector('#clear h2').textContent
        })''')
        print('clear', clear)
        if 'Round Clear' not in clear['title']:
            errs.append('clear title missing: ' + clear['title'])
        if clear['picnic'] != '72%':
            errs.append('picnic remaining expected 72%, got ' + clear['picnic'])
        clips = collect_clip(page)
        if clips:
            print('CLIP clear', clips)
            clips_all += [{'where':'clear844', **c} for c in clips]

        # Next Round should replay steal (Emma, round 2 is even)
        ev(page, '() => window.__game.nextRound()')
        page.wait_for_function('window.__game.state === "steal"', timeout=5000)
        who = ev(page, '() => window.__game.steal() && window.__game.steal().who')
        rnd = ev(page, '() => window.__game.round')
        print('next round steal who', who, 'round', rnd)
        if rnd != 2 or who != 'emma':
            errs.append(f'round 2 should be Emma steal, got round={rnd} who={who}')
        ev(page, '() => window.__game.poseSteal("emma")')
        time.sleep(0.1)
        page.screenshot(path=str(SHOTS / '844x390_steal_emma.png'))

        errs.extend(page_errs)
        ctx.close()

        # ---- clip check at all 3 sizes: steal, play HUD, clear ----
        for w, h in SIZES:
            tag = f'{w}x{h}'
            c = b.new_context(viewport={'width':w,'height':h}, device_scale_factor=1, has_touch=True)
            pg = c.new_page()
            pe = []
            pg.on('console', lambda m: (m.type=='error' and pe.append('console:'+m.text)))
            pg.on('pageerror', lambda e: pe.append('page:'+str(e)))
            boot(pg)
            start_steal(pg)
            ev(pg, '() => window.__game.poseSteal("stormy")')
            time.sleep(0.08)
            pg.screenshot(path=str(SHOTS / f'{tag}_steal.png'))
            cl = collect_clip(pg)
            if cl:
                print('CLIP', tag, 'steal', cl)
                clips_all += [{'where':tag+'-steal', **x} for x in cl]
            ev(pg, '() => window.__game.skipSteal()')
            pg.wait_for_function('window.__game.state === "play"', timeout=8000)
            ev(pg, '() => { window.__game.clearBaddies(); window.__game.setTimeLeft(97.2); }')
            time.sleep(0.08)
            pg.screenshot(path=str(SHOTS / f'{tag}_timer.png'))
            cl = collect_clip(pg)
            if cl:
                print('CLIP', tag, 'timer', cl)
                clips_all += [{'where':tag+'-timer', **x} for x in cl]
            # banner
            ev(pg, '() => { const el = document.getElementById("banner"); el.textContent="ROUND START"; el.classList.add("show"); }')
            time.sleep(0.05)
            pg.screenshot(path=str(SHOTS / f'{tag}_banner.png'))
            cl = collect_clip(pg)
            if cl:
                print('CLIP', tag, 'banner', cl)
                clips_all += [{'where':tag+'-banner', **x} for x in cl]
            ev(pg, '() => document.getElementById("banner").classList.remove("show")')
            ev(pg, '() => { window.__game.setFoodHp(81); window.__game.endRound(); }')
            pg.wait_for_function('window.__game.state === "clear"', timeout=5000)
            time.sleep(0.08)
            pg.screenshot(path=str(SHOTS / f'{tag}_clear.png'))
            cl = collect_clip(pg)
            if cl:
                print('CLIP', tag, 'clear', cl)
                clips_all += [{'where':tag+'-clear', **x} for x in cl]
            if pe:
                print('ERR', tag, pe)
                errs.extend([tag+':'+e for e in pe])
            c.close()

        # ---- 60 vs 120 fps: steal grab time and timer expiry ----
        ctx = b.new_context(viewport={'width':844,'height':390}, device_scale_factor=1, has_touch=True)
        page = ctx.new_page()
        pe = []
        page.on('console', lambda m: (m.type=='error' and pe.append('console:'+m.text)))
        page.on('pageerror', lambda e: pe.append('page:'+str(e)))
        boot(page)

        def measure_grab(dt):
            start_steal(page)
            ev(page, '() => window.__game.freeze(true)')
            grabbed_at = None
            t = 0
            # step just past expected grab
            while t < 3.2:
                ev(page, f'() => window.__game.step({dt})')
                t += min(dt, 1/30)  # step hook caps dt at 1/30
                st = ev(page, '() => window.__game.steal()')
                if st and st.get('grabbed'):
                    grabbed_at = st['t']
                    break
            return grabbed_at

        # Important: step() caps dt at 1/30, so passing 1/60 and 1/120 both advance by that dt
        g60 = measure_grab(1/60)
        g120 = measure_grab(1/120)
        print('grab t @60', g60, '@120', g120)
        if g60 is None or g120 is None:
            errs.append(f'grab never fired 60={g60} 120={g120}')
        elif abs(g60 - g120) > 0.05:
            errs.append(f'grab time drifted 60={g60:.3f} 120={g120:.3f}')
        elif not (1.85 <= g60 <= 2.05):
            errs.append(f'grab time unexpected {g60}')

        def measure_timer(dt, start=2.0):
            ev(page, '''() => {
              if (window.__game.state === "steal") window.__game.skipSteal();
              if (window.__game.state !== "play") { window.__game.start(); if (window.__game.state === "steal") window.__game.skipSteal(); }
              window.__game.clearBaddies();
            }''')
            page.wait_for_function('window.__game.state === "play"', timeout=8000)
            ev(page, '() => window.__game.freeze(true)')
            ev(page, f'() => window.__game.setTimeLeft({start})')
            t = 0
            # step a little past start so we must hit 0
            limit = start + 0.2
            while t < limit:
                ev(page, f'() => window.__game.step({dt})')
                t += min(dt, 1/30)
                st = ev(page, '() => window.__game.state')
                if st == 'clear':
                    return t
            return None

        t60 = measure_timer(1/60, 1.5)
        t120 = measure_timer(1/120, 1.5)
        print('timer end @60', t60, '@120', t120)
        if t60 is None or t120 is None:
            errs.append(f'timer did not expire 60={t60} 120={t120}')
        elif abs(t60 - t120) > 0.08:
            errs.append(f'timer expiry drifted 60={t60:.3f} 120={t120:.3f}')
        elif not (1.45 <= t60 <= 1.62):
            errs.append(f'timer expiry unexpected {t60}')

        # slash still works after skip (don't regress)
        ev(page, '''() => {
          if (window.__game.state === "clear") window.__game.nextRound();
          if (window.__game.state === "steal") window.__game.skipSteal();
          window.__game.clearBaddies();
          window.__game.setPos(0, 1.6);
          window.__game.setYaw(0);
          window.__game.setCamYaw(0);
          window.__game.spawnAntAt(0, 0.7);
        }''')
        ev(page, '() => window.__game.slash()')
        step_to(page, 0.2, 1/60)
        ants = ev(page, '() => window.__game.ants()')
        print('post-steal slash ants', ants)
        dead = any((not a['alive']) or a['state'] in ('launch','down','poof') for a in ants)
        if not dead:
            errs.append('slash after steal did not kill in-front ant')

        errs.extend(pe)
        ctx.close()
        b.close()

    if clips_all:
        print('CLIPS FOUND', json.dumps(clips_all, indent=2))
        errs.append('HUD clipped: ' + ', '.join(c['where']+':'+c['id'] for c in clips_all))
    if page_errs if False else None:
        pass
    print('RESULT', 'FAIL' if errs else 'PASS')
    for e in errs:
        print(' -', e)
    return 0 if not errs else 1

if __name__ == '__main__':
    raise SystemExit(run())
