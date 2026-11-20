#!/usr/bin/env python3
"""Key and slice full-game sheets into art/ using expected-count valley splits."""
import os, sys
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from process_art import key, crop_pad

SRC = os.path.join(ROOT, 'art_src')
ART = os.path.join(ROOT, 'art')
PREV = os.path.join(ROOT, 'preview')
os.makedirs(PREV, exist_ok=True)

def resize_max(im, max_h=360, max_w=520):
    w, h = im.size
    s = min(1.0, max_h / float(h), max_w / float(w))
    if s < 0.999:
        im = im.resize((max(1, int(round(w * s))), max(1, int(round(h * s)))), Image.Resampling.LANCZOS)
    return im

def save(im, name, max_h=360, max_w=520):
    im = crop_pad(im, 8)
    im = resize_max(im, max_h, max_w)
    path = os.path.join(ART, name)
    im.save(path, 'PNG', optimize=True)
    print(f'  {name:28s} {im.size[0]:4d}x{im.size[1]:<4d} {os.path.getsize(path):7d}')
    return im

def split_n(im, n, alpha_thr=16):
    a = np.asarray(im.getchannel('A'))
    occ = (a > alpha_thr).sum(axis=0).astype(np.float64)
    xs = np.where(occ > 2)[0]
    if len(xs) < 8:
        return [im]
    x0, x1 = int(xs[0]), int(xs[-1])
    width = max(1, x1 - x0)
    sm = np.convolve(occ, np.ones(9) / 9.0, mode='same')
    cuts = [x0]
    for i in range(1, n):
        target = x0 + width * i / float(n)
        half = width / (n * 2.4)
        lo = int(max(x0 + 12, target - half))
        hi = int(min(x1 - 12, target + half))
        if hi <= lo:
            cuts.append(int(target))
            continue
        window = sm[lo:hi]
        cuts.append(int(lo + int(np.argmin(window))))
    cuts.append(x1 + 1)
    out = []
    for i in range(n):
        a0, a1 = cuts[i], cuts[i + 1]
        # pad a little but don't invade neighbors
        pad = 4
        left = max(0, a0 - pad if i == 0 else a0)
        right = min(im.width, a1 + pad if i == n - 1 else a1)
        piece = crop_pad(im.crop((left, 0, right, im.height)), 6)
        out.append(piece)
    return out, cuts

def process_sheet(raw, names, protect_wings=False, max_h=360, max_w=520, t0=30, t1=90, dom0=35):
    path = os.path.join(SRC, raw)
    im = key(path, t0=t0, t1=t1, dom0=dom0, protect_wings=protect_wings)
    prev = os.path.join(PREV, raw.replace('_raw.jpg', '_keyed.png'))
    im.save(prev, 'PNG', optimize=True)
    pieces, cuts = split_n(im, len(names))
    print(f'{raw}: {len(pieces)} pieces, cuts={cuts}')
    for i, name in enumerate(names):
        save(pieces[i], name, max_h, max_w)
    return pieces

def main():
    process_sheet('stormy_sausage_run_sheet_raw.jpg',
                  ['stormy_sausage_0.png', 'stormy_sausage_1.png', 'stormy_sausage_2.png'],
                  max_h=310, max_w=460)
    process_sheet('emma_sausage_run_sheet_raw.jpg',
                  ['emma_sausage_0.png', 'emma_sausage_1.png', 'emma_sausage_2.png'],
                  max_h=340, max_w=480)
    process_sheet('beetle_anim_sheet_raw.jpg',
                  ['beetle_walk_0.png', 'beetle_walk_1.png', 'beetle_nibble.png', 'beetle_bonk.png', 'beetle_down.png'],
                  max_h=280, max_w=340)
    # wasp fly/dive: 5 figures on the sheet but last two are leftover ants — take first 3 via 5-split
    wasp = key(os.path.join(SRC, 'wasp_anim_sheet_raw.jpg'), t0=30, t1=90, dom0=35, protect_wings=True)
    wasp.save(os.path.join(PREV, 'wasp_anim_sheet_keyed.png'), 'PNG', optimize=True)
    wp, cuts = split_n(wasp, 5)
    print('wasp fly 5-split cuts', cuts)
    for i, name in enumerate(['wasp_fly_0.png', 'wasp_fly_1.png', 'wasp_dive.png']):
        save(wp[i], name, 270, 340)
    process_sheet('wasp_kill_sheet_raw.jpg',
                  ['wasp_bonk.png', 'wasp_down.png'],
                  protect_wings=True, max_h=280, max_w=360)
    process_sheet('boss_anim_sheet_raw.jpg',
                  ['boss_walk_0.png', 'boss_tele.png', 'boss_charge.png', 'boss_hurt.png', 'boss_down.png'],
                  max_h=340, max_w=420)
    bak = key(os.path.join(SRC, 'basket_raided_raw.jpg'), t0=30, t1=90, dom0=35)
    bak = crop_pad(bak, 10)
    save(bak, 'basket_bitten.png', max_h=260, max_w=280)
    print('done')

if __name__ == '__main__':
    main()
