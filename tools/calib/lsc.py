#!/usr/bin/env python3
"""Lens shading table from raw frames of an evenly lit white sheet filling the view (calibration tool, not part of the image).

The frames are averaged, the black level taken off, and for every cell of the grid and every Bayer position of the quad the
gain that brings it to the level of the centre is computed (so the table also corrects the colour shading: each position is
compared with itself in the middle). The result is the "Lsc" entry of the tuning file (see patches/libcamera/0006-ipu3-lsc.patch):
gains as 12-bit fixed point, 4096 = 1.0, for the four positions of the quad in raster order.

usage: lsc.py --size WxH --black N --ct CT [--cell 64] frame.bin [frame.bin ...]   prints a YAML "sets" entry and a summary
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ipu3raw import planes, unpack  # noqa: E402


def smooth(grid, passes=2):
    """3x3 box blur with edge padding, a few times: the white sheet is never perfect and the gains should vary slowly."""
    for _ in range(passes):
        p = np.pad(grid, 1, mode="edge")
        grid = sum(p[y:y + grid.shape[0], x:x + grid.shape[1]] for y in range(3) for x in range(3)) / 9.0
    return grid


def table(frames, width, height, black, cell):
    img = np.mean([unpack(f, width, height).astype(np.float64) for f in frames], axis=0) - black
    img = np.clip(img, 1.0, None)
    half = cell // 2                       # a cell of the array is cell/2 samples of each Bayer plane
    cols, rows = -(-width // cell), -(-height // cell)
    out = []
    for plane in planes(img):
        grid = np.zeros((rows, cols))
        for r in range(rows):
            for c in range(cols):
                block = plane[r * half:(r + 1) * half, c * half:(c + 1) * half]
                grid[r, c] = np.median(block) if block.size else np.nan
        grid = smooth(grid)
        centre = np.median(grid[rows // 2 - 1:rows // 2 + 1, cols // 2 - 1:cols // 2 + 1])
        out.append(np.clip(centre / grid, 1.0, 3.99))
    return cols, rows, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", required=True)
    ap.add_argument("--black", type=float, required=True, help="black level in 10-bit units")
    ap.add_argument("--ct", type=int, required=True, help="white point key of the light (see ccm.py)")
    ap.add_argument("--cell", type=int, default=64)
    ap.add_argument("frames", nargs="+")
    a = ap.parse_args()
    width, height = map(int, a.size.split("x"))
    cols, rows, gains = table([open(f, "rb").read() for f in a.frames], width, height, a.black, a.cell)
    print("# lens shading: %dx%d cells of %d pixels; corner gains %s" % (
        cols, rows, a.cell, ", ".join("%.2f" % g[0, 0] for g in gains)), file=sys.stderr)
    print("      - ct: %d" % a.ct)
    for i, g in enumerate(gains):
        print("        c%d: [ %s ]" % (i, ", ".join(str(int(round(v * 4096))) for v in g.ravel())))


if __name__ == "__main__":
    main()
