#!/usr/bin/env python3
"""Chroma-key and slice Picnic Knight preview art (Ski Jump / Jet Ski pipeline)."""
import os, sys
import numpy as np
from PIL import Image, ImageFilter, ImageDraw, ImageFont
import scipy.ndimage as nd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'art_src')
ART = os.path.join(ROOT, 'art')
os.makedirs(ART, exist_ok=True)

def key(path, t0=40, t1=110, hole_min=4000, dom0=50, protect_wings=False):
    im = Image.open(path).convert('RGB')
    a = np.asarray(im).astype(np.float32)
    bgc = np.array([0, 255, 0], np.float32)
    b = np.concatenate([
        a[:8].reshape(-1, 3), a[-8:].reshape(-1, 3),
        a[:, :8].reshape(-1, 3), a[:, -8:].reshape(-1, 3)
    ])
    med = np.median(b, 0)
    if np.linalg.norm(med - bgc) < 140:
        bgc = med
    d = np.sqrt(((a - bgc) ** 2).sum(-1))
    dom = a[..., 1] - np.maximum(a[..., 0], a[..., 2])
    score = np.maximum(np.clip((t1 - d) / (t1 - t0), 0, 1), np.clip((dom - dom0) / 55, 0, 1))
    alpha = 1 - score
    if protect_wings:
        # pale / white / translucent wing-like pixels: high luma, low saturation, not strongly green-dominant
        luma = 0.3 * a[..., 0] + 0.59 * a[..., 1] + 0.11 * a[..., 2]
        sat = a.max(-1) - a.min(-1)
        wing = (luma > 170) & (sat < 80) & (dom < 70)
        alpha = np.where(wing, np.maximum(alpha, 0.85), alpha)
    bgmask = alpha < 0.5
    lab, n = nd.label(bgmask)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    sizes = nd.sum(bgmask, lab, range(1, n + 1)) if n else []
    keepbg = np.zeros_like(bgmask)
    for i, s in enumerate(sizes, 1):
        if i in border or s > hole_min:
            keepbg |= (lab == i)
    alpha = np.where(keepbg, 0.0, np.maximum(alpha, 0.0))
    alpha = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7))).astype(np.float32) / 255
    rgb = a.copy()
    sp = np.clip(rgb[..., 1] - np.maximum(rgb[..., 0], rgb[..., 2]), 0, None) * (alpha < 0.97) * 0.95
    rgb[..., 1] -= sp
    edge = nd.binary_dilation(alpha < 0.5, iterations=3) & (alpha > 0.0)
    m = np.maximum(rgb[..., 0], rgb[..., 2])
    rgb[..., 1] = np.where(edge, np.minimum(rgb[..., 1], m), rgb[..., 1])
    # kill leftover near-transparent green
    rgb = np.where(alpha[..., None] < 0.04, 0, rgb)
    out = np.dstack([rgb, alpha * 255]).clip(0, 255).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')

def crop_pad(im, pad=8):
    a = im.getchannel('A')
    bb = a.point(lambda v: 255 if v > 12 else 0).getbbox()
    if not bb:
        return im
    l, t, r, b = bb
    l, t = max(0, l - pad), max(0, t - pad)
    r, b = min(im.width, r + pad), min(im.height, b + pad)
    return im.crop((l, t, r, b))

def split_by_gaps(im, axis='x', min_gap=12, min_size=20, alpha_thr=12):
    a = np.asarray(im.getchannel('A'))
    occ = (a > alpha_thr).sum(axis=0 if axis == 'x' else 1) > 2
    ranges = []
    i = 0
    n = len(occ)
    while i < n:
        if occ[i]:
            j = i
            while j < n and occ[j]:
                j += 1
            if j - i >= min_size:
                ranges.append((i, j))
            i = j
        else:
            i += 1
    # merge ranges separated by tiny gaps
    merged = []
    for r in ranges:
        if merged and r[0] - merged[-1][1] < min_gap // 2:
            merged[-1] = (merged[-1][0], r[1])
        else:
            merged.append(r)
    return merged

def slice_row(im, names, folder, min_gap=18):
    ranges = split_by_gaps(im, 'x', min_gap=min_gap)
    print('  columns', len(ranges), 'expected', len(names), ranges)
    out = []
    for (a, b), name in zip(ranges, names):
        piece = crop_pad(im.crop((a, 0, b, im.height)))
        path = os.path.join(folder, name + '.png')
        piece.save(path, optimize=True)
        print(' ', path, piece.size)
        out.append((name, piece, path))
    return out

