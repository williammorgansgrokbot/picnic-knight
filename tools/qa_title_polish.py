#!/usr/bin/env python3
"""Title polish QA: logo layout, Stormy scale, clips, forward-motion, shots + GIF."""
import json, math, time
from pathlib import Path
from PIL import Image
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
        'btnPlay','logo','btnPause','btnMute','btnMuteTitle','waveNum','scoreNum','arrow','banner','skipHint',
        'bestScore','bossWrap','perks'];
      const w = window.innerWidth, h = window.innerHeight;
      const out = [];
      for (const id of ids) {
        const el = document.getElementById(id) || document.querySelector('.'+id);
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

def layout(page):
    return ev(page, '''() => {
      const box = (id) => {
        const el = document.getElementById(id) || document.querySelector('.'+id);
        if (!el) return null;
        const st = getComputedStyle(el);
        if (st.display === 'none' || st.visibility === 'hidden') return null;
        const r = el.getBoundingClientRect();
        return {id, left:r.left, top:r.top, right:r.right, bottom:r.bottom, w:r.width, h:r.height};
      };
      const overlap = (a,b) => {
        if (!a || !b) return 0;
        const x = Math.max(0, Math.min(a.right,b.right) - Math.max(a.left,b.left));
        const y = Math.max(0, Math.min(a.bottom,b.bottom) - Math.max(a.top,b.top));
        return x*y;
      };
      const logo = box('logo'), play = box('btnPlay'), mute = box('btnMuteTitle');
      const perks = box('perks'), best = box('bestScore');
      return {
        viewport: {w: innerWidth, h: innerHeight},
        logo, play, mute, perks, best,
        overlap: {
          logo_play: overlap(logo, play),
          logo_mute: overlap(logo, mute),
          logo_perks: overlap(logo, perks),
          logo_best: overlap(logo, best)
        }
      };
    }''')

def boot(page):
    page.goto(URL, wait_until='networkidle', timeout=45000)
    page.wait_for_function('window.__game && window.__game.ready === true', timeout=25000)

def attach_console(page, bucket):
    def on_con(m):
        t = m.text or ''
        if m.type in ('error','assert') and not any(k.lower() in t.lower() for k in NOISE):
            bucket.append('console:'+t)
    def on_err(e):
        bucket.append('page:'+str(e))
    page.on('console', on_con)
    page.on('pageerror', on_err)

def to_play(page):
    ev(page, '''() => {
      if (window.__game.state === "title" || window.__game.state === "boot") window.__game.start();
      if (window.__game.state === "steal") window.__game.skipSteal();
      if (window.__game.ensurePlay) window.__game.ensurePlay();
      window.__game.clearBaddies();
      window.__game.freeze(true);
      window.__game.setTimeLeft(180);
    }''')

def sample_movers(page):
    return ev(page, '() => window.__game.movers()')

def facing_ok(a, b, min_px=3.5):
    """Return (ok, reason) comparing screen dx to sprite flip."""
    dsx = b['sx'] - a['sx']
    if abs(dsx) < min_px:
        return True, 'small'
    # art faces right when scaleX > 0, so scaleX and dsx should share a sign
    face = 1 if b.get('scaleX', 0) >= 0 else -1
    if (dsx > 0 and face > 0) or (dsx < 0 and face < 0):
        return True, 'ok'
    return False, f"moonwalk kind={b.get('kind')} dsx={dsx:.2f} scaleX={b.get('scaleX'):.3f} face={b.get('face')}"

def run():
    errs = []
    clips_all = []
    overlaps = []
    face_results = []
    sizes_ok = None
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--use-gl=swiftshader','--ignore-gpu-blocklist'], headless=True)
        # official 844 shots + facing title/steal
        pe = []
        ctx = browser.new_context(viewport={'width':844,'height':390}, device_scale_factor=1, has_touch=True)
        page = ctx.new_page()
        attach_console(page, pe)
        boot(page)
        ev(page, '() => window.__game.freeze(true)')
        sizes_ok = ev(page, '() => ({stormy: window.__game.stormyH, emma: window.__game.emmaH, ratio: window.__game.stormyH / window.__game.emmaH})')
        print('sizes', sizes_ok)
        if abs(sizes_ok['ratio'] - 0.55) > 0.001:
            errs.append('Stormy/Emma ratio is %s, expected 0.55' % sizes_ok['ratio'])

        # title frames + logo layout
        times = [0.2, 0.6, 1.0, 1.4, 1.8, 2.2, 2.8, 3.6, 4.6, 5.8]
        for i, tt in enumerate(times):
            ev(page, f'() => window.__game.setTitleT({tt})')
            ev(page, '() => window.__game.syncNow()')
            page.screenshot(path=str(SHOTS / f'844x390_title_polish_t{i}.png'))
        ev(page, '() => window.__game.setTitleT(2.85)')
        ev(page, '() => window.__game.syncNow()')
        page.screenshot(path=str(SHOTS/'844x390_title_polish_title.png'))
        lay = layout(page)
        print('layout844', json.dumps(lay, indent=2))
        for k,v in lay['overlap'].items():
            if v > 1:
                overlaps.append(('844-'+k, v, lay))
        clips = collect_clip(page)
        if clips: clips_all += [{'where':'844-title', **c} for c in clips]

        # title forward-motion: step through a period
        ev(page, '() => { window.__game.setTitleT(0.15); window.__game.freeze(true); }')
        prev = {}
        fails = []
        samples = 0
        for i in range(48):
            ev(page, '() => window.__game.step(1/30)')
            cur = { (m['kind'], round(m['z'],3), round(m.get('h',0),3)): m for m in sample_movers(page) }
            # match by kind+z (lane) + nearest x for ants
            ants_prev = [m for k,m in prev.items() if m['kind']=='ant']
            ants_cur = [m for k,m in cur.items() if m['kind']=='ant']
            def match(old, newlist):
                if old['kind'] != 'ant':
                    for m in newlist:
                        if m['kind']==old['kind']:
                            return m
                    return None
                best=None; bd=1e9
                for m in newlist:
                    if m['kind']!='ant': continue
                    if abs(m['z']-old['z'])>0.05: continue
                    d=abs(m['sx']-old['sx'])
                    if d<bd: bd=d; best=m
                return best
            newlist = list(cur.values())
            for old in prev.values():
                nxt = match(old, newlist)
                if not nxt: continue
                # ignore wrap-around jumps
                if abs(nxt['sx']-old['sx']) > 200: continue
                ok, reason = facing_ok(old, nxt)
                samples += 1
                if not ok:
                    fails.append(reason + f' t={i}')
            prev = { (m['kind'], round(m['z'],3), round(m['x'],2)): m for m in newlist }
        face_results.append({'where':'title', 'samples':samples, 'fails':fails})
        print('title facing samples', samples, 'fails', len(fails))
        if fails:
            print('title fails', fails[:8])

        # steal cinematic: Stormy (odd round) mid-run shot + facing
        ev(page, '''() => {
          window.__game.start();
          // start() begins steal; keep frozen after posing
        }''')
        ev(page, '() => window.__game.freeze(false)')
        # reset steal to t=0 with stormy
        ev(page, '''() => {
          window.__game.freeze(true);
          window.__game.startSteal();
          const s = window.__game.steal();
          window.__game.freeze(true);
        }''')
        # step steal from 0
        ev(page, '() => { window.__game.startSteal(); window.__game.freeze(true); }')
        prev = {}
        fails = []
        samples = 0
        shot_done = False
        for i in range(90):
            ev(page, '() => window.__game.step(1/30)')
            st = ev(page, '() => window.__game.steal()')
            movers = sample_movers(page)
            if st and (not shot_done) and 1.15 <= st['t'] <= 1.35:
                page.screenshot(path=str(SHOTS/'844x390_title_polish_steal.png'))
                shot_done = True
                hs = ev(page, '''() => {
                  const m = window.__game.movers();
                  const s = m.find(x=>x.kind==="stormy");
                  const e = m.find(x=>x.kind==="emma");
                  return {sH:s&&s.h, eH:e&&e.h, ratio:(s&&e)?s.h/e.h:null, steal:window.__game.steal()};
                }''')
                print('steal mid sizes', hs)
            curlist = movers
            if prev:
                def match2(old, newlist):
                    for m in newlist:
                        if m['kind']==old['kind']: return m
                    return None
                for old in prev:
                    nxt = match2(old, curlist)
                    if not nxt or not nxt.get('sx') or old.get('sx') is None: continue
                    if abs(nxt['sx']-old['sx'])>200: continue
                    # skip if either not visible-ish offscreen
                    if nxt['sx'] < -20 or nxt['sx'] > 880 or old['sx'] < -20: continue
                    ok, reason = facing_ok(old, nxt, min_px=2.5)
                    samples += 1
                    if not ok: fails.append(reason + f" t={st and st.get('t')}")
            prev = curlist
            if ev(page, '() => window.__game.state') != 'steal':
                break
        if not shot_done:
            ev(page, '''() => { window.__game.startSteal(); window.__game.freeze(true); }''')
            # set time by stepping
            ev(page, '''() => { for (let i=0;i<36;i++) window.__game.step(1/30); }''')
            page.screenshot(path=str(SHOTS/'844x390_title_polish_steal.png'))
        face_results.append({'where':'steal', 'samples':samples, 'fails':fails})
        print('steal facing samples', samples, 'fails', len(fails))
        if fails: print('steal fails', fails[:8])

        # in-game bugs vs camera orbit
        to_play(page)
        ev(page, '''() => {
          window.__game.clearBaddies();
          window.__game.freeze(true);
          window.__game.spawnAntAt(0, 0.2);
          window.__game.spawnBugAt("beetle", 1.2, -0.4);
        }''')
        fails = []
        samples = 0
        for yaw in [0, math.pi/2, math.pi, 3*math.pi/2, 0.6, 2.4]:
            ev(page, f'() => {{ window.__game.setCamYaw({yaw}); window.__game.setAntPos(0, 0, 0.2); window.__game.setAntPos(1, 1.2, -0.4); }}')
            for (vx, vz) in [(1.2, 0), (-1.2, 0), (0, 1.2), (0, -1.2), (0.9, 0.9), (-0.9, 0.7)]:
                ev(page, f'''() => {{
                  window.__game.setAntPos(0, 0, 0.2);
                  window.__game.setAntPos(1, 1.2, -0.4);
                  window.__game.setAntVel(0, {vx}, {vz});
                  window.__game.setAntVel(1, {vx}, {vz});
                  window.__game.syncNow();
                }}''')
                a0 = sample_movers(page)
                ev(page, f'''() => {{
                  const ants = window.__game.ants();
                  // nudge without AI by writing pos+vel then step(0) under freeze
                  window.__game.setAntPos(0, ants[0].x + {vx}*0.08, ants[0].z + {vz}*0.08);
                  window.__game.setAntPos(1, ants[1].x + {vx}*0.08, ants[1].z + {vz}*0.08);
                  window.__game.setAntVel(0, {vx}, {vz});
                  window.__game.setAntVel(1, {vx}, {vz});
                  window.__game.syncNow();
                }}''')
                a1 = sample_movers(page)
                # match by kind and roughly same start
                def take(kind, lst):
                    return [m for m in lst if m['kind']==kind]
                # Skip travel that is almost straight into/out of the camera.
                # Perspective then slides the sprite a few pixels sideways, which
                # is not a facing error.
                yaw_r = float(ev(page, '() => window.__game.camYaw()'))
                # camera right in XZ is (cos(yaw), sin(yaw)) matching screenFace fallback
                # (world velocity dotted with camera right)
                lat = abs(vx * math.cos(yaw_r) + vz * math.sin(yaw_r))
                spd = math.hypot(vx, vz) or 1
                if lat / spd < 0.35:
                    continue
                for kind in set(m['kind'] for m in a1):
                    olds, news = take(kind, a0), take(kind, a1)
                    if not olds or not news: continue
                    ok, reason = facing_ok(olds[0], news[0], min_px=2.0)
                    samples += 1
                    if not ok:
                        fails.append(reason + f' yaw={yaw:.2f} vel=({vx},{vz})')
        face_results.append({'where':'play-orbit', 'samples':samples, 'fails':fails})
        print('play facing samples', samples, 'fails', len(fails))
        if fails: print('play fails', fails[:12])

        if pe: errs += pe
        ctx.close()

        # clip + console + overlap at all 3 sizes (title + play)
        for w,h in SIZES:
            pe2 = []
            ctx = browser.new_context(viewport={'width':w,'height':h}, device_scale_factor=1, has_touch=True)
            pg = ctx.new_page()
            attach_console(pg, pe2)
            boot(pg)
            ev(pg, '() => window.__game.freeze(true)')
            ev(pg, '() => window.__game.setTitleT(1.8)')
            ev(pg, '() => window.__game.syncNow()')
            lay = layout(pg)
            tag = f'{w}x{h}'
            print('layout', tag, 'logoH', lay['logo'] and round(lay['logo']['h'],1), 'overlap', lay['overlap'])
            for k,v in lay['overlap'].items():
                if v > 1: overlaps.append((tag+'-'+k, v, lay))
            cl = collect_clip(pg)
            if cl: clips_all += [{'where':tag+'-title', **x} for x in cl]
            pg.screenshot(path=str(SHOTS / f'{tag}_title_polish_layout.png'))
            to_play(pg)
            ev(pg, '() => window.__game.freeze(true)')
            ev(pg, '() => window.__game.syncNow()')
            cl = collect_clip(pg)
            if cl: clips_all += [{'where':tag+'-play', **x} for x in cl]
            pg.screenshot(path=str(SHOTS / f'{tag}_title_polish_play.png'))
            if pe2: errs += [tag+':'+e for e in pe2]
            ctx.close()

        # GIF from title frames
        frames = [Image.open(SHOTS / f'844x390_title_polish_t{i}.png').convert('P', palette=Image.ADAPTIVE, colors=48) for i in range(len(times))]
        frames[0].save(SHOTS/'844x390_title_polish_title.gif', save_all=True, append_images=frames[1:], duration=140, loop=0, optimize=True)
        print('gif', SHOTS/'844x390_title_polish_title.gif', (SHOTS/'844x390_title_polish_title.gif').stat().st_size)

        browser.close()

    if clips_all:
        print('CLIPS', json.dumps(clips_all, indent=2))
        errs.append('HUD clipped: '+', '.join(c['where']+':'+c['id'] for c in clips_all))
    if overlaps:
        print('OVERLAP', [(o[0], o[1]) for o in overlaps])
        errs.append('Logo overlap: '+', '.join(o[0] for o in overlaps))
    for fr in face_results:
        if fr['fails']:
            errs.append('Facing fails in %s (%d/%d): %s' % (fr['where'], len(fr['fails']), fr['samples'], '; '.join(fr['fails'][:6])))
        if fr['samples'] < 8:
            errs.append('Too few facing samples in %s: %d' % (fr['where'], fr['samples']))

    out = {'sizes': sizes_ok, 'face': [{k: (v if k!='fails' else v[:10]) for k,v in fr.items()} for fr in face_results], 'clips': clips_all, 'errs': errs}
    Path('/tmp/pk-title-polish-qa.json').write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    if errs:
        print('FAIL', errs)
        return 1
    print('PASS')
    return 0

if __name__ == '__main__':
    raise SystemExit(run())
