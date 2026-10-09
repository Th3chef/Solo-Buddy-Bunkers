"""Solo Buddy Bunkers release art: the hero scene, a flat illustration. A buddy bunker as in the game (weathered
concrete legs, big angled buttresses in the opening's top corners, a hazard-paneled lintel, the chamber with supply
drums and a closed inner door, the blast door sunk in the floor, a switch box with a round green button on each leg) in
a hazy jungle, both buttons lit, and a link of light between the two (one press,
both switches). hero(W, H, cx, cy, s) -> RGB image, the bunker centered at (cx, cy) with size s (the opening's half
width is 0.85 s). The text is added by the HTML cards (cards.py). Drawn at 2x and scaled down."""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter

YELLOW = (255, 231, 16)
HAZARD = (232, 196, 40)
LIME = (190, 255, 70)
CYAN = (120, 235, 255)
CONC, CONC_D, CONC_L = (176, 164, 136), (138, 128, 106), (204, 194, 170)


def noise(w, h, sigma, seed):
    rnd = np.random.default_rng(seed)
    a = gaussian_filter(rnd.standard_normal((h, w)), sigma)
    return (a - a.min()) / (a.max() - a.min() + 1e-9)


def glow(base, layer, radius, strength=1.0):
    """Screen-blend a blurred copy of an RGB layer (black = nothing) onto base."""
    g = np.asarray(layer.filter(ImageFilter.GaussianBlur(radius)), float) * strength
    b = np.asarray(base, float)
    out = 255 - (255 - b) * (255 - np.clip(g, 0, 255)) / 255
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def mix(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def blob(d, x, y, r, col, rnd, n=7, hi=None):
    """a leafy clump: a cluster of circles, with a lighter top-left tone when hi is given"""
    for i in range(n):
        a = rnd.uniform(0, 2 * math.pi)
        dist = rnd.uniform(0, 0.6) * r
        rr = r * rnd.uniform(0.45, 0.75)
        bx, by = x + math.cos(a) * dist, y + math.sin(a) * dist * 0.7
        d.ellipse((bx - rr, by - rr, bx + rr, by + rr), fill=col)
    if hi:
        for i in range(max(2, n // 3)):
            rr = r * rnd.uniform(0.25, 0.4)
            bx, by = x - r * rnd.uniform(0.1, 0.4), y - r * rnd.uniform(0.2, 0.45)
            d.ellipse((bx - rr, by - rr, bx + rr, by + rr), fill=hi)


def hero(W, H, cx, cy, s, seed=7, arc=1.15):
    k = 2                                      # supersampling
    W2, H2, cx, cy, s = W * k, H * k, cx * k, cy * k, s * k
    floor = cy + 0.42 * s                      # where the opening meets the ground
    horizon = floor - 0.25 * s
    rnd = np.random.default_rng(seed + 3)

    # sky: a hazy jungle day, dark teal overhead to a warm haze at the horizon
    yy = np.linspace(0, 1, H2)[:, None]
    t = np.clip((yy * H2) / max(horizon, 1), 0, 1)[..., None]
    top, hz = np.array([46, 66, 74]), np.array([204, 194, 152])
    sky = top + (hz - top) * t ** 1.4
    sky = np.broadcast_to(sky, (H2, W2, 3)).copy()
    clouds = noise(W2 // 6, H2 // 6, 8, seed)
    clouds = np.asarray(Image.fromarray((clouds * 255).astype(np.uint8)).resize((W2, H2), Image.BICUBIC), float) / 255
    sky *= (0.9 + 0.2 * clouds[..., None])
    img = Image.fromarray(np.clip(sky, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)

    # three layers of jungle, far (hazy) to near (dark)
    for col, hi, base, r, amp in [((136, 140, 114), None, 0.34, 0.15, 0.26),
                                  ((88, 102, 70), (104, 118, 80), 0.20, 0.19, 0.22),
                                  ((48, 64, 40), (62, 80, 48), 0.07, 0.23, 0.16)]:
        r *= s
        by = horizon - base * s
        d.rectangle((0, by, W2, horizon + 0.02 * s), fill=col)
        x = -r
        while x < W2 + r:
            ty = by - rnd.uniform(0, amp) * s
            d.line((x, ty, x + rnd.uniform(-0.02, 0.02) * s, by), fill=mix(col, (20, 20, 16), 0.3), width=max(2, int(0.012 * s)))
            blob(d, x, ty, r * rnd.uniform(0.75, 1.15), col, rnd, n=8, hi=hi)
            x += r * rnd.uniform(0.8, 1.2)
        # haze in front of the layer
        arr = np.asarray(img, float)
        f = np.clip(1 - (horizon - np.arange(H2)[:, None]) / (0.5 * s), 0, 1)[..., None] * 0.22
        arr = arr * (1 - f) + hz * f
        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(img)

    # ground: moss and dirt with grain, darker toward the viewer
    g = noise(W2 // 6, H2 // 6, 4.0, seed + 5)
    g = np.asarray(Image.fromarray((g * 255).astype(np.uint8)).resize((W2, H2), Image.BICUBIC), float) / 255
    arr = np.asarray(img, float)
    gy = np.clip((np.arange(H2)[:, None] - horizon) / max(H2 - horizon, 1), 0, 1)[..., None]
    moss, dirt = np.array([70, 84, 46]), np.array([104, 92, 66])
    gm = g[..., None]
    ground = (moss + (dirt - moss) * np.clip((gm - 0.55) * 2, 0, 1)) * (0.9 + 0.2 * gm) * (1 - 0.45 * gy)
    arr = np.where((np.arange(H2)[:, None] >= horizon)[..., None], ground, arr)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for _ in range(int(W2 / s * 22)):              # stones and fern tufts, bigger toward the viewer
        y = rnd.uniform(horizon + 0.02 * s, H2)
        x = rnd.uniform(0, W2)
        depth = (y - horizon) / max(H2 - horizon, 1)
        if abs(x - cx) < 1.6 * s and y < floor + 0.30 * s:
            continue                               # not on the bunker or its forecourt
        r = (0.010 + 0.05 * depth ** 1.4) * s * rnd.uniform(0.5, 1.3)
        if rnd.uniform() < 0.5:
            n = int(rnd.integers(5, 8))
            ang = np.sort(rnd.uniform(0, 2 * math.pi, n))
            poly = [(x + r * math.cos(a) * rnd.uniform(0.7, 1.2), y + 0.55 * r * math.sin(a) * rnd.uniform(0.7, 1.1)) for a in ang]
            d.polygon(poly, fill=(92, 90, 80))
            d.line([p for p, a in zip(poly, ang) if math.sin(a) < 0], fill=(150, 146, 128), width=max(1, int(r * 0.15)))
        else:
            c = mix((60, 96, 40), (90, 124, 52), rnd.uniform())
            for a in np.linspace(-2.4, -0.7, 6):
                a += rnd.uniform(-0.1, 0.1)
                L = r * rnd.uniform(1.4, 2.2)
                d.line((x, y, x + math.cos(a) * L, y + math.sin(a) * L * 0.8), fill=c, width=max(2, int(r * 0.18)))

    OW, OH, BH, LW = 0.85 * s, 0.56 * s, 0.32 * s, 0.42 * s
    top_beam, top_open = floor - OH - BH, floor - OH

    def concrete(box, base=CONC, sd=0, poly=None):
        """weathered concrete: noise shading, rain stains running down, darker toward the bottom"""
        x0, y0, x1, y1 = [int(v) for v in box]
        w, h = max(1, x1 - x0), max(1, y1 - y0)
        n1 = noise(w, h, max(2.0, w / 30), seed + 20 + sd)[..., None]
        n2 = noise(w, h, 1.2, seed + 40 + sd)[..., None]
        st = noise(w, max(2, h // 10), 1.5, seed + 60 + sd)
        st = np.asarray(Image.fromarray((st * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), float)[..., None] / 255
        yy = np.linspace(0, 1, h)[:, None, None]
        a = np.array(base) * (0.84 + 0.2 * n1 + 0.07 * n2) * (1 - 0.16 * yy) * (1 - 0.22 * np.clip(st - 0.55, 0, 1) * 2.2)
        tile = Image.fromarray(np.clip(np.broadcast_to(a, (h, w, 3)), 0, 255).astype(np.uint8))
        if poly is None:
            img.paste(tile, (x0, y0))
        else:
            m = Image.new('L', (w, h), 0)
            ImageDraw.Draw(m).polygon([(px - x0, py - y0) for px, py in poly], fill=255)
            img.paste(tile, (x0, y0), m)

    def stripes(box, step, col=HAZARD, dark=(26, 24, 20)):
        x0, y0, x1, y1 = box
        layer = Image.new('RGB', img.size, dark)
        sd_ = ImageDraw.Draw(layer)
        x = x0 - (y1 - y0) - step
        while x < x1 + step:
            sd_.polygon([(x, y1), (x + step, y1), (x + step + (y1 - y0), y0), (x + (y1 - y0), y0)], fill=col)
            x += 2 * step
        m = Image.new('L', img.size, 0)
        ImageDraw.Draw(m).rectangle(box, fill=255)
        img.paste(layer, (0, 0), m)

    # the earth mound the bunker is dug into, overgrown
    mound = [(cx - 1.75 * s, floor + 0.02 * s), (cx - 1.42 * s, top_beam + 0.10 * s), (cx - 0.95 * s, top_beam - 0.16 * s),
             (cx + 0.95 * s, top_beam - 0.14 * s), (cx + 1.42 * s, top_beam + 0.12 * s), (cx + 1.75 * s, floor + 0.02 * s)]
    d.polygon(mound, fill=(56, 66, 40))
    for _ in range(60):
        u = rnd.uniform(-1.6, 1.6)
        yt = top_beam - 0.14 * s * (1 - (abs(u) / 1.7) ** 2) + rnd.uniform(-0.02, 0.35) * s
        blob(d, cx + u * s, yt, rnd.uniform(0.05, 0.11) * s, mix((50, 70, 38), (74, 96, 50), rnd.uniform()), rnd, n=5,
             hi=(92, 116, 58) if rnd.uniform() < 0.5 else None)

    # the chamber behind the opening: back wall, a low platform, the closed inner door, drums, steam
    concrete((cx - OW, top_open, cx + OW, floor), base=(132, 124, 104), sd=1)
    d = ImageDraw.Draw(img)
    d.rectangle((cx - OW, floor - 0.13 * s, cx + OW, floor), fill=(112, 106, 90))
    d.line((cx - OW, floor - 0.13 * s, cx + OW, floor - 0.13 * s), fill=(150, 142, 120), width=max(2, int(0.006 * s)))
    door = (cx - 0.17 * s, floor - 0.47 * s, cx + 0.17 * s, floor - 0.13 * s)
    d.rectangle((door[0] - 0.03 * s, door[1] - 0.03 * s, door[2] + 0.03 * s, door[3]), fill=(78, 76, 68))
    d.rectangle(door, fill=(140, 134, 118))
    stripes((door[0], door[1], door[2], door[1] + 0.035 * s), 0.025 * s)
    d = ImageDraw.Draw(img)
    for sx in (-1, 1):
        for fy in (0.30, 0.65):
            px0 = cx + sx * 0.03 * s if sx > 0 else cx - 0.14 * s
            py0 = door[1] + 0.06 * s + (fy - 0.30) * 0.38 * s
            d.rectangle((px0, py0, px0 + 0.11 * s, py0 + 0.11 * s), fill=(122, 116, 102), outline=(100, 96, 84), width=max(2, int(0.005 * s)))
    d.line((cx, door[1] + 0.035 * s, cx, door[3]), fill=(84, 80, 72), width=max(2, int(0.008 * s)))
    lamp = Image.new('RGB', img.size, (0, 0, 0))
    ld = ImageDraw.Draw(lamp)
    r = 0.016 * s
    d.ellipse((cx - r, door[1] - 0.075 * s - r, cx + r, door[1] - 0.075 * s + r), fill=(255, 120, 80))
    ld.ellipse((cx - 3 * r, door[1] - 0.075 * s - 3 * r, cx + 3 * r, door[1] - 0.075 * s + 3 * r), fill=(200, 70, 40))
    for i, u in enumerate([-0.72, -0.60, -0.48, -0.36, 0.40, 0.52, 0.64]):      # drums on the platform
        dx_, dy_ = cx + u * s, floor - 0.12 * s
        col = (128, 94, 60) if i % 3 != 1 else (96, 104, 70)
        d.rounded_rectangle((dx_ - 0.055 * s, dy_ - 0.16 * s, dx_ + 0.055 * s, dy_), 0.01 * s, fill=col)
        d.ellipse((dx_ - 0.055 * s, dy_ - 0.175 * s, dx_ + 0.055 * s, dy_ - 0.145 * s), fill=mix(col, (230, 220, 190), 0.25))
        for f in (0.22, 0.72):
            d.line((dx_ - 0.055 * s, dy_ - f * 0.16 * s, dx_ + 0.055 * s, dy_ - f * 0.16 * s), fill=mix(col, (0, 0, 0), 0.3), width=max(2, int(0.006 * s)))
        d.line((dx_ - 0.03 * s, dy_ - 0.15 * s, dx_ - 0.03 * s, dy_ - 0.01 * s), fill=mix(col, (255, 255, 255), 0.15), width=max(2, int(0.008 * s)))
    img = glow(img, lamp, 0.03 * s, 1.0)
    steam = Image.new('RGB', img.size, (0, 0, 0))
    sd2 = ImageDraw.Draw(steam)
    for _ in range(14):
        x = cx + rnd.uniform(-0.75, 0.75) * s
        y = floor - rnd.uniform(0.15, 0.45) * s
        r = rnd.uniform(0.06, 0.13) * s
        sd2.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(70, 68, 60))
    img = glow(img, steam, 0.06 * s, 1.0)
    d = ImageDraw.Draw(img)

    # the blast door, sunk into the floor of the opening, a hazard stripe along its edge
    d.polygon([(cx - OW + 0.08 * s, floor - 0.075 * s), (cx + OW - 0.08 * s, floor - 0.075 * s),
               (cx + OW, floor + 0.005 * s), (cx - OW, floor + 0.005 * s)], fill=(66, 64, 58))
    d.line((cx - OW + 0.08 * s, floor - 0.075 * s, cx + OW - 0.08 * s, floor - 0.075 * s), fill=(110, 106, 96), width=max(2, int(0.006 * s)))
    stripes((cx - OW + 0.03 * s, floor - 0.035 * s, cx + OW - 0.03 * s, floor - 0.012 * s), 0.022 * s)
    d = ImageDraw.Draw(img)

    # the legs, with a wider foot
    for side in (-1, 1):
        x0, x1 = sorted((cx + side * OW, cx + side * (OW + LW)))
        concrete((x0, top_beam, x1, floor), sd=2 + side)
        fx0, fx1 = sorted((cx + side * OW, cx + side * (OW + LW + 0.06 * s)))
        concrete((fx0, floor - 0.09 * s, fx1, floor + 0.02 * s), base=CONC_D, sd=5 + side)
        d = ImageDraw.Draw(img)
        ix = x0 if side > 0 else x1
        d.line((ix, top_open, ix, floor), fill=(96, 88, 72), width=max(3, int(0.01 * s)))
        ox = x1 if side > 0 else x0                # the outer edge, in shade on the right
        if side > 0:
            d.rectangle((ox - 0.05 * s, top_beam, ox, floor), fill=mix(CONC_D, (60, 56, 46), 0.25))
    # big angled buttresses in the opening's top corners
    for side in (-1, 1):
        ex = cx + side * OW
        poly = [(ex, top_open), (ex, top_open + 0.34 * s), (ex - side * 0.10 * s, top_open + 0.34 * s), (ex - side * 0.40 * s, top_open)]
        xs = [p[0] for p in poly]
        concrete((min(xs), top_open, max(xs), top_open + 0.34 * s), base=CONC if side < 0 else mix(CONC, CONC_D, 0.5), sd=30 + side, poly=poly)
        d = ImageDraw.Draw(img)
        d.line([poly[2], poly[3]], fill=(92, 84, 68), width=max(3, int(0.012 * s)))
        d.line([poly[1], poly[2]], fill=(92, 84, 68), width=max(3, int(0.012 * s)))
        d.line([(poly[2][0] + side * 0.012 * s, poly[2][1] - 0.01 * s), (poly[3][0] + side * 0.03 * s, poly[3][1] + 0.004 * s)], fill=CONC_L, width=max(2, int(0.006 * s)))
        if side < 0:                               # a cable run down the left buttress
            d.line([(ex - side * 0.30 * s, top_open + 0.01 * s), (ex - side * 0.06 * s, top_open + 0.24 * s), (ex - side * 0.06 * s, floor - 0.13 * s)],
                   fill=(40, 40, 36), width=max(2, int(0.012 * s)), joint='curve')
    # the lintel beam: recessed hazard panels between bolted steel plates, a steel strip below, a cap slab with moss
    concrete((cx - OW - LW, top_beam, cx + OW + LW, top_open), sd=9)
    d = ImageDraw.Draw(img)
    panels, span = 4, 2 * (OW + LW) - 0.14 * s
    pw = span / panels
    for i in range(panels):
        px0 = cx - span / 2 + i * pw + 0.04 * s
        box = (px0, top_beam + 0.07 * s, px0 + pw - 0.08 * s, top_open - 0.08 * s)
        d.rectangle((box[0] - 0.012 * s, box[1] - 0.012 * s, box[2] + 0.012 * s, box[3] + 0.012 * s), fill=(110, 102, 84))
        stripes(box, 0.034 * s)
        d = ImageDraw.Draw(img)
    for i in range(panels + 1):
        px = cx - span / 2 + i * pw
        d.rectangle((px - 0.028 * s, top_beam + 0.03 * s, px + 0.028 * s, top_open - 0.04 * s), fill=(98, 96, 88), outline=(70, 68, 62), width=max(2, int(0.004 * s)))
        for f in (0.22, 0.5, 0.78):
            by_ = top_beam + 0.03 * s + (BH - 0.07 * s) * f
            r = 0.008 * s
            d.ellipse((px - r, by_ - r, px + r, by_ + r), fill=(58, 56, 50))
            d.ellipse((px - r * 0.5, by_ - r * 0.8, px + r * 0.2, by_ - r * 0.1), fill=(140, 136, 124))
    d.rectangle((cx - OW - LW, top_open - 0.04 * s, cx + OW + LW, top_open), fill=(62, 62, 58))
    d.line((cx - OW - LW, top_open - 0.04 * s, cx + OW + LW, top_open - 0.04 * s), fill=(110, 108, 100), width=max(2, int(0.005 * s)))
    concrete((cx - OW - LW - 0.07 * s, top_beam - 0.08 * s, cx + OW + LW + 0.07 * s, top_beam), base=CONC_L, sd=12)
    d = ImageDraw.Draw(img)
    for _ in range(26):                          # moss along the cap, some hanging over its edge
        u = rnd.uniform(-1.3, 1.3)
        r = rnd.uniform(0.02, 0.05) * s
        y = top_beam - 0.08 * s
        blob(d, cx + u * s, y, r, (62, 84, 40), rnd, n=4, hi=(86, 110, 52))
        if rnd.uniform() < 0.35:
            d.line((cx + u * s, y, cx + u * s + rnd.uniform(-0.01, 0.01) * s, top_beam + rnd.uniform(0.02, 0.09) * s),
                   fill=(58, 80, 38), width=max(2, int(0.008 * s)))
    # the apron in front
    concrete((cx - 1.45 * s, floor, cx + 1.45 * s, floor + 0.10 * s), base=CONC_D, sd=14)
    d = ImageDraw.Draw(img)
    d.line((cx - 1.45 * s, floor, cx + 1.45 * s, floor), fill=CONC_L, width=max(2, int(0.005 * s)))
    # a warning sign high on the left leg
    wx, wy = cx - OW - LW / 2, top_open + 0.10 * s
    d.polygon([(wx, wy - 0.055 * s), (wx - 0.05 * s, wy + 0.035 * s), (wx + 0.05 * s, wy + 0.035 * s)], fill=YELLOW, outline=(26, 24, 20))
    d.line((wx, wy - 0.025 * s, wx, wy + 0.008 * s), fill=(26, 24, 20), width=max(2, int(0.008 * s)))
    d.ellipse((wx - 0.005 * s, wy + 0.016 * s, wx + 0.005 * s, wy + 0.026 * s), fill=(26, 24, 20))

    # the two switch boxes, a round green button on each, both lit (both pressed)
    neon = Image.new('RGB', img.size, (0, 0, 0))
    nd = ImageDraw.Draw(neon)
    sw = []
    for side in (-1, 1):
        px, py = cx + side * (OW + LW / 2), floor - 0.25 * s
        bw, bh = 0.12 * s, 0.13 * s
        d.rounded_rectangle((px - bw, py - bh, px + bw, py + bh), 0.02 * s, fill=(110, 104, 90), outline=(64, 62, 56), width=max(2, int(0.007 * s)))
        d.rectangle((px - bw * 0.7, py - bh * 0.8, px + bw * 0.7, py - bh * 0.6), fill=LIME)
        by_ = py + 0.025 * s
        r1, r2 = 0.075 * s, 0.055 * s
        d.ellipse((px - r1, by_ - r1, px + r1, by_ + r1), fill=(40, 70, 14))
        d.ellipse((px - r2, by_ - r2, px + r2, by_ + r2), fill=LIME)
        r3 = 0.02 * s
        d.ellipse((px - 0.025 * s - r3, by_ - 0.025 * s - r3, px - 0.025 * s + r3, by_ - 0.025 * s + r3), fill=(235, 255, 190))
        nd.ellipse((px - r1 * 1.25, by_ - r1 * 1.25, px + r1 * 1.25, by_ + r1 * 1.25), fill=(110, 210, 30))
        nd.rectangle((px - bw * 0.8, py - bh * 0.9, px + bw * 0.8, py - bh * 0.5), fill=(70, 140, 20))
        sw.append((px, py - bh - 0.02 * s))
    # the link: an arc of light from one switch over the opening to the other
    (ax, ay), (bx, by) = sw
    pts = []
    for i in range(0, 161):
        u = i / 160
        pts.append((ax + (bx - ax) * u, ay + (by - ay) * u - math.sin(math.pi * u) * arc * s))
    core = Image.new('RGB', img.size, (0, 0, 0))
    cd = ImageDraw.Draw(core)
    seg = 6
    for i in range(0, len(pts) - 1, seg * 2):     # dashed
        cd.line(pts[i:i + seg + 1], fill=CYAN, width=int(0.011 * s))
    nd.line(pts, fill=(50, 120, 150), width=int(0.026 * s))
    for (x, y) in sw:                              # rings above the switches
        rr = 0.07 * s
        cd.ellipse((x - rr, y - rr * 0.45 - 0.02 * s, x + rr, y + rr * 0.45 - 0.02 * s), outline=CYAN, width=int(0.008 * s))
    img = glow(img, neon, 0.06 * s, 1.0)
    img = glow(img, core, 0.012 * s, 1.0)
    img = glow(img, core, 0.002 * s, 1.0)
    d = ImageDraw.Draw(img)

    # vignette and a little grain
    arr = np.asarray(img, float)
    Y, X = np.mgrid[0:H2, 0:W2]
    v = np.maximum(np.abs(X / W2 - 0.5) * 2, np.abs(Y / H2 - 0.5) * 2)
    arr *= (1 - 0.45 * np.clip((v - 0.6) / 0.4, 0, 1) ** 1.5)[..., None]
    arr += (noise(W2, H2, 0.8, seed + 9)[..., None] - 0.5) * 10
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return img.resize((W, H), Image.LANCZOS)


if __name__ == '__main__':
    import sys
    hero(1254, 1254, 627, 740, 460, arc=0.8).save(sys.argv[1] if len(sys.argv) > 1 else 'hero_test.png')