def slice_grid(im, row_names, col_names, folder):
    rows = split_by_gaps(im, 'y', min_gap=10, min_size=30)
    print('  rows', len(rows), 'expected', len(row_names), rows)
    out = []
    for (y0, y1), rname in zip(rows, row_names):
        band = im.crop((0, y0, im.width, y1))
        cols = split_by_gaps(band, 'x', min_gap=10, min_size=20)
        print('   ', rname, 'cols', len(cols), 'expected', len(col_names))
        for (x0, x1), cname in zip(cols, col_names):
            piece = crop_pad(band.crop((x0, 0, x1, band.height)))
            name = f'{cname}_{rname}'
            path = os.path.join(folder, name + '.png')
            piece.save(path, optimize=True)
            print('  ', path, piece.size)
            out.append((name, piece, path))
    return out

def main():
    # --- knight ---
    kn = key(os.path.join(SRC, 'knight_poses_raw.jpg'), t0=35, t1=100, dom0=45)
    kn.save(os.path.join(ART, 'knight_poses.png'), optimize=True)
    print('knight sheet', kn.size)
    slice_row(kn, ['knight_idle', 'knight_run', 'knight_slash', 'knight_spin'], ART)

    # --- bugs ---
    bg = key(os.path.join(SRC, 'bugs_raw.jpg'), t0=35, t1=100, dom0=45, protect_wings=True)
    bg.save(os.path.join(ART, 'bugs.png'), optimize=True)
    print('bugs sheet', bg.size)
    slice_row(bg, ['ant', 'beetle', 'wasp', 'boss'], ART, min_gap=16)

    # --- foods original ---
    fd = key(os.path.join(SRC, 'foods_raw.jpg'), t0=35, t1=100, dom0=45)
    fd.save(os.path.join(ART, 'foods.png'), optimize=True)
    print('foods sheet', fd.size)
    slice_grid(fd, ['intact', 'bitten'], ['basket', 'sandwich', 'watermelon', 'pie', 'cookies', 'lemonade'], ART)

    # --- bite fixes (replace weak bitten versions) ---
    fx = key(os.path.join(SRC, 'foods_bites_fix_raw.jpg'), t0=35, t1=100, dom0=45)
    fx.save(os.path.join(ART, 'foods_bites_fix.png'), optimize=True)
    print('foods fix sheet', fx.size)
    slice_row(fx, ['basket_bitten', 'watermelon_bitten', 'cookies_bitten'], ART, min_gap=16)

    # --- logo ---
    lg = key(os.path.join(SRC, 'logo_raw.jpg'), t0=35, t1=100, dom0=45)
    lg = crop_pad(lg, pad=12)
    lg.save(os.path.join(ART, 'logo.png'), optimize=True)
    print('logo', lg.size)

    # --- blanket: copy, and extract a grass patch + blanket-only crop ---
    bl = Image.open(os.path.join(SRC, 'blanket_grass_raw.jpg')).convert('RGB')
    bl.save(os.path.join(ART, 'blanket_grass.jpg'), quality=90, optimize=True)
    # rough blanket crop: the checkered area is inset; sample to find red/cream vs green grass
    arr = np.asarray(bl).astype(np.float32)
    # grass: green-dominant; blanket: red or cream (low green dominance, higher red or luma)
    gdom = arr[..., 1] - np.maximum(arr[..., 0], arr[..., 2])
    mask = gdom < 18  # blanket-ish
    # erode a bit to stay inside hem
    mask = nd.binary_erosion(mask, iterations=6)
    ys, xs = np.where(mask)
    if len(xs):
        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        blanket = bl.crop((x0, y0, x1, y1))
        blanket.save(os.path.join(ART, 'blanket.jpg'), quality=90, optimize=True)
        print('blanket crop', blanket.size, (x0, y0, x1, y1))
    # grass strips from the borders
    h, w = arr.shape[:2]
    strips = [
        bl.crop((0, 0, w, max(8, int((ys.min() if len(xs) else 80) * 0.9)))),
    ]
    # take top grass band and make a tile
    top = bl.crop((0, 0, w, 180))
    top.save(os.path.join(ART, 'grass_band.jpg'), quality=90, optimize=True)
    # make a larger grass field by mirroring the four edge bands
    band = 160
    topb = np.asarray(bl.crop((0, 0, w, band)))
    botb = np.asarray(bl.crop((0, h - band, w, h)))
    leftb = np.asarray(bl.crop((0, 0, band, h)))
    rightb = np.asarray(bl.crop((w - band, 0, w, h)))
    # 2048 field
    field = np.zeros((2048, 2048, 3), np.uint8)
    # fill with repeated flipped top band
    tile = np.concatenate([topb, topb[::-1]], axis=0)  # 320 x w
    for y in range(0, 2048, tile.shape[0]):
        for x in range(0, 2048, tile.shape[1]):
            yy, xx = min(tile.shape[0], 2048 - y), min(tile.shape[1], 2048 - x)
            field[y:y+yy, x:x+xx] = tile[:yy, :xx]
    Image.fromarray(field).save(os.path.join(ART, 'grass_field.jpg'), quality=88, optimize=True)
    print('grass_field', field.shape)

if __name__ == '__main__':
    main()
