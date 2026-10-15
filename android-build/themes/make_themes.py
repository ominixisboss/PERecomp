#!/usr/bin/env python3
"""Generate the extra screen-background themes (BG2.png ...) from the game's
own graphics, so no outside artwork is needed and the art is reproducible.

Run from the pokeemerald-multiplatform root:  python3 make_themes.py [outdir]

Only the bands either side of the game screen are ever visible -- about 8% of
the width each side on a 16:9 phone, 16% on 20:9 -- and the Android overlay
cover-scales the 16:9 image (cropping top/bottom on taller phones). So every
theme keeps its subject in those side bands and its vertical middle.
"""
import math, random, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

W, H = 1600, 900
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else '.')

# Theme order is the in-game BACKGROUND number minus 2 (BG.png and BG1.png
# are the fork's own art). Keep in sync with Themes.java.
ORDER = ['rayquaza_sky', 'hoenn_sunset', 'magma', 'starter_meadow',
         'eon_night', 'gba_indigo', 'classic_green']


def sprite(name, scale, frame=0):
    """A front sprite with index 0 transparent, nearest-neighbour scaled."""
    im = Image.open(f'graphics/pokemon/{name}/front.png')
    im = im.crop((0, 64 * frame, 64, 64 * frame + 64))
    rgba = im.convert('RGBA')
    px = rgba.load(); idx = im.load()
    for y in range(64):
        for x in range(64):
            if idx[x, y] == 0:
                px[x, y] = (0, 0, 0, 0)
    return rgba.resize((64 * scale, 64 * scale), Image.NEAREST)


def gradient(top, bottom, h=H):
    g = Image.new('RGB', (W, h))
    d = ImageDraw.Draw(g)
    for y in range(h):
        t = y / (h - 1)
        d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return g


def shadow(img, sprite_img, pos, alpha=90, blur=10):
    s = Image.new('RGBA', sprite_img.size, (0, 0, 0, 0))
    s.putalpha(sprite_img.getchannel('A').point(lambda a: alpha if a else 0))
    s = s.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(s, (pos[0] + 14, pos[1] + 18))


def place(img, spr, pos, drop=True):
    if drop:
        shadow(img, spr, pos)
    img.alpha_composite(spr, pos)


def stars(img, n, seed, box=(0, 0, W, H), color=(255, 255, 255)):
    r = random.Random(seed); d = ImageDraw.Draw(img)
    for _ in range(n):
        x = r.randrange(box[0], box[2]); y = r.randrange(box[1], box[3])
        s = r.choice([1, 1, 1, 2, 2, 3])
        a = r.randrange(120, 255)
        d.rectangle([x, y, x + s, y + s], fill=color + (a,))


def clouds_layer(img, y, scale, seed, alpha=200):
    """The title screen's cloud strip, recoloured by palette index: its PNG
    palette is not the one the game draws it with. 0 is transparent, 2 the
    cloud body, 12 its shading."""
    src = Image.open('graphics/title_screen/clouds.png')
    colours = {2: (255, 255, 255), 12: (196, 222, 240)}
    c = Image.new('RGBA', src.size, (0, 0, 0, 0))
    sp, cp = src.load(), c.load()
    for yy in range(src.height):
        for xx in range(src.width):
            if sp[xx, yy] in colours:
                cp[xx, yy] = colours[sp[xx, yy]] + (alpha,)
    c = c.resize((c.width * scale, c.height * scale), Image.NEAREST)
    r = random.Random(seed)
    x = -r.randrange(0, c.width)
    while x < W:
        img.alpha_composite(c, (x, y + r.randrange(-12, 12)))
        x += c.width - 8


def rayquaza_sky():
    img = gradient((18, 64, 70), (70, 160, 150)).convert('RGBA')
    stars(img, 140, 1, (0, 0, W, 300))
    clouds_layer(img, 540, 4, 2, 150)
    clouds_layer(img, 650, 6, 3, 220)
    place(img, sprite('rayquaza', 5), (-60, 170))
    place(img, sprite('rayquaza', 5).transpose(Image.FLIP_LEFT_RIGHT), (W - 260, 140))
    return img


def hoenn_sunset():
    img = gradient((255, 140, 90), (120, 60, 140), 520).convert('RGBA')
    sea = gradient((40, 90, 160), (10, 30, 80), H - 520).convert('RGBA')
    img = img.crop((0, 0, W, H)); img.alpha_composite(sea, (0, 520))
    d = ImageDraw.Draw(img)
    for x0 in (120, W - 120):   # a low sun on each side
        d.ellipse([x0 - 90, 380, x0 + 90, 560], fill=(255, 220, 140, 255))
    img.alpha_composite(sea, (0, 520))
    r = random.Random(4)
    for y in range(540, H, 22):    # glints
        for _ in range(10):
            x = r.randrange(0, W); w = r.randrange(20, 70)
            d.line([(x, y), (x + w, y)], fill=(255, 200, 150, r.randrange(60, 150)), width=3)
    place(img, sprite('kyogre', 4), (-20, 470))
    place(img, sprite('wailord', 4).transpose(Image.FLIP_LEFT_RIGHT), (W - 270, 470))
    return img


