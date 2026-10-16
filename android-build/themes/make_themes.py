#!/usr/bin/env python3
"""Generate the screen-background themes (BG2.png ...) from the game's own
graphics -- Pokemon sprites, the PC box wallpapers, the weather effects, the
title screen's clouds -- so no outside artwork is needed and the art is
reproducible. Also softens the fork's own two (BG.png, BG1.png) so buttons
read over them.

Run from the pokeemerald-multiplatform root:  python3 make_themes.py [outdir]

Only the bands either side of the game screen are ever visible -- about 200px
of this 1600px image each side on a 16:9 phone, 320px on 20:9 -- and the
Android overlay cover-scales the 16:9 image (cropping top/bottom on taller
phones). Everything in those bands sits behind a button, so they must stay
calm: ThemeCheck (android-build/controls-tests) fails a theme whose
background varies too much under any control, or whose labels stop reading.

The theme's index (BGn.png) is what the game stores, so existing themes keep
their numbers and new ones are only ever appended. themes-index.txt records
index -> id, and ThemeCheck checks Themes.java against it.
"""
import os, random, re, struct, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps, ImageStat, PngImagePlugin

W, H = 1600, 900
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
PX = 4       # one game pixel; ~6 screen pixels on a 1080p phone, like the game


# ---- sources -------------------------------------------------------------

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


def indexed(path, scale=1, colour=None, alpha=255):
    """An indexed PNG with index 0 transparent, optionally recoloured."""
    im = Image.open(path)
    rgba = im.convert('RGBA')
    px = rgba.load(); idx = im.load()
    for y in range(im.height):
        for x in range(im.width):
            if idx[x, y] == 0:
                px[x, y] = (0, 0, 0, 0)
            else:
                px[x, y] = (colour or px[x, y][:3]) + (alpha,)
    return rgba.resize((im.width * scale, im.height * scale), Image.NEAREST)


WDIR = 'graphics/pokemon_storage/wallpapers'


