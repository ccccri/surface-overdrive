#!/usr/bin/env python3
"""Scroll with a virtual mouse wheel (/dev/uinput), to look at the lower part of a settings page in screenshots. Development tool, needs root.

usage: uinput_scroll.py <x> <y> <clicks>     moves the pointer to (x, y) from the top-left corner, then turns the wheel (negative = up)
"""
import fcntl
import os
import struct
import sys
import time

EV_SYN, EV_REL = 0x00, 0x02
REL_X, REL_Y, REL_WHEEL = 0, 1, 8
UI_SET_EVBIT, UI_SET_RELBIT = 0x40045564, 0x40045566
UI_DEV_SETUP, UI_DEV_CREATE, UI_DEV_DESTROY = 0x405C5503, 0x5501, 0x5502


def emit(fd, t, c, v):
    os.write(fd, struct.pack("llHHi", 0, 0, t, c, v))


def main():
    x, y, clicks = (int(a) for a in sys.argv[1:4])
    fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_REL)
    for r in (REL_X, REL_Y, REL_WHEEL):
        fcntl.ioctl(fd, UI_SET_RELBIT, r)
    fcntl.ioctl(fd, UI_DEV_SETUP, struct.pack("HHHH80sI", 0x03, 0x1209, 0x0002, 1, b"Surface Overdrive virtual mouse", 0))
    fcntl.ioctl(fd, UI_DEV_CREATE)
    try:
        time.sleep(1)
        for _ in range(60):                         # to the corner
            emit(fd, EV_REL, REL_X, -100); emit(fd, EV_REL, REL_Y, -100); emit(fd, EV_SYN, 0, 0)
        for _ in range(x // 10):
            emit(fd, EV_REL, REL_X, 10); emit(fd, EV_SYN, 0, 0)
        for _ in range(y // 10):
            emit(fd, EV_REL, REL_Y, 10); emit(fd, EV_SYN, 0, 0)
        time.sleep(0.3)
        step = 1 if clicks > 0 else -1
        for _ in range(abs(clicks)):
            emit(fd, EV_REL, REL_WHEEL, -step); emit(fd, EV_SYN, 0, 0)
            time.sleep(0.05)
        time.sleep(0.5)
    finally:
        fcntl.ioctl(fd, UI_DEV_DESTROY)
        os.close(fd)


if __name__ == "__main__":
    main()
