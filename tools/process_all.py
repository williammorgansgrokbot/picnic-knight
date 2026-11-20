#!/usr/bin/env python3
"""Key, slice, composite lawn, and refresh preview lineup."""
import os, shutil
import numpy as np
from PIL import Image, ImageFilter, ImageDraw, ImageFont
import scipy.ndimage as nd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'art_src')
ART = os.path.join(ROOT, 'art')
PREV = os.path.join(ROOT, 'preview')
os.makedirs(ART, exist_ok=True)
os.makedirs(PREV, exist_ok=True)

def key(path, t0=35, t1=100, dom0=45, protect_wings=False, hole_min=4000):
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
    rgb = np.where(alpha[..., None] < 0.04, 0, rgb)
    return Image.fromarray(np.dstack([rgb, alpha * 255]).clip(0, 255).astype(np.uint8), 'RGBA')

def despill_trails(im, g_over=6):
    a = np.asarray(im).copy()
    rgb = a[..., :3].astype(np.float32)
    al = a[..., 3]
    gish = (al > 16) & (rgb[..., 1] > rgb[..., 0] + g_over) & (rgb[..., 1] > rgb[..., 2] + g_over)
    target = np.maximum(rgb[..., 0], rgb[..., 2])
    rgb[..., 1] = np.where(gish, target, rgb[..., 1])
    a[..., :3] = rgb.clip(0, 255).astype(np.uint8)
    return Image.fromarray(a, 'RGBA')

def crop_pad(im, pad=6):
    bb = im.getchannel('A').point(lambda v: 255 if v > 12 else 0).getbbox()
    if not bb:
        return im
    l, t, r, b = bb
    return im.crop((max(0, l - pad), max(0, t - pad), min(im.width, r + pad), min(im.height, b + pad)))

def drop_tiny(im, min_size=40):
    a = np.asarray(im).copy()
    mask = a[..., 3] > 16
    lab, n = nd.label(mask)
    if n <= 1:
        return im
    sizes = nd.sum(mask, lab, range(1, n + 1))
    main = 1 + int(np.argmax(sizes))
    for i, s in enumerate(sizes, 1):
        if i != main and s < min_size:
            a[..., 3] = np.where(lab == i, 0, a[..., 3])
    return Image.fromarray(a)

def split_n(im, n, names, dest, min_alpha=24, despill=False):
    if despill:
        im = despill_trails(im)
    occ = (np.asarray(im.getchannel('A')) > min_alpha).sum(0).astype(np.float32)
    k = 9
    sm = np.convolve(occ, np.ones(k) / k, mode='same')
    xs = np.where(sm > 8)[0]
    x0, x1 = int(xs[0]), int(xs[-1])
    width = x1 - x0
    cuts = []
    for i in range(1, n):
        c = x0 + int(width * i / n)
        w = int(width / (2 * n)) + 30
        lo, hi = max(x0 + 20, c - w), min(x1 - 20, c + w)
        cuts.append(lo + int(np.argmin(sm[lo:hi])))
    bounds = [0] + cuts + [im.width]
    out = []
    for (a, b), name in zip(zip(bounds[:-1], bounds[1:]), names):
        piece = crop_pad(drop_tiny(im.crop((a, 0, b, im.height))))
        path = os.path.join(dest, name + '.png')
        piece.save(path, optimize=True)
        print(' ', name, piece.size)
        out.append(path)
    return out

def key_single(src_name, out_name, protect_wings=False, despill=False):
    im = key(os.path.join(SRC, src_name), protect_wings=protect_wings)
    if despill:
        im = despill_trails(im)
    im = crop_pad(drop_tiny(im))
    path = os.path.join(ART, out_name)
    im.save(path, optimize=True)
    print('single', out_name, im.size)
    return im

