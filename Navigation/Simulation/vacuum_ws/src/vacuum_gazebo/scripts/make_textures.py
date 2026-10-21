#!/usr/bin/env python3
"""Deterministically generate distinct wall_00..15.png (1024) and floor_0..3.png (2048).

Distinct textures per wall avoid perceptual aliasing in visual loop closure.
Usage: python3 make_textures.py [out_dir]   (default: ../worlds/textures)
"""
import os
import sys
import colorsys
import numpy as np
from PIL import Image, ImageDraw

N_WALL, N_FLOOR = 16, 4


def hsv(h, s, v):
    return tuple(int(255 * c) for c in colorsys.hsv_to_rgb(h % 1.0, s, v))


def wall(i):
    rng = np.random.default_rng(1000 + i)
    S = 1024
    hue = (i / N_WALL + rng.uniform(-0.02, 0.02)) % 1.0
    bw = int(rng.choice([64, 96, 128, 160, 192, 256]))
    bh = int(rng.choice([32, 48, 64, 80, 128]))
    mortar = hsv(hue, 0.1, rng.uniform(0.15, 0.85))
    img = Image.new('RGB', (S, S), mortar)
    d = ImageDraw.Draw(img)
    for r, y in enumerate(range(0, S, bh)):
        off = (bw // 2 if r % 2 else 0) if i % 3 else int(rng.integers(0, bw))
        for x in range(-bw, S + bw, bw):
            col = hsv(hue + rng.uniform(-0.04, 0.04), rng.uniform(0.45, 0.95),
                      rng.uniform(0.25, 0.95))
            d.rectangle([x + off + 3, y + 3, x + off + bw - 3, y + bh - 3], fill=col)
    style = i % 4
    for _ in range(int(rng.integers(40, 90))):
        x, y = (int(v) for v in rng.integers(0, S, 2))
        s = int(rng.integers(12, 70))
        c = hsv(hue + 0.5 + rng.uniform(-0.1, 0.1), 0.9, rng.choice([0.05, 0.98]))
        if style == 0:
            d.rectangle([x, y, x + s, y + s], outline=c, width=4)
        elif style == 1:
            d.polygon([(x, y), (x + s, y), (x + s // 2, y + s)], fill=c)
        elif style == 2:
            d.line([x, y, x + s * 2, y + int(rng.integers(-s, s))], fill=c, width=5)
        else:
            d.ellipse([x, y, x + s, y + s // 2 + 8], outline=c, width=4)
    return img


def floor(i):
    rng = np.random.default_rng(5000 + i)
    S = 2048
    tile = [128, 256, 170, 512][i]
    hue = [0.08, 0.55, 0.30, 0.95][i]
    img = Image.new('RGB', (S, S))
    d = ImageDraw.Draw(img)
    for ty in range(0, S, tile):
        for tx in range(0, S, tile):
            v = rng.uniform(0.35, 0.85)
            d.rectangle([tx, ty, tx + tile, ty + tile],
                        fill=hsv(hue + rng.uniform(-0.03, 0.03), rng.uniform(0.15, 0.5), v))
            d.rectangle([tx, ty, tx + tile, ty + tile], outline=hsv(hue, 0.2, 0.15), width=4)
    for _ in range(250):
        x, y = (int(v) for v in rng.integers(0, S, 2))
        s = int(rng.integers(8, 40))
        d.rectangle([x, y, x + s, y + s], fill=hsv(hue + 0.4, 0.8, rng.choice([0.1, 0.95])))
    return img


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'worlds', 'textures')
    os.makedirs(out, exist_ok=True)
    for i in range(N_WALL):
        wall(i).save(os.path.join(out, 'wall_%02d.png' % i))
    for i in range(N_FLOOR):
        floor(i).save(os.path.join(out, 'floor_%d.png' % i))


if __name__ == '__main__':
    main()
