#!/usr/bin/env python3
"""Build a standalone index.html (Three.js r160 + game + PNG/JPEG assets inlined)."""
import base64, os, re, json

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/'
ART = D + 'art/'

def b64(data, mime):
    return 'data:%s;base64,' % mime + base64.b64encode(data).decode()

NEED = [
    'picnic_ground_wide.jpg', 'logo.png',
    'knight_idle_0.png', 'knight_idle_1.png', 'knight_idle_2.png',
    'knight_idle_front.png', 'knight_idle_side.png', 'knight_idle_back34.png', 'knight_idle_back.png',
    'knight_run_1.png', 'knight_run_3.png',
    'knight_run_front_0.png', 'knight_run_front_1.png',
    'knight_run_side_0.png', 'knight_run_side_1.png',
    'knight_run_back_0.png', 'knight_run_back_1.png',
    'knight_run_back34_0.png',
    'knight_slash_0.png', 'knight_slash_1.png', 'knight_slash_2.png',
    'knight_spin_0.png', 'knight_spin_1.png', 'knight_spin_2.png',
    'ant_walk_0.png', 'ant_walk_1.png', 'ant_walk_2.png', 'ant_walk_3.png',
    'ant_nibble.png', 'ant_bonk.png', 'ant_down_0.png', 'ant_down_1.png',
    'fx_puff_0.png', 'fx_puff_1.png', 'fx_stars.png',
    'knight_run_34front_a.png', 'knight_run_34front_b.png',
    'knight_run_back34_0.png', 'knight_run_back34_1.png',
    'sandwich_intact.png', 'sandwich_bitten.png',
    'basket_intact.png', 'basket_bitten.png',
    'pie_intact.png', 'pie_bitten.png',
    'cookies_intact.png', 'cookies_bitten.png',
    'watermelon_intact.png', 'watermelon_bitten.png',
    'sausage_links.png',
    'stormy_run_0.png', 'stormy_run_1.png', 'stormy_run_2.png', 'stormy_grab.png',
    'emma_run_0.png', 'emma_run_1.png', 'emma_run_2.png', 'emma_grab.png',
    'stormy_sausage_0.png', 'stormy_sausage_1.png', 'stormy_sausage_2.png',
    'emma_sausage_0.png', 'emma_sausage_1.png', 'emma_sausage_2.png',
    'beetle_walk_0.png', 'beetle_walk_1.png', 'beetle_nibble.png', 'beetle_bonk.png', 'beetle_down.png',
    'wasp_fly_0.png', 'wasp_fly_1.png', 'wasp_dive.png', 'wasp_bonk.png', 'wasp_down.png',
    'boss_walk_0.png', 'boss_tele.png', 'boss_charge.png', 'boss_hurt.png', 'boss_down.png',
    'watcher_woman_0.png', 'watcher_woman_1.png', 'watcher_woman_2.png',
    'watcher_man_0.png', 'watcher_man_1.png', 'watcher_man_2.png',
    'bear_pop.png', 'bear_shimmy_0.png', 'bear_shimmy_1.png', 'bear_shimmy_2.png', 'bear_duck.png',
]
A = {}
for n in NEED:
    p = ART + n
    raw = open(p, 'rb').read()
    mime = 'image/jpeg' if n.endswith('.jpg') else 'image/png'
    A[n] = b64(raw, mime)

css = open(D + 'src/style.css').read()
html = open(D + 'src/template.html').read()
three = open(D + 'vendor/three.module.min.js').read()
m = re.search(r'export\{([^}]*)\};?\s*$', three)
assert m, 'could not wrap three.module.min.js'
pairs = []
for part in m.group(1).split(','):
    a = part.strip().split(' as ')
    pairs.append('%s:%s' % ((a[1].strip() if len(a) > 1 else a[0].strip()), a[0].strip()))
three_js = 'const THREE=(()=>{"use strict";' + three[:m.start()] + ';return Object.freeze({' + ','.join(pairs) + '});})();'

order = ['00_util', '10_audio', '20_input', '30_game']
game = '\n'.join(open(D + 'src/%s.js' % n).read() for n in order)
body = '(function(){"use strict";\n' + three_js + '\n' + game + '\n})();'
body = body.replace('</script', '<\\/script')
html = html.replace('/*CSS*/', css)
html = html.replace('<script>/*SCRIPT*/</script>',
                    '<script>window.__ASSETS=' + json.dumps(A) + ';</script>\n<script>\n' + body + '\n</script>')
out = D + 'index.html'
open(out, 'w').write(html)
print('index.html', round(os.path.getsize(out) / 1e6, 2), 'MB')
