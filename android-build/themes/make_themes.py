#!/usr/bin/env python3
"""Generate the extra screen-background themes (BG2.png ...) from the game's
own graphics, so no outside artwork is needed and the art is reproducible,
and soften the fork's own two (BG.png, BG1.png) so buttons read over them.

Run from the pokeemerald-multiplatform root:  python3 make_themes.py [outdir]

Only the bands either side of the game screen are ever visible -- about 8% of
the width each side on a 16:9 phone, 16% on 20:9 -- and the Android overlay
cover-scales the 16:9 image (cropping top/bottom on taller phones). So every
theme keeps its subject in those side bands and its vertical middle.
"""
import math, random, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps, PngImagePlugin

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


class Layer:
    """Translucent drawing that actually blends. ImageDraw on an RGBA image
    writes pixels through, alpha and all -- so a 7%-white line became a solid
    white stripe once saved as RGB. Draw on a clear overlay instead, then
    composite it over the image."""
    def __init__(self, img):
        self.img = img
        self.ov = Image.new('RGBA', img.size, (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.ov)

    def __enter__(self):
        return self.d

    def __exit__(self, *exc):
        self.img.alpha_composite(self.ov)


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
    r = random.Random(seed)
    with Layer(img) as d:
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


# ---- the themes ----------------------------------------------------------
#
# Everything in the side bands sits behind a button, so the bands must stay
# calm: ThemeCheck (android-build/controls-tests) fails a theme whose
# background luminance varies by more than a set amount under any control.
# Scenes are carried by colour and soft light; Pokemon appear as large faint
# watermarks tinted into the palette, never as full-contrast sprites.

def watermark(img, name, scale, pos, tint, alpha=0.22, flip=False, frame=0):
    """A sprite as a soft, single-hue silhouette: luminance mapped onto the
    theme's tint, faded and slightly blurred so its edges never read as a
    hard line behind a button."""
    spr = sprite(name, scale, frame)
    if flip:
        spr = spr.transpose(Image.FLIP_LEFT_RIGHT)
    lum = spr.convert('L')
    col = ImageOps.colorize(lum, black=tuple(max(0, c - 40) for c in tint),
                            white=tuple(min(255, c + 60) for c in tint)).convert('RGBA')
    a = spr.getchannel('A').point(lambda v: int(v * alpha))
    col.putalpha(a)
    col = col.filter(ImageFilter.GaussianBlur(scale * 0.6))
    img.alpha_composite(col, pos)


def glow(img, cx, cy, r, colour, strength):
    """A soft radial light, no edge."""
    with Layer(img) as d:
        steps = 40
        for i in range(steps, 0, -1):
            rr = r * i / steps
            a = int(strength * (1 - i / steps) ** 1.6 * 255 / steps * 3)
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=colour + (min(255, a),))


def soft_band(img, y0, y1, top, bottom):
    """A horizon that fades over its height rather than a hard line."""
    band = gradient(top, bottom, y1 - y0).convert('RGBA')
    mask = Image.linear_gradient('L').resize((W, y1 - y0)).point(lambda v: min(255, v * 2))
    band.putalpha(mask)
    img.alpha_composite(band, (0, y0))


