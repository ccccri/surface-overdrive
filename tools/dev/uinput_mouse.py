#!/usr/bin/env python3
"""Click with a virtual mouse (/dev/uinput) that points at absolute screen positions. Development tool, needs root.

A click makes the window under it the active one and gives the keyboard focus to what was clicked, which the virtual finger of
uinput_touch.py does not do reliably from a remote session.

usage: uinput_mouse.py SCREEN_W SCREEN_H    then commands on standard input, one per line, coordinates in screen pixels:
  click X Y
  drag X1 Y1 X2 Y2      press, move in about a third of a second, release
  move X Y
  wait SECONDS
"""
import fcntl
import os
import struct
import sys
import time

EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
ABS_X, ABS_Y = 0, 1
BTN_LEFT = 0x110
UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_ABSBIT = 0x40045564, 0x40045565, 0x40045567
UI_DEV_SETUP, UI_ABS_SETUP, UI_DEV_CREATE, UI_DEV_DESTROY = 0x405C5503, 0x401C5504, 0x5501, 0x5502
RANGE = 20000          # device units per axis


def emit(fd, etype, code, value):
    os.write(fd, struct.pack("llHHi", 0, 0, etype, code, value))


class Mouse:
    def __init__(self, width, height):
        self.w, self.h = width, height
        fd = self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
        fcntl.ioctl(fd, UI_SET_EVBIT, EV_ABS)
        fcntl.ioctl(fd, UI_SET_KEYBIT, BTN_LEFT)
        for code in (ABS_X, ABS_Y):
            fcntl.ioctl(fd, UI_SET_ABSBIT, code)
            fcntl.ioctl(fd, UI_ABS_SETUP, struct.pack("HHiiiiii", code, 0, 0, 0, RANGE, 0, 0, 0))
        fcntl.ioctl(fd, UI_DEV_SETUP, struct.pack("HHHH80sI", 0x06, 0x1234, 0x567A, 1, b"Overdrive test mouse", 0))
        fcntl.ioctl(fd, UI_DEV_CREATE)
        time.sleep(1.5)        # the compositor needs a moment to take the new device

    def move(self, x, y):
        emit(self.fd, EV_ABS, ABS_X, int(x * RANGE / self.w))
        emit(self.fd, EV_ABS, ABS_Y, int(y * RANGE / self.h))
        emit(self.fd, EV_SYN, 0, 0)
        time.sleep(0.02)

    def button(self, down):
        emit(self.fd, EV_KEY, BTN_LEFT, 1 if down else 0)
        emit(self.fd, EV_SYN, 0, 0)
        time.sleep(0.06)

    def click(self, x, y):
        self.move(x - 2, y - 2)
        self.move(x, y)
        self.button(True)
        self.button(False)

    def drag(self, x1, y1, x2, y2):
        self.move(x1 - 2, y1 - 2)
        self.move(x1, y1)
        self.button(True)
        for i in range(1, 21):
            self.move(x1 + (x2 - x1) * i / 20, y1 + (y2 - y1) * i / 20)
        self.button(False)

    def close(self):
        fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        os.close(self.fd)


def main():
    mouse = Mouse(int(sys.argv[1]), int(sys.argv[2]))
    try:
        for line in sys.stdin:
            words = line.split()
            if not words:
                continue
            numbers = [float(w) for w in words[1:]]
            if words[0] == "click":
                mouse.click(*numbers)
            elif words[0] == "drag":
                mouse.drag(*numbers)
            elif words[0] == "move":
                mouse.move(*numbers)
            elif words[0] == "wait":
                time.sleep(numbers[0])
            sys.stdout.write("done %s\n" % line.strip())
            sys.stdout.flush()
    finally:
        mouse.close()


if __name__ == "__main__":
    main()
