#!/usr/bin/env python3
"""Colour correction matrix from the colours of the chart shown one at a time on the whole laptop screen (calibration tool,
run on the PC; the screen is driven by screen.py, the tablet over ssh).

For every colour of the chart (ccm.CHART) the screen shows it, the camera takes a raw frame and the middle of the frame
is averaged per Bayer position: every colour is measured on the optical axis, so the lens shading, the screen's fall-off
with the viewing angle and the camera's distance do not enter. The fit is the one of ccm.py (white balance from the
neutrals, then a matrix with rows summing to 1, each colour free in brightness). Prints the "ccms" entry and keeps the
measurements in build/<name>.json.

A colour that reaches the top of the raw range is taken again with a lower exposure target (a saturated blue or red is
exposed for its brightness, which is mostly green, and clips in its own channel); --only measures some colours again into
an existing build/<name>.json.

usage: ccm_screen.py <1=rear|2=front> [--black 16] [--cfa BGGR] [--name ccm-rear] [--only 9 12 ...]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ccm import CHART, fit, linear  # noqa: E402
from ipu3raw import unpack  # noqa: E402

SIZES = {"1": (3264, 2448), "2": (2592, 1944)}
HOST = "cri@192.168.0.96"


def encode(v):
    """Linear values (0-1) to sRGB codes (0-255)."""
    v = np.clip(v, 0, 1)
    return 255 * np.where(v <= 0.0031308, 12.92 * v, 1.055 * v ** (1 / 2.4) - 0.055)


def show(rgb):
    subprocess.run([sys.executable, str(Path(__file__).with_name("screen.py")), "set"] + [str(v) for v in rgb], check=True)


CLIP = 1000          # raw codes above which a pixel may be clipped (10-bit, black included)


def capture(camera, target):
    subprocess.run(["ssh", HOST, "bash /var/tmp/capture.sh %s ccm %g >/dev/null" % (camera, target)], check=True)
    return subprocess.run(["ssh", HOST, "cat /var/tmp/calib/ccm.raw"], check=True, capture_output=True).stdout


def centre_rgb(data, width, height, black, cfa):
    img = unpack(data, width, height).astype(np.float64) - black
    h, w = height // 10 * 2, width // 10 * 2              # the middle fifth of each side
    y0, x0 = (height - h) // 2 & ~1, (width - w) // 2 & ~1
    block = img[y0:y0 + h, x0:x0 + w]
    sums = {"R": [], "G": [], "B": []}
    for (dy, dx), colour in zip(((0, 0), (0, 1), (1, 0), (1, 1)), cfa):
        sums[colour].append(block[dy::2, dx::2].mean())
    return [float(np.mean(sums[c])) for c in "RGB"], float(block.max() + black)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("camera", choices=SIZES)
    ap.add_argument("--black", type=float, default=16)
    ap.add_argument("--cfa", default="BGGR")
    ap.add_argument("--name", default="ccm-rear")
    ap.add_argument("--only", nargs="+", type=int, help="colours to measure again")
    ap.add_argument("--dim", type=float, default=1.0,
                    help="show the colours at this fraction of their light (same chromaticity): for colours that clip even at "
                         "the shortest exposure; the fit only uses the colour, not the brightness")
    a = ap.parse_args()
    width, height = SIZES[a.camera]
    out = Path("build/%s.json" % a.name)

    cam = json.loads(out.read_text())["camera"] if a.only else [None] * len(CHART)
    for n, rgb in enumerate(CHART):
        if a.only and n not in a.only:
            continue
        shown = rgb if a.dim == 1.0 else tuple(int(round(v)) for v in encode(linear(rgb) * a.dim))
        show(shown)
        target = 0.08
        while True:
            value, peak = centre_rgb(capture(a.camera, target), width, height, a.black, a.cfa)
            if peak < CLIP or target < 0.01:
                break
            target /= 2
        cam[n] = value
        print("%2d %-15s camera %6.1f %6.1f %6.1f  peak %4.0f  target %g" % (n, rgb, *value, peak, target), file=sys.stderr)
    show((0, 0, 0))
    out.write_text(json.dumps({"chart": CHART, "camera": cam}, indent=1))

    cam = np.array(cam)
    ref = linear(CHART)
    neutral = cam[18:24]
    wb = neutral[:, 1].sum() / neutral.sum(axis=0)
    balanced = cam * wb
    luma = np.array([0.2126, 0.7152, 0.0722])
    # every colour was exposed on its own, so only its colour counts: fit, bring each to its reference luminance, fit again
    balanced *= ((ref @ luma) / (balanced @ luma))[:, None]
    m = fit(balanced, ref)
    for _ in range(20):
        balanced *= ((ref @ luma) / ((balanced @ m.T) @ luma))[:, None]
        m = fit(balanced, ref)
    err = balanced @ m.T - ref
    for i, e in enumerate(err):
        print("# colour %2d  error %s" % (i, " ".join("%+.3f" % v for v in e)), file=sys.stderr)
    rg, bg = 1 / wb[0], 1 / wb[2]
    ct = int(round(1000 * np.log(bg / rg))) + 5000
    print("# white balance gains R %.3f B %.3f, mean error %.4f (linear)" % (wb[0], wb[2], np.abs(err).mean()), file=sys.stderr)
    print("      - ct: %d" % ct)
    print("        ccm: [ %s ]" % ", ".join("%.4f" % x for x in m.ravel()))


if __name__ == "__main__":
    main()
