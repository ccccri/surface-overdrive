#!/usr/bin/env python3
"""Lens shading calibration in one sitting (calibration tool, run on the PC, drives the tablet over ssh).

With the camera held still against an evenly lit white (a sheet on the lens, pointed at a window): capture raw frames and
compute the table (lsc.py); then close the loop on the processed picture, which is what people see: the colour matrix
amplifies the few per cent the raw table leaves and the tone curve bends them, so the remaining tint and brightness of every
part of the picture against the centre are measured and folded back into the table, a few times, until it is flat.
Writes the tuning file with the new Lsc entry to <out>/tuning.yaml.

Kept for its helpers (processed(), flatness(), with_lsc(), used by shading_probe.py): the loop itself folds whatever the
flat has (light falling off across a window, a diffuser's tint) into the table, so the tables of the image come from raw
frames only (lsc.py, lsc_colour.py) and are checked with shading_probe.py.

usage: flat_auto.py <1=rear|2=front> <tuning.yaml> [--cfa BGGR] [--host cri@192.168.0.96] [--black 16] [--ct 5300]
"""
import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lsc import table  # noqa: E402

SIZES = {"1": (3264, 2448), "2": (2592, 1944)}
PREVIEW = (1536, 1152)
REMOTE = "/var/tmp/calib"
ROUNDS = 4
GOAL = 0.02          # worst colour deviation from the centre that counts as flat
# The processed picture is the linear one through the colour matrix (which roughly doubles a tint) and a ~1/2.2 curve:
# the exponents turn a measured ratio into the change of gain that removes it, damped a little so the loop converges.
COLOUR_EXP = 0.5
BRIGHT_EXP = 1.2
GRID = (16, 12)      # columns, rows of the regions measured on the processed picture
MAX_GAIN = 4.9       # the shading block takes 1.0 to 4.99


def sh(host, cmd, **kw):
    return subprocess.run(["ssh", host, cmd], check=True, **kw)


def lsc_block(cols, rows, gains, ct):
    lines = ["  - Lsc:", "      cell: 64", "      grid: [ %d, %d ]" % (cols, rows), "      sets:", "      - ct: %d" % ct]
    for i, g in enumerate(gains):
        lines.append("        c%d: [ %s ]" % (i, ", ".join(str(int(round(v * 4096))) for v in g.ravel())))
    return "\n".join(lines) + "\n"


def with_lsc(tuning, block):
    """The tuning file with its Lsc entry replaced by (or, if it has none, added before BlackLevelCorrection) the given one."""
    out, skip = [], False
    for line in tuning.splitlines(keepends=True):
        if line.startswith("  - "):
            skip = line.strip() == "- Lsc:"
            if skip:
                out.append(block)
                continue
        if not skip:
            out.append(line)
    text = "".join(out)
    return text if block in text else text.replace("  - BlackLevelCorrection:", block + "  - BlackLevelCorrection:", 1)


