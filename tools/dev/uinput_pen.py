#!/usr/bin/env python3
"""Draw with a virtual pen (/dev/uinput), to test the Pen page without a person holding the real pen. Development tool, needs root.

usage: uinput_pen.py SCREEN_W SCREEN_H    then commands on standard input, one per line, coordinates in screen pixels:
  circle CX CY R        a circle drawn with pressure going from light to full
  line X1 Y1 X2 Y2      a straight line at half pressure
  erase X1 Y1 X2 Y2     the same with the eraser end
  barrel X Y SECONDS    hover at X Y holding the side button
  hover X Y SECONDS     hover without touching
"""
import fcntl
import math
import os
import struct
import sys
import time

EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
ABS_X, ABS_Y, ABS_PRESSURE, ABS_TILT_X, ABS_TILT_Y = 0, 1, 0x18, 0x1A, 0x1B
BTN_TOOL_PEN, BTN_TOOL_RUBBER, BTN_TOUCH, BTN_STYLUS = 0x140, 0x141, 0x14A, 0x14B
INPUT_PROP_DIRECT = 1
UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_ABSBIT, UI_SET_PROPBIT = 0x40045564, 0x40045565, 0x40045567, 0x4004556E
UI_DEV_SETUP, UI_ABS_SETUP, UI_DEV_CREATE, UI_DEV_DESTROY = 0x405C5503, 0x401C5504, 0x5501, 0x5502
RANGE = 20000          # device units per axis
PRESSURE = 4096


def emit(fd, etype, code, value):
    os.write(fd, struct.pack("llHHi", 0, 0, etype, code, value))


class Pen:
    def __init__(self, width, height):
        self.w, self.h = width, height
        fd = self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
        fcntl.ioctl(fd, UI_SET_EVBIT, EV_ABS)
        fcntl.ioctl(fd, UI_SET_PROPBIT, INPUT_PROP_DIRECT)
        for key in (BTN_TOOL_PEN, BTN_TOOL_RUBBER, BTN_TOUCH, BTN_STYLUS):
            fcntl.ioctl(fd, UI_SET_KEYBIT, key)
        # struct uinput_abs_setup { u16 code; struct input_absinfo { s32 value, minimum, maximum, fuzz, flat, resolution; } }
        for code, top, res in ((ABS_X, RANGE, 80), (ABS_Y, int(RANGE * height / width), 80), (ABS_PRESSURE, PRESSURE, 0),
                               (ABS_TILT_X, 90, 57), (ABS_TILT_Y, 90, 57)):
            low = -90 if code in (ABS_TILT_X, ABS_TILT_Y) else 0
            fcntl.ioctl(fd, UI_SET_ABSBIT, code)
            fcntl.ioctl(fd, UI_ABS_SETUP, struct.pack("HHiiiiii", code, 0, 0, low, top, 0, 0, res))
        self.ymax = int(RANGE * height / width)
        fcntl.ioctl(fd, UI_DEV_SETUP, struct.pack("HHHH80sI", 0x03, 0x1209, 0x0002, 1, b"Surface Overdrive virtual pen", 0))
        fcntl.ioctl(fd, UI_DEV_CREATE)
        time.sleep(2.0)
        self.tool = None

    def close(self):
        self.away()
        time.sleep(0.2)
        fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        os.close(self.fd)

    def point(self, x, y, pressure=0.0, tool=BTN_TOOL_PEN, barrel=False, tilt=(0, 0)):
        fd = self.fd
        if self.tool != tool:
            self.away()
            emit(fd, EV_KEY, tool, 1)
            self.tool = tool
        emit(fd, EV_ABS, ABS_X, int(x / self.w * RANGE))
        emit(fd, EV_ABS, ABS_Y, int(y / self.h * self.ymax))
        emit(fd, EV_ABS, ABS_PRESSURE, int(pressure * PRESSURE))
        emit(fd, EV_ABS, ABS_TILT_X, tilt[0])
        emit(fd, EV_ABS, ABS_TILT_Y, tilt[1])
        emit(fd, EV_KEY, BTN_TOUCH, 1 if pressure > 0 else 0)
        emit(fd, EV_KEY, BTN_STYLUS, 1 if barrel else 0)
        emit(fd, EV_SYN, 0, 0)
        time.sleep(0.008)

    def away(self):
        if self.tool is not None:
            emit(self.fd, EV_KEY, BTN_TOUCH, 0)
            emit(self.fd, EV_KEY, BTN_STYLUS, 0)
            emit(self.fd, EV_KEY, self.tool, 0)
            emit(self.fd, EV_SYN, 0, 0)
            self.tool = None
            time.sleep(0.1)

    def stroke(self, points, tool=BTN_TOOL_PEN):
        x0, y0, _ = points[0]
        for _ in range(5):
            self.point(x0, y0, 0, tool)
        for x, y, p in points:
            self.point(x, y, p, tool, tilt=(20, -10))
        self.point(points[-1][0], points[-1][1], 0, tool)


def main():
    pen = Pen(int(sys.argv[1]), int(sys.argv[2]))
    try:
        for line in sys.stdin:
            word, *rest = line.split()
            a = [float(v) for v in rest]
            if word == "circle":
                pen.stroke([(a[0] + a[2] * math.cos(t / 100 * 2 * math.pi), a[1] + a[2] * math.sin(t / 100 * 2 * math.pi), 0.1 + 0.9 * t / 100)
                            for t in range(101)])
            elif word in ("line", "erase"):
                pen.stroke([(a[0] + (a[2] - a[0]) * t / 60, a[1] + (a[3] - a[1]) * t / 60, 0.5) for t in range(61)],
                           BTN_TOOL_RUBBER if word == "erase" else BTN_TOOL_PEN)
            elif word in ("barrel", "hover"):
                end = time.monotonic() + a[2]
                step = 0
                while time.monotonic() < end:
                    step += 1                 # a hand never holds still: a few pixels of wobble
                    pen.point(a[0] + 3 * math.sin(step / 3), a[1] + 3 * math.cos(step / 3), 0, barrel=word == "barrel")
                    time.sleep(0.05)
    finally:
        pen.close()


if __name__ == "__main__":
    main()
