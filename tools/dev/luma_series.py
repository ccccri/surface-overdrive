#!/usr/bin/env python3
"""Print the mean luma of every frame of a raw GRAY8 dump (development helper).

usage: luma_series.py <width> <height> <file.gray>
Capture with: gst-launch-1.0 -q pipewiresrc target-object=<node> num-buffers=N ! videoconvert ! videoscale ! video/x-raw,format=GRAY8,width=W,height=H ! filesink location=f.gray
"""
import sys
w, h, path = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
d = open(path, "rb").read()
n = len(d) // (w * h)
out = []
for i in range(n):
    f = d[i * w * h:(i + 1) * w * h]
    out.append(sum(f[::7]) / len(f[::7]))
print(" ".join(f"{v:.0f}" for v in out))