def magma():
    img = gradient((40, 8, 8), (150, 40, 10)).convert('RGBA')
    d = ImageDraw.Draw(img)
    r = random.Random(5)
    for _ in range(26):                # lava cracks
        x = r.randrange(0, W); y = r.randrange(600, H)
        pts = [(x, y)]
        for _ in range(6):
            x += r.randrange(-60, 60); y += r.randrange(-30, 30); pts.append((x, y))
        d.line(pts, fill=(255, 140, 30, 220), width=r.randrange(3, 7))
    for _ in range(90):                # embers
        x = r.randrange(0, W); y = r.randrange(0, H); s = r.randrange(2, 6)
        d.ellipse([x, y, x + s, y + s], fill=(255, r.randrange(120, 220), 40, r.randrange(120, 255)))
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    place(img, sprite('groudon', 5), (-70, 330))
    place(img, sprite('groudon', 5).transpose(Image.FLIP_LEFT_RIGHT), (W - 250, 330))
    return img


def starter_meadow():
    img = gradient((130, 200, 255), (200, 235, 255), 430).convert('RGBA')
    grass = gradient((120, 200, 90), (60, 140, 60), H - 430).convert('RGBA')
    img = img.crop((0, 0, W, H)); img.alpha_composite(grass, (0, 430))
    clouds_layer(img, 120, 4, 6, 230)
    d = ImageDraw.Draw(img); r = random.Random(7)
    for _ in range(900):               # grass tufts
        x = r.randrange(0, W); y = r.randrange(440, H)
        d.line([(x, y), (x + r.randrange(-4, 5), y - r.randrange(6, 16))],
               fill=(40, 120 + r.randrange(0, 60), 40, 255), width=2)
    place(img, sprite('treecko', 3), (10, 420))
    place(img, sprite('torchic', 3), (W - 210, 400))
    place(img, sprite('mudkip', 3).transpose(Image.FLIP_LEFT_RIGHT), (W - 230, 600))
    return img


def eon_night():
    img = gradient((8, 10, 40), (40, 30, 90)).convert('RGBA')
    stars(img, 420, 8)
    d = ImageDraw.Draw(img)
    d.ellipse([60, 60, 200, 200], fill=(250, 245, 220, 255))      # moon
    d.ellipse([95, 50, 235, 190], fill=(8, 10, 40, 0))
    place(img, sprite('latias', 4), (-10, 360))
    place(img, sprite('latios', 4).transpose(Image.FLIP_LEFT_RIGHT), (W - 260, 300))
    return img


def gba_indigo():
    img = gradient((70, 58, 150), (48, 38, 110)).convert('RGBA')
    d = ImageDraw.Draw(img)
    for x0 in (90, W - 210):           # speaker grilles
        for row in range(6):
            for col in range(6):
                cx = x0 + col * 22 + (row % 2) * 11; cy = 560 + row * 22
                d.ellipse([cx, cy, cx + 9, cy + 9], fill=(30, 22, 80, 255))
    for y in range(0, H, 6):           # faint plastic texture
        d.line([(0, y), (W, y)], fill=(255, 255, 255, 6))
    return img


def classic_green():
    pal = [(15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)]
    img = Image.new('RGBA', (W, H), pal[2] + (255,))
    d = ImageDraw.Draw(img)
    for y in range(0, H, 16):
        for x in range(0, W, 16):
            if (x // 16 + y // 16) % 2 == 0:
                d.rectangle([x, y, x + 15, y + 15], fill=pal[3] + (255,))
    for spr, pos in ((sprite('treecko', 4), (-10, 360)),
                     (sprite('mudkip', 4).transpose(Image.FLIP_LEFT_RIGHT), (W - 250, 360))):
        # Four-shade it like the original handheld, by luminance rank within
        # the sprite so a bright sprite does not vanish into the background.
        lum = spr.convert('L'); alpha = spr.getchannel('A')
        lp, ap = lum.load(), alpha.load()
        levels = sorted({lp[xx, yy] for yy in range(spr.height) for xx in range(spr.width) if ap[xx, yy]})
        shade = [pal[0], pal[1], pal[3]]
        mono = Image.new('RGBA', spr.size, (0, 0, 0, 0)); mp = mono.load()
        for yy in range(spr.height):
            for xx in range(spr.width):
                if ap[xx, yy]:
                    rank = levels.index(lp[xx, yy]) * 3 // max(1, len(levels))
                    mp[xx, yy] = shade[min(2, rank)] + (255,)
        img.alpha_composite(mono, pos)
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for i, name in enumerate(ORDER):
        img = globals()[name]()
        img.convert('RGB').save(OUT / f'BG{i + 2}.png', optimize=True)
        print(f'BG{i + 2}.png  {name}')


if __name__ == '__main__':
    main()