def processed(host, camera, text, size=PREVIEW):
    """Last viewfinder frame of a short run with the given tuning and stream size, as float RGB."""
    subprocess.run(["ssh", host, "cat > %s/try.yaml" % REMOTE], input=text.encode(), check=True)
    sh(host, "cd %s && systemctl --user stop wireplumber; rm -f pv-*; LIBCAMERA_IPU3_TUNING_FILE=%s/try.yaml timeout 60 "
             "cam -c %s -s role=viewfinder,width=%d,height=%d -C30 --file=pv-#.nv12 >/dev/null 2>&1; "
             "mv $(ls pv-* | tail -1) pv.nv12; rm -f pv-0*" % (REMOTE, REMOTE, camera, size[0], size[1]))
    nv12 = subprocess.run(["ssh", host, "cat %s/pv.nv12" % REMOTE], check=True, capture_output=True).stdout
    w, h = size
    d = np.frombuffer(nv12, np.uint8)
    y = d[:w * h].reshape(h, w).astype(float)
    uv = d[w * h:w * h * 3 // 2].reshape(h // 2, w // 2, 2).astype(float) - 128
    u = uv[..., 0].repeat(2, 0).repeat(2, 1)
    v = uv[..., 1].repeat(2, 0).repeat(2, 1)
    return np.clip(np.stack([y + 1.402 * v, y - 0.344 * u - 0.714 * v, y + 1.772 * u], -1), 1, 255)


def regions(img):
    """Mean R, G, B of every region of the grid, and of the centre."""
    h, w, _ = img.shape
    gx, gy = GRID
    m = img[:h // gy * gy, :w // gx * gx].reshape(gy, h // gy, gx, w // gx, 3).mean((1, 3))
    s = 100
    c = img[h // 2 - s // 2:h // 2 + s // 2, w // 2 - s // 2:w // 2 + s // 2].reshape(-1, 3).mean(0)
    return m, c


def flatness(img):
    """Worst deviation of a region from the centre: colour (R/G, B/G) and brightness, as fractions, and the corners."""
    m, c = regions(img)
    rg = (m[..., 0] / m[..., 1]) / (c[0] / c[1]) - 1
    bg = (m[..., 2] / m[..., 1]) / (c[2] / c[1]) - 1
    y = m[..., 1] / c[1] - 1
    corners = {"TL": (0, 0), "TR": (0, -1), "BL": (-1, 0), "BR": (-1, -1)}
    detail = " ".join("%s %+.0f%%r %+.0f%%b %+.0f%%y" % (k, 100 * rg[p], 100 * bg[p], 100 * y[p]) for k, p in corners.items())
    return max(np.abs(rg).max(), np.abs(bg).max()), np.abs(y).max(), detail


def resample(grid, cols, rows):
    """A map of region values to the cells of the calibration table (bilinear between region centres, edges held)."""
    gy, gx = grid.shape
    xs = (np.arange(cols) + 0.5) / cols * gx - 0.5
    ys = (np.arange(rows) + 0.5) / rows * gy - 0.5
    across = np.array([np.interp(xs, np.arange(gx), row) for row in grid])
    return np.array([np.interp(ys, np.arange(gy), col) for col in across.T]).T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("camera", choices=SIZES)
    ap.add_argument("tuning")
    ap.add_argument("--cfa", default="BGGR", help="colours of the quad in raster order")
    ap.add_argument("--host", default="cri@192.168.0.96")
    ap.add_argument("--black", type=float, default=16, help="sensor black level for the raw table, 10-bit")
    ap.add_argument("--ct", type=int, default=5300)
    ap.add_argument("--out", default="build/flat")
    ap.add_argument("--reuse", action="store_true", help="use the raw frames already on the tablet")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    width, height = SIZES[a.camera]
    r_plane, b_plane = a.cfa.index("R"), a.cfa.index("B")

    if not a.reuse:
        print("raw frames...", file=sys.stderr)
        sh(a.host, "for n in 1 2 3; do bash /var/tmp/capture.sh %s flat$n 0.35 >/dev/null; done" % a.camera)
    frames = [subprocess.run(["ssh", a.host, "cat %s/flat%d.raw" % (REMOTE, n)], check=True, capture_output=True).stdout
              for n in (1, 2, 3)]
    cols, rows, gains = table(frames, width, height, a.black, 64)
    print("table %dx%d, corner gains %s" % (cols, rows, ", ".join("%.2f" % g[0, 0] for g in gains)), file=sys.stderr)

    base = Path(a.tuning).read_text()
    best = None
    for n in range(ROUNDS + 1):
        text = with_lsc(base, lsc_block(cols, rows, gains, a.ct))
        img = processed(a.host, a.camera, text)
        colour, bright, detail = flatness(img)
        print("round %d: colour %.1f%% brightness %.1f%%   %s" % (n, 100 * colour, 100 * bright, detail), file=sys.stderr)
        if best is None or colour + bright / 2 < best[0]:     # a round that made it worse is not kept
            best = (colour + bright / 2, n, text)
        if colour < GOAL or n == ROUNDS:
            break
        m, c = regions(img)
        rg = resample((m[..., 0] / m[..., 1]) / (c[0] / c[1]), cols, rows)
        bg = resample((m[..., 2] / m[..., 1]) / (c[2] / c[1]), cols, rows)
        y = resample(m[..., 1] / c[1], cols, rows)
        for i in range(4):
            gains[i] = gains[i] * y ** -BRIGHT_EXP
        gains[r_plane] *= rg ** -COLOUR_EXP
        gains[b_plane] *= bg ** -COLOUR_EXP
        low = min(g.min() for g in gains)                 # keep every gain at 1.0 or above, the block cannot attenuate
        gains = [np.clip(g / low, 1.0, MAX_GAIN) for g in gains]
    sh(a.host, "systemctl --user start wireplumber")
    (out / "tuning.yaml").write_text(best[2])
    print("written %s (round %d)" % (out / "tuning.yaml", best[1]), file=sys.stderr)


if __name__ == "__main__":
    main()
