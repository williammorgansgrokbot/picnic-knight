#!/usr/bin/env python3
"""Despill, split sheets into individual sprites, recrop blanket."""
import os
import numpy as np
from PIL import Image, ImageFilter
import scipy.ndimage as nd

ART = '/workspace/picnic-knight/art'
SRC = '/workspace/picnic-knight/art_src'

def despill_trails(im, g_over=8):
    a = np.asarray(im).copy()
    rgb = a[..., :3].astype(np.float32)
    al = a[..., 3]
    gish = (al > 16) & (rgb[..., 1] > rgb[..., 0] + g_over) & (rgb[..., 1] > rgb[..., 2] + g_over)
    # pull green down toward max(r,b) (keep a tiny warm bias)
    target = np.maximum(rgb[..., 0], rgb[..., 2])
    rgb[..., 1] = np.where(gish, target, rgb[..., 1])
    a[..., :3] = rgb.clip(0, 255).astype(np.uint8)
    return Image.fromarray(a, 'RGBA')

def crop_pad(im, pad=6):
    bb = im.getchannel('A').point(lambda v: 255 if v > 12 else 0).getbbox()
    if not bb:
        return im
    l, t, r, b = bb
    l, t = max(0, l - pad), max(0, t - pad)
    r, b = min(im.width, r + pad), min(im.height, b + pad)
    return im.crop((l, t, r, b))

def split_n(im, n, names, min_alpha=24):
    occ = (np.asarray(im.getchannel('A')) > min_alpha).sum(0).astype(np.float32)
    # smooth
    k = 9
    ker = np.ones(k) / k
    sm = np.convolve(occ, ker, mode='same')
    # find valley indices between n peaks: iteratively pick deepest local min in remaining gaps
    # first find tight bbox of content
    xs = np.where(sm > 8)[0]
    x0, x1 = int(xs[0]), int(xs[-1])
    # expected rough centers
    cuts = []
    # search valleys in n-1 interior bands
    width = x1 - x0
    for i in range(1, n):
        # search window around the i/n mark, but favor true minima
        c = x0 + int(width * i / n)
        w = int(width / (2 * n)) + 30
        lo, hi = max(x0 + 20, c - w), min(x1 - 20, c + w)
        seg = sm[lo:hi]
        # prefer low occupancy
        idx = lo + int(np.argmin(seg))
        cuts.append(idx)
    bounds = [0] + cuts + [im.width]
    print('cuts', cuts, 'bounds', bounds)
    out = []
    for (a, b), name in zip(zip(bounds[:-1], bounds[1:]), names):
        piece = crop_pad(im.crop((a, 0, b, im.height)))
        path = os.path.join(ART, name + '.png')
        piece.save(path, optimize=True)
        print(' ', name, piece.size, 'x', a, b)
        out.append(path)
    return out

def main():
    kn = Image.open(os.path.join(ART, 'knight_poses.png'))
    kn = despill_trails(kn, g_over=6)
    kn.save(os.path.join(ART, 'knight_poses.png'), optimize=True)
    split_n(kn, 4, ['knight_idle', 'knight_run', 'knight_slash', 'knight_spin'])

    bg = Image.open(os.path.join(ART, 'bugs.png'))
    # do NOT despill bugs — wasp wings are pale mint on purpose
    split_n(bg, 4, ['ant', 'beetle', 'wasp', 'boss'])

    # recrop blanket using row/col majority
    bl = Image.open(os.path.join(SRC, 'blanket_grass_raw.jpg')).convert('RGB')
    arr = np.asarray(bl).astype(np.int16)
    gdom = arr[..., 1] - np.maximum(arr[..., 0], arr[..., 2])
    row = (gdom < 10).mean(1)
    col = (gdom < 10).mean(0)
    ys = np.where(row > 0.4)[0]
    xs = np.where(col > 0.4)[0]
    # inset a few px to the stitch
    y0, y1 = int(ys[0]) + 4, int(ys[-1]) - 4
    x0, x1 = int(xs[0]) + 4, int(xs[-1]) - 4
    blanket = bl.crop((x0, y0, x1, y1))
    blanket.save(os.path.join(ART, 'blanket.jpg'), quality=92, optimize=True)
    print('blanket crop', blanket.size, (x0, y0, x1, y1))
    # keep full picnic ground too
    bl.save(os.path.join(ART, 'picnic_ground.jpg'), quality=92, optimize=True)

if __name__ == '__main__':
    main()
