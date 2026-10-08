#!/usr/bin/env python3
"""Touch the screen with a virtual finger (/dev/uinput), to test touch behaviour without a person at the tablet. Development tool, needs root.

usage: uinput_touch.py SCREEN_W SCREEN_H    then commands on standard input, one per line, coordinates in screen pixels:
  tap X Y               a short tap
  hold X Y SECONDS      a finger that stays down that long
  swipe X1 Y1 X2 Y2     a drag lasting about a third of a second
  wait SECONDS
"""
import fcntl
import os
import struct
import sys
import time

EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
ABS_X, ABS_Y, ABS_MT_SLOT, ABS_MT_POSITION_X, ABS_MT_POSITION_Y, ABS_MT_TRACKING_ID = 0, 1, 0x2F, 0x35, 0x36, 0x39
BTN_TOUCH = 0x14A
INPUT_PROP_DIRECT = 1
UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_ABSBIT, UI_SET_PROPBIT = 0x40045564, 0x40045565, 0x40045567, 0x4004556E
UI_DEV_SETUP, UI_ABS_SETUP, UI_DEV_CREATE, UI_DEV_DESTROY = 0x405C5503, 0x401C5504, 0x5501, 0x5502
RANGE = 20000          # device units per axis


def emit(fd, etype, code, value):
    os.write(fd, struct.pack("llHHi", 0, 0, etype, code, value))


class Finger:
    def __init__(self, width, height):
        self.w, self.h = width, height
        self.touches = 0
        fd = self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
        fcntl.ioctl(fd, UI_SET_EVBIT, EV_ABS)
        fcntl.ioctl(fd, UI_SET_PROPBIT, INPUT_PROP_DIRECT)
        fcntl.ioctl(fd, UI_SET_KEYBIT, BTN_TOUCH)
        for code, top in ((ABS_X, RANGE), (ABS_Y, RANGE), (ABS_MT_SLOT, 1), (ABS_MT_POSITION_X, RANGE), (ABS_MT_POSITION_Y, RANGE),
                          (ABS_MT_TRACKING_ID, 65535)):
            fcntl.ioctl(fd, UI_SET_ABSBIT, code)
            fcntl.ioctl(fd, UI_ABS_SETUP, struct.pack("HHiiiiii", code, 0, 0, 0, top, 0, 0, 40 if top == RANGE else 0))
        fcntl.ioctl(fd, UI_DEV_SETUP, struct.pack("HHHH80sI", 0x06, 0x1234, 0x5679, 1, b"Overdrive test touchscreen", 0))
        fcntl.ioctl(fd, UI_DEV_CREATE)
        time.sleep(1.5)        # the compositor needs a moment to take the new device

    def move(self, x, y):
        dx, dy = int(x * RANGE / self.w), int(y * RANGE / self.h)
        for code, value in ((ABS_MT_POSITION_X, dx), (ABS_MT_POSITION_Y, dy), (ABS_X, dx), (ABS_Y, dy)):
            emit(self.fd, EV_ABS, code, value)
        emit(self.fd, EV_SYN, 0, 0)

    def down(self, x, y):
        self.touches += 1
        emit(self.fd, EV_ABS, ABS_MT_SLOT, 0)
        emit(self.fd, EV_ABS, ABS_MT_TRACKING_ID, self.touches)
        emit(self.fd, EV_KEY, BTN_TOUCH, 1)
        self.move(x, y)

    def up(self):
        emit(self.fd, EV_ABS, ABS_MT_TRACKING_ID, -1)
        emit(self.fd, EV_KEY, BTN_TOUCH, 0)
        emit(self.fd, EV_SYN, 0, 0)

    def tap(self, x, y):
        self.down(x, y)
        time.sleep(0.08)
        self.up()

    def swipe(self, x1, y1, x2, y2):
        self.down(x1, y1)
        for i in range(1, 21):
            time.sleep(0.016)
            self.move(x1 + (x2 - x1) * i / 20, y1 + (y2 - y1) * i / 20)
        self.up()

    def close(self):
        fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        os.close(self.fd)


def main():
    finger = Finger(int(sys.argv[1]), int(sys.argv[2]))
    try:
        for line in sys.stdin:
            words = line.split()
            if not words:
                continue
            numbers = [float(w) for w in words[1:]]
            if words[0] == "tap":
                finger.tap(*numbers)
            elif words[0] == "hold":
                finger.down(numbers[0], numbers[1])
                time.sleep(numbers[2])
                finger.up()
            elif words[0] == "swipe":
                finger.swipe(*numbers)
            elif words[0] == "wait":
                time.sleep(numbers[0])
            sys.stdout.write("done %s\n" % line.strip())
            sys.stdout.flush()
    finally:
        finger.close()


if __name__ == "__main__":
    main()
