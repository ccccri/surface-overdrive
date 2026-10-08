#!/usr/bin/env python3
"""Print every key and button the kernel reports, with the device it comes from. To see what the buttons of the pen send. Needs root.

usage: sudo input_keys.py [seconds, default 30]
"""
import glob
import os
import select
import struct
import sys
import time

EVENT = struct.Struct("llHHi")
NAMES = {183: "F13", 184: "F14", 185: "F15", 186: "F16", 187: "F17", 188: "F18", 189: "F19", 190: "F20", 191: "F21", 192: "F22",
         193: "F23", 194: "F24", 125: "LEFTMETA", 126: "RIGHTMETA", 0x140: "TOOL_PEN", 0x141: "TOOL_RUBBER", 0x14A: "TOUCH",
         0x14B: "STYLUS (side button)", 0x14C: "STYLUS2"}


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 30
    devices = {}
    for path in sorted(glob.glob("/dev/input/event*")):
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            continue
        name = open("/sys/class/input/%s/device/name" % os.path.basename(path)).read().strip()
        devices[fd] = name
    print("listening on %d devices for %.0f s: press the buttons of the pen" % (len(devices), seconds), flush=True)
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        ready, _, _ = select.select(list(devices), [], [], 0.5)
        for fd in ready:
            try:
                data = os.read(fd, EVENT.size * 64)
            except OSError:
                continue
            for off in range(0, len(data) - EVENT.size + 1, EVENT.size):
                _s, _u, kind, code, value = EVENT.unpack_from(data, off)
                if kind == 1 and value != 2:                 # EV_KEY, not a repeat
                    print("%-34s %-22s %s" % (devices[fd][:34], NAMES.get(code, "key %d" % code), "down" if value else "up"), flush=True)


if __name__ == "__main__":
    main()
