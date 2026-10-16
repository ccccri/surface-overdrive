#!/usr/bin/env python3
"""Colour correction matrix from a raw frame of the colour chart page shown full screen on another display (calibration tool,
not part of the image).

The chart (tools/calib/chart.html) is 6 x 4 patches with known sRGB values, the bottom row neutral. The four corners of the
patch area are given in pixels of the raw frame (top left, top right, bottom right, bottom left: read them off a preview).
For every patch the middle half is averaged per Bayer position, the lens shading table (optional) and the black level taken
off; the neutral patches give the white balance; then the 3x3 matrix from white-balanced camera RGB to linear sRGB is fitted
by least squares, each row summing to 1 so that greys stay grey. Printed as the "ccms" entry of the Awb algorithm (see
patches/libcamera/0004-ipu3-ccm.patch), with its "ct": 1000 * ln((B/G) / (R/G)) + 5000 of the white point.

usage: ccm.py --size WxH --black N --cfa BGGR --corners x0,y0,x1,y1,x2,y2,x3,y3 frame.bin
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ipu3raw import unpack  # noqa: E402

# sRGB values of the patches, row by row: the colours of the classic 24-patch chart (approximate published sRGB values)
CHART = [
    (115, 82, 68), (194, 150, 130), (98, 122, 157), (87, 108, 67), (133, 128, 177), (103, 189, 170),
    (214, 126, 44), (80, 91, 166), (193, 90, 99), (94, 60, 108), (157, 188, 64), (224, 163, 46),
    (56, 61, 150), (70, 148, 73), (175, 54, 60), (231, 199, 31), (187, 86, 149), (8, 133, 161),
    (243, 243, 242), (200, 200, 200), (160, 160, 160), (122, 122, 121), (85, 85, 85), (52, 52, 52),
]


def linear(v):
    v = np.asarray(v, dtype=np.float64) / 255.0
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def patch_points(corners, cols=6, rows=4):
    """Centre of every patch, by bilinear interpolation between the four corners of the patch area."""
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = corners
    pts = []
    for r in range(rows):
        v = (r + 0.5) / rows
        for c in range(cols):
            u = (c + 0.5) / cols
            top = (x0 + (x1 - x0) * u, y0 + (y1 - y0) * u)
            bottom = (x3 + (x2 - x3) * u, y3 + (y2 - y3) * u)
            pts.append((top[0] + (bottom[0] - top[0]) * v, top[1] + (bottom[1] - top[1]) * v))
    return pts


def camera_rgb(img, cfa, x, y, radius):
    """Mean R, G, B around (x, y) of the raw image, from the Bayer quads in a square of the given radius."""
    x0, y0 = int(x - radius) & ~1, int(y - radius) & ~1
    block = img[y0:y0 + 2 * radius, x0:x0 + 2 * radius]
    pos = {(0, 0): cfa[0], (0, 1): cfa[1], (1, 0): cfa[2], (1, 1): cfa[3]}
    sums = {"R": [], "G": [], "B": []}
    for (dy, dx), colour in pos.items():
        sums[colour].append(block[dy::2, dx::2].mean())
    return np.array([np.mean(sums["R"]), np.mean(sums["G"]), np.mean(sums["B"])])


def fit(cam, ref):
    """3x3 matrix M with rows summing to 1, minimising |M cam - ref|."""
    m = np.zeros((3, 3))
    for row in range(3):
        # m[row] = (a, b, 1 - a - b): solve for a, b
        a = np.stack([cam[:, 0] - cam[:, 2], cam[:, 1] - cam[:, 2]], axis=1)
        b = ref[:, row] - cam[:, 2]
        (p, q), *_ = np.linalg.lstsq(a, b, rcond=None)
        m[row] = (p, q, 1 - p - q)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", required=True)
    ap.add_argument("--black", type=float, required=True)
    ap.add_argument("--cfa", default="BGGR", help="colours of the quad in raster order")
    ap.add_argument("--corners", required=True)
    ap.add_argument("frame")
    a = ap.parse_args()
    width, height = map(int, a.size.split("x"))
    img = unpack(open(a.frame, "rb").read(), width, height).astype(np.float64) - a.black
    v = [float(n) for n in a.corners.split(",")]
    corners = list(zip(v[0::2], v[1::2]))
    pts = patch_points(corners)
    side = abs(corners[1][0] - corners[0][0]) / 6
    cam = np.array([camera_rgb(img, a.cfa, x, y, max(4, int(side / 4))) for x, y in pts])
    ref = linear(CHART)
    neutral = cam[18:24]
    wb = neutral[:, 1].sum() / neutral.sum(axis=0)              # gains that make the greys grey
    balanced = cam * wb
    scale = (ref[18:24, 1].sum() / balanced[18:24, 1].sum())     # exposure: match the greys' level
    balanced *= scale
    m = fit(balanced, ref)
    err = np.abs(balanced @ m.T - ref).mean()
    rg, bg = 1 / wb[0], 1 / wb[2]
    ct = int(round(1000 * np.log(bg / rg))) + 5000
    print("# white balance gains R %.3f B %.3f, mean error %.4f (linear)" % (wb[0], wb[2], err), file=sys.stderr)
    print("      - ct: %d" % ct)
    print("        ccm: [ %s ]" % ", ".join("%.4f" % x for x in m.ravel()))


if __name__ == "__main__":
    main()
