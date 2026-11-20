#!/usr/bin/env python3
"""Polished art-preview lineup sheet."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path

ART = Path('/workspace/picnic-knight/art')
OUT = Path('/workspace/picnic-knight/preview')
OUT.mkdir(exist_ok=True)

def font(size, bold=False):
    candidates = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def fit(im, max_w, max_h):
    im = im.convert('RGBA')
    s = min(max_w / im.width, max_h / im.height)
    return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)

def shadow_paste(dst, spr, xy, blur=10, opac=70):
    x, y = xy
    sh = Image.new('RGBA', (spr.width + blur * 4, spr.height + blur * 4), (0, 0, 0, 0))
    blob = Image.new('L', spr.size, 0)
    blob.paste(spr.getchannel('A'), (0, 0))
    blob = Image.new('RGBA', spr.size, (40, 25, 10, opac))
    blob.putalpha(spr.getchannel('A').point(lambda v: int(v * opac / 255)))
    sh.paste(blob, (blur * 2, blur * 2), blob)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    dst.alpha_composite(sh, (x - blur * 2, y - blur * 2 + 4))
    dst.alpha_composite(spr, (x, y))

def main():
    W, H = 1920, 1180
    # warm parchment + soft vignette over a blurred picnic ground
    ground = Image.open(ART / 'picnic_ground.jpg').convert('RGB').resize((W, H), Image.LANCZOS)
    ground = ground.filter(ImageFilter.GaussianBlur(8))
    # fade toward cream so sprites pop
    cream = Image.new('RGB', (W, H), (255, 244, 214))
    bg = Image.blend(ground, cream, 0.55)
    # top banner wash
    canvas = bg.convert('RGBA')
    wash = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(wash)
    for i in range(220):
        a = int(120 * (1 - i / 220))
        dr.rectangle((0, i, W, i + 1), fill=(255, 246, 220, a))
    canvas.alpha_composite(wash)

    draw = ImageDraw.Draw(canvas)
    logo = fit(Image.open(ART / 'logo.png'), 620, 260)
    shadow_paste(canvas, logo, ((W - logo.width) // 2, 18), blur=12, opac=50)

    # section helper
    def row(title, items, y, box_w, box_h, gap=18):
        f = font(28, True)
        # measure title
        bbox = draw.textbbox((0, 0), title, font=f)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, y), title, font=f, fill=(62, 36, 16, 230))
        total = len(items) * box_w + (len(items) - 1) * gap
        x0 = (W - total) // 2
        yy = y + 44
        label_f = font(20, True)
        for i, (label, path) in enumerate(items):
            x = x0 + i * (box_w + gap)
            # card
            card = Image.new('RGBA', (box_w, box_h), (255, 250, 236, 210))
            # rounded-ish by pasting on a mask
            mask = Image.new('L', (box_w, box_h), 0)
            md = ImageDraw.Draw(mask)
            md.rounded_rectangle((0, 0, box_w - 1, box_h - 1), radius=22, fill=255)
            card.putalpha(mask.point(lambda v: int(v * 210 / 255)))
            canvas.alpha_composite(card, (x, yy))
            spr = fit(Image.open(path), box_w - 36, box_h - 58)
            px = x + (box_w - spr.width) // 2
            py = yy + 12 + (box_h - 52 - spr.height) // 2
            shadow_paste(canvas, spr, (px, py), blur=8, opac=55)
            lb = draw.textbbox((0, 0), label, font=label_f)
            lw = lb[2] - lb[0]
            draw.text((x + (box_w - lw) // 2, yy + box_h - 32), label, font=label_f, fill=(62, 36, 16, 230))

    row('The Knight', [
        ('Idle', ART / 'knight_idle.png'),
        ('Run', ART / 'knight_run.png'),
        ('Slash', ART / 'knight_slash.png'),
        ('Spin', ART / 'knight_spin.png'),
    ], 280, 280, 300, gap=28)

    row('The Bugs', [
        ('Marching ant', ART / 'ant.png'),
        ('Beetle', ART / 'beetle.png'),
        ('Wasp', ART / 'wasp.png'),
        ('Ant captain (boss)', ART / 'boss.png'),
    ], 640, 280, 280, gap=28)

    # foods two groups side by side? or two rows
    row('Picnic food — intact', [
        ('Basket', ART / 'basket_intact.png'),
        ('Sandwich', ART / 'sandwich_intact.png'),
        ('Watermelon', ART / 'watermelon_intact.png'),
        ('Pie', ART / 'pie_intact.png'),
        ('Cookies', ART / 'cookies_intact.png'),
        ('Lemonade', ART / 'lemonade_intact.png'),
    ], 980, 180, 200, gap=16)

    # bitten row would make the page too tall at 1180... 980+200=1180 exactly, overflow.
    # Make the canvas taller for bitten row.
    # I'll extend after the fact if needed — actually H=1180 is tight. Bump design:
    # I'll rebuild with H=1480 including bitten foods, or make a tighter layout.

if __name__ == '__main__':
    main()
