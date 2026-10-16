#!/usr/bin/env python3
"""Read a raw frame of the IPU3 CIO2 (10-bit Bayer packed 25 pixels in 32 bytes, rows padded to a multiple of 64 bytes).
Calibration tool, not part of the image.

usage: ipu3raw.py <file> <width> <height>     prints the mean of each of the four Bayer positions, as a quick look
"""
import sys

import numpy as np


def unpack(data, width, height):
    """2D uint16 array of 10-bit samples."""
    stride = -(-width // 50) * 64
    rows = np.frombuffer(data, dtype=np.uint8)[: stride * height].reshape(height, stride)
    blocks = rows[:, : (stride // 32) * 32].reshape(height, -1, 32)
    bits = np.unpackbits(blocks, axis=2, bitorder="little").reshape(height, blocks.shape[1], 256)[:, :, :250]
    pix = bits.reshape(height, blocks.shape[1], 25, 10)
    values = (pix * (1 << np.arange(10, dtype=np.uint16))).sum(axis=3).astype(np.uint16)
    return values.reshape(height, -1)[:, :width]


def planes(img):
    """The four Bayer positions (0,0) (0,1) (1,0) (1,1) as half-size images."""
    return [img[0::2, 0::2], img[0::2, 1::2], img[1::2, 0::2], img[1::2, 1::2]]


if __name__ == "__main__":
    w, h = int(sys.argv[2]), int(sys.argv[3])
    img = unpack(open(sys.argv[1], "rb").read(), w, h)
    print("min %d max %d" % (img.min(), img.max()))
    for name, p in zip(("00", "01", "10", "11"), planes(img)):
        print(name, "mean %.1f  p1 %.1f  p99 %.1f" % (p.mean(), np.percentile(p, 1), np.percentile(p, 99)))