def wallpaper(name):
    """A PC box wallpaper's pattern area (inside the box frame), decoded the
    way the game builds it: tiles = frame tiles then pattern tiles (see
    graphics_file_rules.mk), a 20x18 tilemap, frame and pattern palettes."""
    mk = open('graphics_file_rules.mk').read()

    def ntiles(png):
        m = re.search(re.escape(f'$(WALLPAPERGFXDIR)/{png[:-4]}.4bpp') +
                      r': %\.4bpp: %\.png\n\t\$\(GFX\) \$< \$@ -num_tiles (\d+)', mk)
        im = Image.open(f'{WDIR}/{png}')
        return int(m.group(1)) if m else (im.width // 8) * (im.height // 8)

    def tiles(png, n):
        im = Image.open(f'{WDIR}/{png}'); tw = im.width // 8; px = im.load()
        return [[[px[(t % tw) * 8 + x, (t // tw) * 8 + y] & 15 for x in range(8)]
                 for y in range(8)] for t in range(n)]

    def pal(png):
        p = Image.open(f'{WDIR}/{png}').getpalette()[:48]
        return [tuple(p[i:i + 3]) for i in range(0, 48, 3)]

    m = re.search(re.escape(f'$(WALLPAPERGFXDIR)/{name}/tiles.4bpp: ') + r'(\S+) (\S+)', mk)
    frame, bg = (s.replace('$(WALLPAPERGFXDIR)/', '').replace('.4bpp', '.png') for s in m.groups())
    nf = ntiles(frame)
    bgim = Image.open(f'{WDIR}/{bg}')
    ts = tiles(frame, nf) + tiles(bg, (bgim.width // 8) * (bgim.height // 8))
    fpal, bpal = pal(frame), pal(bg)
    data = open(f'{WDIR}/{name}/tilemap.bin', 'rb').read()
    ents = struct.unpack('<%dH' % (len(data) // 2), data)
    wt = 20
    banks = sorted(set(e >> 12 for e in ents))
    img = Image.new('RGB', (wt * 8, len(ents) // wt * 8)); op = img.load()
    xs, ys = [], []
    for i, e in enumerate(ents):
        t, hf, vf, b = e & 0x3FF, e >> 10 & 1, e >> 11 & 1, e >> 12
        if t >= len(ts):
            continue
        if t >= nf:
            xs.append(i % wt); ys.append(i // wt)
        p = fpal if (b == banks[0] and len(banks) > 1) else bpal
        tile = ts[t]
        for y in range(8):
            for x in range(8):
                op[(i % wt) * 8 + x, (i // wt) * 8 + y] = p[tile[7 - y if vf else y][7 - x if hf else x]]
    return img.crop((min(xs) * 8, min(ys) * 8, (max(xs) + 1) * 8, (max(ys) + 1) * 8))


# ---- building blocks -----------------------------------------------------

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


def gradient(top, bottom, h=H, w=W):
    g = Image.new('RGB', (w, h))
    d = ImageDraw.Draw(g)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return g.convert('RGBA')


def side_gradient(left, right):
    """Left-to-right colour change, for scenes with two sides."""
    return gradient(left, right, h=W, w=H).rotate(90, expand=True).resize((W, H))


def stars(img, n, seed, box=(0, 0, W, H), color=(255, 255, 255), alpha=(120, 255)):
    r = random.Random(seed)
    with Layer(img) as d:
        for _ in range(n):
            x = r.randrange(box[0], box[2]); y = r.randrange(box[1], box[3])
            s = r.choice([1, 1, 1, 2, 2, 3])
            d.rectangle([x, y, x + s, y + s], fill=color + (r.randrange(*alpha),))


def glow(img, cx, cy, r, colour, strength):
    """A soft radial light, no edge."""
    with Layer(img) as d:
        steps = 40
        for i in range(steps, 0, -1):
            rr = r * i / steps
            a = int(strength * (1 - i / steps) ** 1.6 * 255 / steps * 3)
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=colour + (min(255, a),))


def soft_band(img, y0, y1, top, bottom):
    """A horizon that fades in over its height rather than a hard line."""
    band = gradient(top, bottom, y1 - y0)
    mask = Image.linear_gradient('L').resize((W, y1 - y0)).point(lambda v: min(255, v * 2))
    band.putalpha(mask)
    img.alpha_composite(band, (0, y0))


def watermark(img, name, scale, pos, tint, alpha=0.22, flip=False, frame=0, blur=0.6):
    """A sprite as a soft, single-hue silhouette: luminance mapped onto the
    theme's tint, faded and slightly blurred so its edges never read as a
    hard line behind a button."""
    spr = sprite(name, scale, frame)
    if flip:
        spr = spr.transpose(Image.FLIP_LEFT_RIGHT)
    lum = spr.convert('L')
    col = ImageOps.colorize(lum, black=tuple(max(0, c - 40) for c in tint),
                            white=tuple(min(255, c + 60) for c in tint)).convert('RGBA')
    col.putalpha(spr.getchannel('A').point(lambda v: int(v * alpha)))
    if blur:
        col = col.filter(ImageFilter.GaussianBlur(scale * blur))
    img.alpha_composite(col, pos)


def scatter(img, piece, n, seed, alpha=1.0, box=(0, 0, W, H)):
    """Pixel-art particles (rain, snow, bubbles) dropped at random."""
    r = random.Random(seed)
    p = piece.copy()
    p.putalpha(p.getchannel('A').point(lambda v: int(v * alpha)))
    for _ in range(n):
        img.alpha_composite(p, (r.randrange(box[0] - p.width, box[2]), r.randrange(box[1] - p.height, box[3])))


def texture(img, path, scale, alpha, colour=None):
    """A tiling weather texture (fog, sandstorm, ash) laid over everything."""
    t = indexed(path, scale, colour, int(255 * alpha))
    for y in range(0, H, t.height):
        for x in range(0, W, t.width):
            img.alpha_composite(t, (x, y))


def calm(img, k, toward=None):
    """Pull every pixel a fraction k toward one colour (the image's mean by
    default): lowers contrast without blurring the pixel art."""
    rgb = img.convert('RGB')
    mean = toward or tuple(int(v) for v in ImageStat.Stat(rgb).mean)
    return Image.blend(rgb, Image.new('RGB', img.size, mean), k).convert('RGBA')


def clouds_strip(scale, alpha=255, colours=None):
    """The title screen's cloud strip, recoloured by palette index: its PNG
    palette is not the one the game draws it with. 0 is transparent, 2 the
    cloud body, 12 its shading."""
    src = Image.open('graphics/title_screen/clouds.png')
    colours = colours or {2: (255, 255, 255), 12: (196, 222, 240)}
    c = Image.new('RGBA', src.size, (0, 0, 0, 0))
    sp, cp = src.load(), c.load()
    for yy in range(src.height):
        for xx in range(src.width):
            if sp[xx, yy] in colours:
                cp[xx, yy] = colours[sp[xx, yy]] + (alpha,)
    return c.resize((c.width * scale, c.height * scale), Image.NEAREST)


def cloud_row(img, y, scale, seed, alpha=200, colours=None):
    c = clouds_strip(scale, alpha, colours)
    r = random.Random(seed)
    x = -r.randrange(0, c.width)
    while x < W:
        img.alpha_composite(c, (x, y + r.randrange(-12, 12)))
        x += c.width - 8


# ---- PC box wallpapers ---------------------------------------------------

def box_tile(name, scale=PX, soften=0.0, centre=False):
    """A seamless wallpaper pattern tiled at the game's pixel size. centre
    puts a tile's middle (a pals wallpaper's picture) in the middle of each
    side band rather than wherever the tiling happens to land."""
    im = wallpaper(name)
    t = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    y0 = -((t.height - H % t.height) // 2)

    def tiled(x0):
        part = Image.new('RGB', (W, H))
        for y in range(y0, H, t.height):
            for x in range(x0 % t.width - t.width, W, t.width):
                part.paste(t, (x, y))
        return part

    if centre:
        out = Image.new('RGB', (W, H))
        out.paste(tiled(130 - t.width // 2).crop((0, 0, W // 2, H)), (0, 0))
        out.paste(tiled(W - 130 - t.width // 2).crop((W // 2, 0, W, H)), (W // 2, 0))
    else:
        out = tiled(0)
    out = out.convert('RGBA')
    return calm(out, soften) if soften else out


def box_fill(name, soften=0.0, crop=(0, 0, 0, 0)):
    """A wallpaper with top-to-bottom structure (a sky, a shore, the sea
    floor): scaled to the full height, its left part in the left band and its
    right part in the right band. The join is in the middle, under the game."""
    im = wallpaper(name)
    im = im.crop((crop[0], crop[1], im.width - crop[2], im.height - crop[3]))
    t = im.resize((round(im.width * H / im.height), H), Image.NEAREST)
    out = Image.new('RGB', (W, H))
    out.paste(t.crop((0, 0, W // 2, H)), (0, 0))
    out.paste(t.crop((t.width - W // 2, 0, t.width, H)), (W // 2, 0))
    out = out.convert('RGBA')
    return calm(out, soften) if soften else out


# ---- Hoenn ---------------------------------------------------------------

def rayquaza_sky():
    img = gradient((18, 66, 76), (44, 116, 108))
    stars(img, 70, 1, (0, 0, W, 300), (200, 240, 230))
    glow(img, W // 2, 420, 700, (90, 170, 150), 0.6)
    cloud_row(img, H - 150, 4, 2, alpha=70, colours={2: (170, 225, 205), 12: (120, 190, 170)})
    watermark(img, 'rayquaza', 6, (-90, 120), (60, 150, 120))
    watermark(img, 'rayquaza', 6, (W - 300, 100), (60, 150, 120), flip=True)
    return img


def hoenn_sunset():
    img = gradient((226, 132, 104), (112, 72, 132))
    soft_band(img, 470, H, (70, 80, 140), (40, 50, 100))
    glow(img, 130, 470, 260, (255, 200, 140), 0.5)
    glow(img, W - 130, 470, 260, (255, 200, 140), 0.5)
    cloud_row(img, 60, 4, 3, alpha=45, colours={2: (255, 214, 190), 12: (240, 170, 160)})
    watermark(img, 'wingull', 4, (40, 200), (150, 80, 110), alpha=0.18)
    watermark(img, 'wailord', 5, (W - 300, 430), (60, 80, 150), flip=True)
    watermark(img, 'kyogre', 5, (-50, 430), (60, 80, 150))
    return img


def magma():
    img = gradient((52, 14, 12), (112, 34, 16))
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
    img = gradient((122, 178, 214), (150, 196, 170))
    cloud_row(img, 40, 4, 4, alpha=110)
    soft_band(img, 520, H, (110, 168, 112), (86, 140, 92))
    glow(img, W // 2, 160, 600, (255, 250, 220), 0.35)
    watermark(img, 'treecko', 4, (0, 380), (60, 120, 70), alpha=0.26)
    watermark(img, 'torchic', 4, (W - 260, 300), (60, 120, 70), alpha=0.26, flip=True)
    watermark(img, 'mudkip', 4, (W - 280, 560), (60, 120, 70), alpha=0.26, flip=True)
    return img


def eon_night():
    img = gradient((14, 16, 46), (34, 28, 76))
    stars(img, 160, 8, (0, 0, W, H), (190, 200, 255))
    glow(img, 150, 150, 220, (230, 230, 255), 0.35)
    watermark(img, 'latias', 5, (-40, 300), (120, 90, 170))
    watermark(img, 'latios', 5, (W - 290, 280), (90, 110, 190), flip=True)
    return img


def primal_clash():
    """Groudon's land on the left, Kyogre's sea on the right."""
    img = side_gradient((120, 36, 18), (16, 46, 120))
    glow(img, 0, H, 600, (255, 120, 50), 0.40)
    glow(img, W, 0, 600, (90, 170, 255), 0.35)
    watermark(img, 'groudon', 6, (-120, 260), (170, 60, 30), alpha=0.26)
    watermark(img, 'kyogre', 6, (W - 270, 300), (40, 90, 190), alpha=0.26, flip=True)
    return img


def sealed_chamber():
    """Sandstone with the Sealed Chamber's raised braille dots."""
    img = gradient((150, 124, 88), (112, 88, 62))
    r = random.Random(11)
    with Layer(img) as d:
        # braille cells: 2x3 dot grids, about half the dots raised
        for cy in range(30, H, 110):
            for cx in range(20, W, 70):
                for k in range(6):
                    if r.random() < 0.5:
                        x = cx + (k % 2) * 22; y = cy + (k // 2) * 22
                        d.ellipse([x, y, x + 10, y + 10], fill=(70, 52, 34, 46))
                        d.ellipse([x - 2, y - 2, x + 6, y + 6], fill=(230, 206, 160, 38))
    watermark(img, 'regirock', 5, (-20, 330), (140, 100, 60), alpha=0.22)
    watermark(img, 'registeel', 5, (W - 300, 330), (120, 110, 100), alpha=0.22, flip=True)
    return img


def sootopolis():
    """The crater city's deep water, still and ringed with soft ripples."""
    img = gradient((20, 92, 116), (10, 52, 84))
    with Layer(img) as d:
        for cx, cy in ((100, 640), (W - 100, 300)):
            for i in range(1, 14):
                rr = i * 46
                d.ellipse([cx - rr, cy - rr * 0.42, cx + rr, cy + rr * 0.42],
                          outline=(180, 235, 240, max(6, 34 - i * 2)), width=3)
    soft_band(img, 0, 160, (220, 232, 236), (20, 92, 116))
    watermark(img, 'milotic', 5, (-40, 200), (60, 150, 170), alpha=0.22)
    watermark(img, 'wailmer', 4, (W - 240, 520), (40, 110, 150), alpha=0.22, flip=True)
    return img


def meteor_falls():
    img = gradient((12, 10, 34), (40, 24, 70))
    stars(img, 200, 21, (0, 0, W, H), (220, 210, 255))
    r = random.Random(22)
    with Layer(img) as d:             # meteor streaks, high and faint
        for _ in range(7):
            x = r.randrange(0, W); y = r.randrange(0, 360); n = r.randrange(80, 180)
            for k in range(n):
                d.point((x - k, y + k // 2), fill=(255, 230, 200, max(0, 120 - k * 120 // n)))
    glow(img, W // 2, H + 100, 700, (160, 90, 200), 0.35)
    watermark(img, 'deoxys', 6, (-90, 280), (170, 80, 90), alpha=0.22)
    watermark(img, 'lunatone', 4, (W - 250, 80), (160, 150, 120), alpha=0.18, flip=True)
    watermark(img, 'solrock', 4, (W - 260, 560), (180, 110, 70), alpha=0.18, flip=True)
    return img


def contest_hall():
    """Red stage curtains with spotlights."""
    img = gradient((120, 20, 34), (60, 8, 20))
    with Layer(img) as d:                  # curtain folds
        for x in range(0, W, 46):
            d.rectangle([x, 0, x + 18, H], fill=(0, 0, 0, 26))
            d.rectangle([x + 22, 0, x + 28, H], fill=(255, 200, 200, 14))
    glow(img, 160, 0, 520, (255, 236, 190), 0.40)
    glow(img, W - 160, 0, 520, (255, 236, 190), 0.40)
    soft_band(img, 680, H, (120, 20, 34), (40, 4, 12))
    return img


# ---- weather -------------------------------------------------------------

def rain():
    """Route 119's rain: the game's own raindrop over a dark green-grey sky."""
    img = gradient((52, 66, 72), (30, 48, 46))
    drop = indexed('graphics/weather/rain.png').crop((0, 0, 16, 32)).resize((32, 64), Image.NEAREST)
    scatter(img, drop, 260, 31, alpha=0.30)
    soft_band(img, 640, H, (40, 70, 52), (24, 46, 34))
    watermark(img, 'kecleon', 4, (W - 250, 520), (60, 100, 70), alpha=0.18, flip=True)
    watermark(img, 'lotad', 4, (10, 580), (60, 100, 70), alpha=0.18)
    return img


def snowfall():
    img = gradient((40, 58, 98), (90, 116, 156))
    a = indexed('graphics/weather/snow0.png', PX); b = indexed('graphics/weather/snow1.png', PX)
    scatter(img, a, 120, 41, alpha=0.30)
    scatter(img, b, 200, 42, alpha=0.24)
    soft_band(img, 720, H, (120, 140, 180), (110, 130, 170))
    watermark(img, 'spheal', 4, (20, 560), (150, 170, 210), alpha=0.20)
    watermark(img, 'regice', 5, (W - 300, 300), (140, 170, 220), alpha=0.20, flip=True)
    return img


def volcanic_ash():
    """Route 113: ash drifting down from Mt. Chimney."""
    img = gradient((118, 108, 104), (78, 70, 70))
    texture(img, 'graphics/weather/ash.png', PX, 0.22, (200, 196, 190))
    glow(img, W // 2, H + 60, 600, (240, 140, 80), 0.25)
    watermark(img, 'torkoal', 5, (-30, 480), (120, 90, 80), alpha=0.20)
    watermark(img, 'skarmory', 5, (W - 300, 160), (110, 110, 120), alpha=0.18, flip=True)
    return img


def sandstorm():
    """Route 111's desert sandstorm."""
    img = gradient((196, 160, 104), (150, 112, 70))
    texture(img, 'graphics/weather/sandstorm.png', PX, 0.20, (232, 204, 150))
    watermark(img, 'trapinch', 4, (10, 560), (150, 110, 60), alpha=0.20)
    watermark(img, 'cacnea', 4, (W - 250, 520), (120, 120, 60), alpha=0.20, flip=True)
    watermark(img, 'flygon', 5, (W - 320, 60), (120, 130, 70), alpha=0.16, flip=True)
    return img


def fog():
    img = gradient((150, 160, 170), (110, 120, 132))
    texture(img, 'graphics/weather/fog_horizontal.png', PX, 0.28, (230, 234, 240))
    watermark(img, 'duskull', 4, (20, 260), (110, 110, 130), alpha=0.16)
    watermark(img, 'shuppet', 4, (W - 250, 540), (110, 110, 130), alpha=0.16, flip=True)
    return img


def harsh_sun():
    img = gradient((250, 176, 76), (214, 104, 50))
    glow(img, W // 2, -120, 900, (255, 244, 200), 0.5)
    glow(img, 0, 0, 380, (255, 250, 230), 0.35)
    soft_band(img, 680, H, (214, 120, 60), (170, 80, 40))
    watermark(img, 'solrock', 5, (-20, 300), (200, 110, 50), alpha=0.18)
    watermark(img, 'groudon', 5, (W - 300, 420), (190, 90, 40), alpha=0.16, flip=True)
    return img


def underwater():
    """Diving off Mossdeep: light from above, bubbles rising."""
    img = gradient((30, 108, 156), (8, 34, 76))
    with Layer(img) as d:                  # light shafts
        for x in (60, 240, W - 260, W - 90):
            d.polygon([(x, 0), (x + 70, 0), (x + 170, H), (x + 40, H)], fill=(180, 230, 255, 16))
    bub = indexed('graphics/weather/bubble.png', PX)
    big, small = bub.crop((0, 0, 8 * PX, 8 * PX)), bub.crop((0, 8 * PX, 8 * PX, 16 * PX))
    scatter(img, big, 40, 51, alpha=0.35)
    scatter(img, small, 70, 52, alpha=0.30)
    watermark(img, 'relicanth', 5, (-30, 520), (40, 90, 120), alpha=0.22)
    watermark(img, 'kyogre', 5, (W - 300, 220), (40, 80, 150), alpha=0.18, flip=True)
    return img


# ---- classic & minimal ---------------------------------------------------

def gba_indigo():
    img = gradient((70, 58, 150), (48, 38, 110))
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


def pocket():
    """The grey-green of a pocket-sized handheld's screen."""
    img = gradient((196, 200, 180), (170, 176, 156))
    with Layer(img) as d:
        for y in range(0, H, 8):
            d.line([(0, y), (W, y)], fill=(0, 0, 0, 8))
    watermark(img, 'pikachu', 5, (-20, 330), (110, 116, 96), alpha=0.18)
    watermark(img, 'pichu', 4, (W - 250, 380), (110, 116, 96), alpha=0.18, flip=True)
    return img


def midnight():
    return gradient((16, 20, 40), (6, 8, 18))


def slate():
    img = gradient((70, 76, 86), (44, 48, 56))
    glow(img, W // 2, H // 2, 900, (120, 130, 150), 0.18)
    return img


def paper():
    img = gradient((238, 232, 220), (218, 210, 196))
    r = random.Random(61)
    with Layer(img) as d:                  # a faint paper grain
        for _ in range(4000):
            x = r.randrange(W); y = r.randrange(H)
            d.point((x, y), fill=(120, 100, 80, 18))
    return img


# ---- the catalogue -------------------------------------------------------
#
# (index, id, function). Index 0 and 1 are the fork's own paintings. Never
# renumber: the index is what players' settings store. Append new themes.

def _box(name, **kw):
    return lambda: box_tile(name, **kw)


def _fill(name, **kw):
    return lambda: box_fill(name, **kw)


CATALOGUE = [
    (2, 'rayquaza_sky', rayquaza_sky),
    (3, 'hoenn_sunset', hoenn_sunset),
    (4, 'magma', magma),
    (5, 'starter_meadow', starter_meadow),
    (6, 'eon_night', eon_night),
    (7, 'gba_indigo', gba_indigo),
    (8, 'classic_green', classic_green),
    # Hoenn
    (9, 'primal_clash', primal_clash),
    (10, 'sealed_chamber', sealed_chamber),
    (11, 'sootopolis', sootopolis),
    (12, 'meteor_falls', meteor_falls),
    (13, 'contest_hall', contest_hall),
    # Weather
    (14, 'rain', rain),
    (15, 'snowfall', snowfall),
    (16, 'volcanic_ash', volcanic_ash),
    (17, 'sandstorm', sandstorm),
    (18, 'fog', fog),
    (19, 'harsh_sun', harsh_sun),
    (20, 'underwater', underwater),
    # PC box wallpapers
    (21, 'box_forest', _box('forest')),
    (22, 'box_city', _box('city')),
    (23, 'box_desert', _box('desert')),
    (24, 'box_savanna', _fill('savanna')),
    (25, 'box_crag', _box('crag')),
    (26, 'box_volcano', _box('volcano')),
    (27, 'box_snow', _fill('snow')),
    (28, 'box_cave', _box('cave')),
    (29, 'box_beach', _fill('beach', crop=(8, 0, 8, 0))),
    (30, 'box_seafloor', _fill('seafloor', soften=0.25)),
    (31, 'box_river', _fill('river')),
    (32, 'box_sky', _fill('sky', soften=0.18)),
    (33, 'box_polkadot', _box('polkadot')),
    (34, 'box_pokecenter', _box('pokecenter')),
    (35, 'box_machine', _box('machine')),
    # Box pals: the friends wallpapers as soft repeating patterns
    (36, 'pal_pikachu', _box('pikachu', scale=2, soften=0.55, centre=True)),
    (37, 'pal_zigzagoon', _box('zigzagoon', scale=2, soften=0.62, centre=True)),
    (38, 'pal_azumarill', _box('azumarill', scale=2, soften=0.66, centre=True)),
    (39, 'pal_ludicolo', _box('ludicolo', scale=2, soften=0.62, centre=True)),
    # Classic and minimal
    (40, 'pocket', pocket),
    (41, 'midnight', midnight),
    (42, 'slate', slate),
    (43, 'paper', paper),
]


# ---- border frames -------------------------------------------------------
#
# The game's own 20 text-window frames (Options > FRAME) as borders around the
# game screen. Each is 3x3 tiles of 8px: corners, an edge tile the game
# repeats, and the fill. Saved as a nine-slice the overlay scales by the
# game's pixel size: the fill colour becomes transparent (the frame is drawn
# outside the game, never over it), and inner rows that are only fill are
# trimmed so the frame sits tight against the screen.
#   FRAMEn.png: k x k corners, 8px edge pieces; size (2k + 8) square:
#     [TL k*k][top 8*k][TR k*k] / [left k*8][  ][right k*8] / [BL][bottom][BR]

def frame_slices(n, tint=None):
    im = Image.open(f'graphics/text_window/{n}.png')
    idx = im.load()
    pal = im.getpalette()[:48]
    pal = [tuple(pal[i:i + 3]) for i in range(0, 48, 3)]
    centre = [idx[x, y] for y in range(8, 16) for x in range(8, 16)]
    fill = max(set(centre), key=centre.count)
    clear = {0, fill}
    # inner rows of the top edge tile (bottom of tile 1,0) that are only fill
    inset = 0
    for y in range(7, -1, -1):
        if all(idx[x, y] in clear for x in range(8, 16)):
            inset += 1
        else:
            break
    k = 8 - inset

    def px(x, y):
        v = idx[x, y]
        if v in clear:
            return (0, 0, 0, 0)
        c = pal[v]
        if tint:
            lum = (c[0] * 299 + c[1] * 587 + c[2] * 114) // 1000
            c = tuple(int(lo + (hi - lo) * lum / 255) for lo, hi in zip(*tint))
        return c + (255,)

    out = Image.new('RGBA', (2 * k + 8, 2 * k + 8), (0, 0, 0, 0))
    op = out.load()
    # source x/y spans for left/middle/right (and top/middle/bottom) bands
    src = [(0, k), (8, 16), (16 + inset, 24)]
    dst = [0, k, k + 8]
    for row in range(3):
        for col in range(3):
            if row == 1 and col == 1:
                continue
            (x0, x1), (y0, y1) = src[col], src[row]
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    op[dst[col] + xx - x0, dst[row] + yy - y0] = px(xx, yy)
    return out


# Tinted variants, for themes no game frame's own colours suit:
# (asset name, frame number, (dark colour, light colour)).
TINTED_FRAMES = [
    ('FRAME_dmg', 2, ((15, 56, 15), (155, 188, 15))),
]


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
    only = set(sys.argv[2:])            # optional: regenerate just these ids
    index = ['0 starfall', '1 open_sea']
    for i, tid, fn in CATALOGUE:
        index.append(f'{i} {tid}')
        if only and tid not in only:
            continue
        fn().convert('RGB').save(OUT / f'BG{i}.png', optimize=True)
        print(f'BG{i}.png  {tid}')
    (OUT / 'themes-index.txt').write_text('\n'.join(index) + '\n')
    for n in range(1, 21):
        frame_slices(n).save(OUT / f'FRAME{n}.png', optimize=True)
    for name, n, tint in TINTED_FRAMES:
        frame_slices(n, tint).save(OUT / f'{name}.png', optimize=True)
    print('FRAME1..20.png + %d tinted frames' % len(TINTED_FRAMES))


if __name__ == '__main__':
    main()