def composite_lawn():
    picnic = Image.open(os.path.join(ART, 'picnic_ground.jpg')).convert('RGB')
    # prefer already-copied picnic; source fallback
    if os.path.exists(os.path.join(SRC, 'blanket_grass_raw.jpg')):
        picnic = Image.open(os.path.join(SRC, 'blanket_grass_raw.jpg')).convert('RGB')
        picnic.save(os.path.join(ART, 'picnic_ground.jpg'), quality=92, optimize=True)
    surround = Image.open(os.path.join(SRC, 'grass_surround_raw.jpg')).convert('RGB')
    # color-match surround to picnic grass border
    pa = np.asarray(picnic).astype(np.float32)
    sa = np.asarray(surround).astype(np.float32)
    gdom = pa[..., 1] - np.maximum(pa[..., 0], pa[..., 2])
    grass = gdom > 12
    # keep only a border band (not the inner blanket)
    h, w = grass.shape
    yy, xx = np.mgrid[0:h, 0:w]
    # blanket-like region from earlier analysis ~ rows 164-889, cols 98-939 on 1024
    # scale if size differs
    sy, sx = h / 1024, w / 1024
    inner = (yy > 164 * sy) & (yy < 889 * sy) & (xx > 98 * sx) & (xx < 939 * sx)
    border = grass & ~inner
    if border.sum() < 1000:
        border = grass
    pmean = pa[border].mean(0)
    smean = sa.mean(axis=(0, 1))
    scale = np.where(smean < 1, 1, pmean / np.maximum(smean, 1))
    # gentle match
    scale = 0.65 * scale + 0.35
    sa2 = (sa * scale).clip(0, 255).astype(np.uint8)
    surround = Image.fromarray(sa2)
    # 2048 canvas
    S = 2048
    # fill base by covering 2048 with surround (scaled up, slightly)
    base = surround.resize((S, S), Image.LANCZOS)
    # picnic in the center, 1200 px so the grass border of the photo is visible
    side = 1200
    pic = picnic.resize((side, side), Image.LANCZOS)
    x0 = (S - side) // 2
    y0 = (S - side) // 2
    # feathered mask: opaque in the inner area, fade across the photo's grass border
    mask = Image.new('L', (side, side), 0)
    m = np.zeros((side, side), np.float32)
    # fade starts near the blanket hem and finishes at the photo edge
    cy, cx = np.mgrid[0:side, 0:side]
    # normalized distance from center, box distance
    dx = np.maximum(0, np.abs(cx - side / 2) - side * 0.32)
    dy = np.maximum(0, np.abs(cy - side / 2) - side * 0.32)
    d = np.maximum(dx, dy)
    fade = 1 - np.clip(d / (side * 0.16), 0, 1)
    # smoother
    fade = fade * fade * (3 - 2 * fade)
    mask = Image.fromarray((fade * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(8))
    canvas = base.copy()
    canvas.paste(pic, (x0, y0), mask)
    out = os.path.join(ART, 'picnic_ground_wide.jpg')
    canvas.save(out, quality=90, optimize=True)
    print('lawn composite', canvas.size, out)
    # also a closer crop used if needed
    return canvas

def font(size, bold=False):
    p = ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold
         else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    return ImageFont.truetype(p, size)

def fit(im, max_w, max_h):
    im = im.convert('RGBA')
    s = min(max_w / im.width, max_h / im.height)
    return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)

def shadow_paste(dst, spr, xy, blur=8, opac=55):
    x, y = xy
    blob = Image.new('RGBA', spr.size, (40, 25, 10, opac))
    blob.putalpha(spr.getchannel('A').point(lambda v: int(v * opac / 255)))
    pad = blur * 3
    sh = Image.new('RGBA', (spr.width + pad * 2, spr.height + pad * 2), (0, 0, 0, 0))
    sh.paste(blob, (pad, pad), blob)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    dst.alpha_composite(sh, (x - pad, y - pad + 5))
    dst.alpha_composite(spr, (x, y))

