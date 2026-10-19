#!/usr/bin/env python3
"""How the ImgU applies the lens shading table (calibration tool, run on the PC, drives the tablet over ssh).

A neutral flat corrected with the table computed from that same flat has to come out neutral whatever the colour matrix and
the tone curve do (the matrix rows sum to 1), so any tint left in the corners comes from the chain itself. With the camera
held still against the flat (the laptop screen in white through a sheet of paper, see screen.py), this computes the table
from raw frames once and then looks at the processed picture for every combination of stream size (which puts the sensor
and the ImgU in different configurations: binning, BDS scaling), optical black level and exposure target, printing for each
how far the corners are from the centre.

usage: shading_probe.py <1=rear|2=front> <tuning.yaml> [--size 3200x2400 ...] [--optical 16 ...] [--target 0.3 ...]
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flat_auto import REMOTE, SIZES, flatness, lsc_block, processed, sh, with_lsc  # noqa: E402
from lsc import table  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("camera", choices=SIZES)
    ap.add_argument("tuning")
    ap.add_argument("--host", default="cri@192.168.0.96")
    ap.add_argument("--reuse", action="store_true", help="use the raw frames already on the tablet")
    ap.add_argument("--installed", action="store_true", help="keep the Lsc entry of the tuning file instead of a new table")
    ap.add_argument("--save", help="keep the raw frames on the PC under this name (build/<name>.bin)")
    ap.add_argument("--size", nargs="+", default=["1536x1152", "2048x1536", "3200x2400", "1152x864"])
    ap.add_argument("--optical", nargs="+", type=int, default=[32], help="optical black levels to try")
    # a low target by default: a clipped centre hides any difference in brightness
    ap.add_argument("--target", nargs="+", type=float, default=[0.12], help="mean luminance targets of the exposure")
    a = ap.parse_args()
    width, height = SIZES[a.camera]
    if not a.reuse:
        print("raw frames...", file=sys.stderr)
        sh(a.host, "for n in 1 2 3; do bash /var/tmp/capture.sh %s flat$n 0.25 >/dev/null; done" % a.camera)
    frames = [subprocess.run(["ssh", a.host, "cat %s/flat%d.raw" % (REMOTE, n)], check=True, capture_output=True).stdout
              for n in (1, 2, 3)]
    if a.save:
        Path("build/%s.bin" % a.save).write_bytes(b"".join(frames))
    cols, rows, gains = table(frames, width, height, 16, 64)
    base = Path(a.tuning).read_text()
    for size in a.size:
        size = tuple(int(v) for v in size.split("x"))
        for optical in a.optical:
            for target in a.target:
                text = re.sub(r"(?m)^      black: \[ [0-9, ]+ \]$", "      black: [ %d, %d, %d, %d ]" % ((optical,) * 4), base)
                if target is not None:
                    text = re.sub(r"relativeLuminanceTarget: \[ 0, [0-9.]+ \]", "relativeLuminanceTarget: [ 0, %g ]" % target, text)
                    text = re.sub(r"(?ms)^      AeConstraintMode:.*?(?=^  - )", "", text)
                img = processed(a.host, a.camera, text if a.installed else with_lsc(text, lsc_block(cols, rows, gains, 5300)), size)
                colour, bright, detail = flatness(img)
                h, w, _ = img.shape
                print("%dx%d optical %2d target %-4s: centre %3.0f  colour %4.1f%% brightness %4.1f%%   %s" % (
                    size + (optical, target if target is not None else "-", img[h // 2 - 50:h // 2 + 50, w // 2 - 50:w // 2 + 50, 1].mean(),
                            100 * colour, 100 * bright, detail)), file=sys.stderr)
    sh(a.host, "systemctl --user start wireplumber")


if __name__ == "__main__":
    main()
