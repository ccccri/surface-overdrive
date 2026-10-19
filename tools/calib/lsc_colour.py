#!/usr/bin/env python3
"""Lens shading table with its brightness from one flat and its colour from another (calibration tool).

A flat seen through a diffuser (a sheet on the laptop screen, the camera pressed against it) has an even brightness but not
an even colour: light leaving the paper at a slant is warmer, so the corners look redder than they are. A matt white sheet
lit from the front by a single kind of light (a window) has an even colour but not an even brightness. The table takes the
green gains of the first and, for red and blue, the colour fall-off of the second relative to green, fitted with a smooth
surface whose tilt (x and y terms: one side of the sheet nearer the window) is dropped, so that only the lens is left.

usage: lsc_colour.py --brightness flat.bin --colour sheet.bin --size WxH --black N --cfa BGGR > sets-entry
       (each .bin: raw frames one after the other)
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ipu3raw import unpack  # noqa: E402
from lsc import table  # noqa: E402


def frames(path, width, height):
    data = Path(path).read_bytes()
    n = (width + 49) // 50 * 64 * height
    return [data[i:i + n] for i in range(0, len(data), n)]


def cell_means(raws, width, height, black, cell):
    img = np.mean([unpack(f, width, height).astype(np.float64) for f in raws], axis=0) - black
    half = cell // 2
    cols, rows = -(-width // cell), -(-height // cell)
    out = []
    for dy, dx in ((0, 0), (0, 1), (1, 0), (1, 1)):
        plane = img[dy::2, dx::2]
        grid = np.full((rows, cols), np.nan)
        for r in range(rows):
            for c in range(cols):
                block = plane[r * half:(r + 1) * half, c * half:(c + 1) * half]
                if block.size:
                    grid[r, c] = np.median(block)
        out.append(grid)
    return out


def radial_fit(values, cols, rows):
    """Smooth fit of log(values) over the grid with 1, x, y, x2, y2, xy, r4, r6; returned without the x and y terms."""
    y, x = np.mgrid[0:rows, 0:cols]
    x = (x + 0.5) / cols * 2 - 1
    y = ((y + 0.5) / rows * 2 - 1) * rows / cols
    r2 = x * x + y * y
    terms = [np.ones_like(x), x, y, x * x, y * y, x * y, r2 * r2, r2 * r2 * r2]
    a = np.stack([t.ravel() for t in terms], axis=1)
    ok = np.isfinite(values.ravel()) & (values.ravel() > 0)
    coef, *_ = np.linalg.lstsq(a[ok], np.log(values.ravel()[ok]), rcond=None)
    coef[1] = coef[2] = 0.0
    return np.exp(sum(c * t for c, t in zip(coef, terms)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brightness", required=True)
    ap.add_argument("--colour", required=True)
    ap.add_argument("--size", required=True)
    ap.add_argument("--black", type=float, default=16)
    ap.add_argument("--cfa", default="BGGR")
    ap.add_argument("--ct", type=int, default=5300)
    ap.add_argument("--cell", type=int, default=64)
    a = ap.parse_args()
    width, height = map(int, a.size.split("x"))
    cols, rows, gains = table(frames(a.brightness, width, height), width, height, a.black, a.cell)
    planes = cell_means(frames(a.colour, width, height), width, height, a.black, a.cell)
    green = [i for i, c in enumerate(a.cfa) if c == "G"]
    g = (planes[green[0]] + planes[green[1]]) / 2
    for i, c in enumerate(a.cfa):
        if c == "G":
            continue
        ratio = radial_fit(planes[i] / g, cols, rows)
        ratio /= ratio[rows // 2 - 1:rows // 2 + 1, cols // 2 - 1:cols // 2 + 1].mean()
        green_gain = (gains[green[0]] + gains[green[1]]) / 2
        gains[i] = np.clip(green_gain / ratio, 1.0, 4.9)
    print("# corner gains %s" % ", ".join("%.2f" % gg[0, 0] for gg in gains), file=sys.stderr)
    print("      - ct: %d" % a.ct)
    for i, gg in enumerate(gains):
        print("        c%d: [ %s ]" % (i, ", ".join(str(int(round(v * 4096))) for v in gg.ravel())))


if __name__ == "__main__":
    main()