def make_lineup():
    W, H = 1920, 1680
    ground = Image.open(os.path.join(ART, 'picnic_ground.jpg')).convert('RGB').resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(10))
    cream = Image.new('RGB', (W, H), (255, 244, 214))
    canvas = Image.blend(ground, cream, 0.58).convert('RGBA')
    wash = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    drw = ImageDraw.Draw(wash)
    for i in range(280):
        a = int(140 * (1 - i / 280))
        drw.rectangle((0, i, W, i + 1), fill=(255, 246, 220, a))
    canvas.alpha_composite(wash)
    draw = ImageDraw.Draw(canvas)
    logo = fit(Image.open(os.path.join(ART, 'logo.png')), 640, 260)
    shadow_paste(canvas, logo, ((W - logo.width) // 2, 20), blur=12, opac=50)
    sf = font(22, False)
    sub = "Art preview  ·  classic silver knight  ·  original storybook cartoon"
    bb = draw.textbbox((0, 0), sub, font=sf)
    draw.text(((W - (bb[2] - bb[0])) // 2, 20 + logo.height + 4), sub, font=sf, fill=(90, 55, 28, 220))

    def row(title, items, y, box_w, box_h, gap=18):
        f = font(28, True)
        bbox = draw.textbbox((0, 0), title, font=f)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, y), title, font=f, fill=(62, 36, 16, 230))
        total = len(items) * box_w + (len(items) - 1) * gap
        x0 = (W - total) // 2
        yy = y + 46
        label_f = font(20, True)
        for i, (label, path) in enumerate(items):
            x = x0 + i * (box_w + gap)
            card = Image.new('RGBA', (box_w, box_h), (0, 0, 0, 0))
            ImageDraw.Draw(card).rounded_rectangle((0, 0, box_w - 1, box_h - 1), radius=22, fill=(255, 250, 236, 215))
            canvas.alpha_composite(card, (x, yy))
            spr = fit(Image.open(path), box_w - 36, box_h - 58)
            px = x + (box_w - spr.width) // 2
            py = yy + 12 + (box_h - 52 - spr.height) // 2
            shadow_paste(canvas, spr, (px, py), blur=8, opac=55)
            lb = draw.textbbox((0, 0), label, font=label_f)
            lw = lb[2] - lb[0]
            draw.text((x + (box_w - lw) // 2, yy + box_h - 34), label, font=label_f, fill=(62, 36, 16, 230))

    A = ART
    row('The Knight', [
        ('Idle', f'{A}/knight_idle.png'),
        ('Run', f'{A}/knight_run.png'),
        ('Slash', f'{A}/knight_slash.png'),
        ('Spin', f'{A}/knight_spin.png'),
    ], 360, 300, 320, gap=28)
    row('The Bugs', [
        ('Marching ant', f'{A}/ant.png'),
        ('Beetle', f'{A}/beetle.png'),
        ('Wasp', f'{A}/wasp.png'),
        ('Ant captain (boss)', f'{A}/boss.png'),
    ], 750, 300, 300, gap=28)
    row('Picnic food — intact', [
        ('Basket', f'{A}/basket_intact.png'),
        ('Sandwich', f'{A}/sandwich_intact.png'),
        ('Watermelon', f'{A}/watermelon_intact.png'),
        ('Pie', f'{A}/pie_intact.png'),
        ('Cookies', f'{A}/cookies_intact.png'),
        ('Lemonade', f'{A}/lemonade_intact.png'),
    ], 1110, 190, 210, gap=16)
    row('Picnic food — bite stages', [
        ('Rummaged basket', f'{A}/basket_bitten.png'),
        ('Bitten sandwich', f'{A}/sandwich_bitten.png'),
        ('Bitten watermelon', f'{A}/watermelon_bitten.png'),
        ('Pie, slice gone', f'{A}/pie_bitten.png'),
        ('Bitten cookies', f'{A}/cookies_bitten.png'),
        ('Spilled lemonade', f'{A}/lemonade_bitten.png'),
    ], 1380, 190, 220, gap=16)
    ff = font(16, False)
    foot = "Picnic Knight  ·  painted sprites, original IP  ·  not published yet"
    bb = draw.textbbox((0, 0), foot, font=ff)
    draw.text(((W - (bb[2] - bb[0])) // 2, 1644), foot, font=ff, fill=(90, 55, 28, 180))
    path = os.path.join(PREV, 'lineup.png')
    canvas.convert('RGB').save(path, quality=95, optimize=True)
    print('lineup', path)

def main():
    # singles
    key_single('ant_painterly_raw.jpg', 'ant.png')
    key_single('beetle_painterly_raw.jpg', 'beetle.png')
    key_single('wasp_painterly_raw.jpg', 'wasp.png', protect_wings=True)
    key_single('boss_painterly_raw.jpg', 'boss.png')
    key_single('basket_rummaged_raw.jpg', 'basket_bitten.png')

    # keep a copy of the hero idle from the original approved sheet if present
    # animation sheets
    knr = despill_trails(key(os.path.join(SRC, 'knight_run_sheet_raw.jpg')))
    knr.save(os.path.join(ART, 'knight_run_sheet.png'), optimize=True)
    split_n(knr, 4, ['knight_run_0', 'knight_run_1', 'knight_run_2', 'knight_run_3'], ART, despill=False)

    kns = despill_trails(key(os.path.join(SRC, 'knight_slash_sheet_raw.jpg')))
    kns.save(os.path.join(ART, 'knight_slash_sheet.png'), optimize=True)
    split_n(kns, 3, ['knight_slash_0', 'knight_slash_1', 'knight_slash_2'], ART)

    knp = despill_trails(key(os.path.join(SRC, 'knight_spin_sheet_raw.jpg')))
    knp.save(os.path.join(ART, 'knight_spin_sheet.png'), optimize=True)
    split_n(knp, 3, ['knight_spin_0', 'knight_spin_1', 'knight_spin_2'], ART)

    kni = key(os.path.join(SRC, 'knight_idle_sheet_raw.jpg'))
    kni.save(os.path.join(ART, 'knight_idle_sheet.png'), optimize=True)
    split_n(kni, 3, ['knight_idle_0', 'knight_idle_1', 'knight_idle_2'], ART)

    ant = key(os.path.join(SRC, 'ant_anim_sheet_raw.jpg'))
    ant.save(os.path.join(ART, 'ant_anim_sheet.png'), optimize=True)
    split_n(ant, 6, ['ant_walk_0', 'ant_walk_1', 'ant_walk_2', 'ant_walk_3', 'ant_nibble', 'ant_bonk'], ART)

    # Use the best idle from the new sheet as the standup portrait, keep slash/spin heroes
    # Prefer idle_0 as knight_idle (or keep original if we want). New idle is consistent with anims.
    shutil.copy(os.path.join(ART, 'knight_idle_0.png'), os.path.join(ART, 'knight_idle.png'))
    # run: skip standing frame 0; use 1 as the poster run (frame 2 is a lunge). We'll pick in game.
    shutil.copy(os.path.join(ART, 'knight_run_1.png'), os.path.join(ART, 'knight_run.png'))
    shutil.copy(os.path.join(ART, 'knight_slash_1.png'), os.path.join(ART, 'knight_slash.png'))
    shutil.copy(os.path.join(ART, 'knight_spin_1.png'), os.path.join(ART, 'knight_spin.png'))

    composite_lawn()
    make_lineup()

if __name__ == '__main__':
    main()