def rayquaza_sky():
    img = gradient((20, 70, 78), (40, 110, 104)).convert('RGBA')
    stars(img, 60, 1, (0, 0, W, 260), (200, 240, 230))
    glow(img, W // 2, 420, 700, (90, 170, 150), 0.6)
    watermark(img, 'rayquaza', 6, (-90, 120), (60, 150, 120))
    watermark(img, 'rayquaza', 6, (W - 300, 100), (60, 150, 120), flip=True)
    return img


def hoenn_sunset():
    img = gradient((222, 128, 104), (112, 72, 132)).convert('RGBA')
    soft_band(img, 470, H, (70, 80, 140), (40, 50, 100))
    glow(img, 130, 470, 260, (255, 200, 140), 0.5)
    glow(img, W - 130, 470, 260, (255, 200, 140), 0.5)
    watermark(img, 'kyogre', 5, (-50, 430), (60, 80, 150))
    watermark(img, 'wailord', 5, (W - 300, 430), (60, 80, 150), flip=True)
    return img


def magma():
    img = gradient((52, 14, 12), (112, 34, 16)).convert('RGBA')
    glow(img, 150, H, 520, (255, 110, 40), 0.45)
    glow(img, W - 150, H, 520, (255, 110, 40), 0.45)
    r = random.Random(5)
    with Layer(img) as d:                 # a few faint embers, high up
        for _ in range(40):
            x = r.randrange(0, W); y = r.randrange(0, 260); s = r.randrange(2, 5)
            d.ellipse([x, y, x + s, y + s], fill=(255, 170, 80, r.randrange(50, 110)))
    watermark(img, 'groudon', 6, (-110, 300), (150, 50, 30))
    watermark(img, 'groudon', 6, (W - 280, 300), (150, 50, 30), flip=True)
    return img


def starter_meadow():
    img = gradient((122, 178, 214), (150, 196, 170)).convert('RGBA')
    soft_band(img, 520, H, (110, 168, 112), (86, 140, 92))
    glow(img, W // 2, 160, 600, (255, 250, 220), 0.35)
    watermark(img, 'treecko', 4, (0, 380), (60, 120, 70), alpha=0.26)
    watermark(img, 'torchic', 4, (W - 260, 300), (60, 120, 70), alpha=0.26, flip=True)
    watermark(img, 'mudkip', 4, (W - 280, 560), (60, 120, 70), alpha=0.26, flip=True)
    return img


def eon_night():
    img = gradient((14, 16, 46), (34, 28, 76)).convert('RGBA')
    stars(img, 140, 8, (0, 0, W, H), (190, 200, 255))
    glow(img, 150, 150, 220, (230, 230, 255), 0.35)
    watermark(img, 'latias', 5, (-40, 300), (120, 90, 170))
    watermark(img, 'latios', 5, (W - 290, 280), (90, 110, 190), flip=True)
    return img


def gba_indigo():
    img = gradient((70, 58, 150), (48, 38, 110)).convert('RGBA')
    # Faint moulded-plastic texture. (No speaker grille: wherever it goes in
    # the side bands, the on-screen A/B or D-pad sits on top of it.)
    with Layer(img) as d:
        for y in range(0, H, 6):
            d.line([(0, y), (W, y)], fill=(255, 255, 255, 7))
    return img


def classic_green():
    pal = [(15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)]
    img = Image.new('RGBA', (W, H), pal[2] + (255,))
    # A faint version of the handheld's dot grid, not a loud checkerboard.
    with Layer(img) as d:
        for y in range(0, H, 12):
            for x in range(0, W, 12):
                d.rectangle([x, y, x + 1, y + 1], fill=pal[1] + (40,))
    watermark(img, 'treecko', 5, (-40, 330), (60, 100, 20), alpha=0.25)
    watermark(img, 'mudkip', 5, (W - 290, 330), (60, 100, 20), alpha=0.25, flip=True)
    return img


def soften_original(path):
    """The fork's own two backgrounds (BG.png, BG1.png) are busy painted art
    with a bright moon and characters exactly where the buttons sit. Keep the
    painting but soften it: fine detail pulled toward a broad blur, highlights
    rolled off, a little darker. Marked in the PNG so a rerun doesn't soften
    it twice."""
    if not path.exists():
        return
    im = Image.open(path)
    if im.info.get('softened') == '1':
        return
    im = im.convert('RGB')
    fine = im.filter(ImageFilter.GaussianBlur(3))
    broad = im.filter(ImageFilter.GaussianBlur(45))
    out = Image.blend(fine, broad, 0.65)
    out = out.point(lambda v: v if v < 150 else int(150 + (v - 150) * 0.35))
    out = ImageEnhance.Brightness(out).enhance(0.85)
    meta = PngImagePlugin.PngInfo()
    meta.add_text('softened', '1')
    out.save(path, optimize=True, pnginfo=meta)
    print(f'{path.name}  softened')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ('BG.png', 'BG1.png'):
        soften_original(OUT / name)
    for i, name in enumerate(ORDER):
        img = globals()[name]()
        img.convert('RGB').save(OUT / f'BG{i + 2}.png', optimize=True)
        print(f'BG{i + 2}.png  {name}')


if __name__ == '__main__':
    main()
