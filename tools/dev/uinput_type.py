#!/usr/bin/env python3
"""Type text through a virtual keyboard (/dev/uinput), like a user would on the login screen. Development tool, needs root.

usage: uinput_type.py [--enter] [--delay SECONDS]    the text to type is read from the first line of standard input

Only letters, digits and a few punctuation marks are mapped (US layout key codes: letters and digits sit on the same keys on the
Italian layout too). The text never goes on the command line, so it does not show up in the process list.
"""
import argparse
import fcntl
import os
import struct
import sys
import time

# linux/input-event-codes.h
EV_SYN, EV_KEY = 0x00, 0x01
KEY_ENTER = 28
KEYS = {}
for i, c in enumerate("qwertyuiop"):
    KEYS[c] = 16 + i
for i, c in enumerate("asdfghjkl"):
    KEYS[c] = 30 + i
for i, c in enumerate("zxcvbnm"):
    KEYS[c] = 44 + i
for i, c in enumerate("1234567890"):
    KEYS[c] = 2 + i
KEYS.update({" ": 57, "-": 12, ".": 52, ",": 51})
KEY_LEFTSHIFT = 42

# linux/uinput.h
UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565
UI_DEV_SETUP = 0x405C5503
UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502


def emit(fd, etype, code, value):
    os.write(fd, struct.pack("llHHi", 0, 0, etype, code, value))


def tap(fd, code, shift=False):
    if shift:
        emit(fd, EV_KEY, KEY_LEFTSHIFT, 1)
        emit(fd, EV_SYN, 0, 0)
    emit(fd, EV_KEY, code, 1)
    emit(fd, EV_SYN, 0, 0)
    time.sleep(0.03)
    emit(fd, EV_KEY, code, 0)
    emit(fd, EV_SYN, 0, 0)
    if shift:
        emit(fd, EV_KEY, KEY_LEFTSHIFT, 0)
        emit(fd, EV_SYN, 0, 0)
    time.sleep(0.05)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--enter", action="store_true", help="press Enter after the text")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds to wait after the device is created, so the session picks it up")
    args = ap.parse_args()
    text = sys.stdin.readline().rstrip("\n")
    unknown = sorted({c for c in text if c.lower() not in KEYS})
    if unknown:
        sys.exit(f"cannot type these characters: {unknown}")

    fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
    for code in list(KEYS.values()) + [KEY_ENTER, KEY_LEFTSHIFT]:
        fcntl.ioctl(fd, UI_SET_KEYBIT, code)
    setup = struct.pack("HHHH80sI", 0x03, 0x1209, 0x0001, 1, b"Surface Overdrive virtual keyboard", 0)
    fcntl.ioctl(fd, UI_DEV_SETUP, setup)
    fcntl.ioctl(fd, UI_DEV_CREATE)
    try:
        time.sleep(args.delay)
        for c in text:
            tap(fd, KEYS[c.lower()], shift=c.isupper())
        if args.enter:
            tap(fd, KEY_ENTER)
        time.sleep(0.2)
    finally:
        fcntl.ioctl(fd, UI_DEV_DESTROY)
        os.close(fd)


if __name__ == "__main__":
    main()
