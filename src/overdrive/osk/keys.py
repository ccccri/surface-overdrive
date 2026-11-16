"""Keys of the on-screen keyboard, sent to the system as a keyboard would send them.

The keyboard is a kernel input device made through /dev/uinput (Fedora KDE lets the user at the screen open it: the
udev rule of KDE Connect). What goes out is key codes, and the system turns them into characters with its keyboard
layout, so this table is for the layout in use. Only "us" is here: the prototype says so when the layout is another.
A character the layout cannot type (an accented letter, an emoji) goes through the clipboard instead: it is put there
marked as sensitive (the clipboard history then leaves it out), Ctrl+V is sent, and what the clipboard held comes back.
"""
import fcntl
import os
import struct
import subprocess
import time

EV_SYN, EV_KEY = 0, 1
UI_SET_EVBIT, UI_SET_KEYBIT, UI_DEV_CREATE, UI_DEV_DESTROY = 0x40045564, 0x40045565, 0x5501, 0x5502

# evdev key codes
NAMED = {
    "esc": 1, "backspace": 14, "tab": 15, "enter": 28, "ctrl": 29, "shift": 42, "alt": 56, "space": 57, "capslock": 58,
    "home": 102, "up": 103, "pageup": 104, "left": 105, "right": 106, "end": 107, "down": 108, "pagedown": 109,
    "insert": 110, "delete": 111, "meta": 125,
    "f1": 59, "f2": 60, "f3": 61, "f4": 62, "f5": 63, "f6": 64, "f7": 65, "f8": 66, "f9": 67, "f10": 68, "f11": 87, "f12": 88,
}
MODIFIERS = ("ctrl", "shift", "alt", "meta")
_ROWS = (("1234567890-=", 2), ("qwertyuiop[]", 16), ("asdfghjkl;'", 30), ("zxcvbnm,./", 44))
_SHIFTED = {"1": "!", "2": "@", "3": "#", "4": "$", "5": "%", "6": "^", "7": "&", "8": "*", "9": "(", "0": ")", "-": "_",
            "=": "+", "[": "{", "]": "}", ";": ":", "'": '"', ",": "<", ".": ">", "/": "?", "`": "~", "\\": "|"}


def _us_layout():
    table = {" ": (57, False), "\n": (28, False), "\t": (15, False), "`": (41, False), "\\": (43, False)}
    for chars, first in _ROWS:
        for i, c in enumerate(chars):
            table[c] = (first + i, False)
    for c in "abcdefghijklmnopqrstuvwxyz":
        table[c.upper()] = (table[c][0], True)
    for plain, shifted in _SHIFTED.items():
        table[shifted] = (table[plain][0], True)
    return table


US = _us_layout()


def plan(text, table=US):
    """How to type text: a list of ("key", code, shift) for what the layout has and ("paste", string) for runs of
    characters it has not (kept together, one paste each)."""
    out = []
    for c in text:
        if c in table:
            code, shift = table[c]
            out.append(("key", code, shift))
        elif out and out[-1][0] == "paste":
            out[-1] = ("paste", out[-1][1] + c)
        else:
            out.append(("paste", c))
    return out


def chord(names):
    """Key codes of a combination such as ("ctrl", "shift", "v") or ("alt", "tab"): modifiers first, then the key."""
    codes = []
    for name in names:
        if name in NAMED:
            codes.append(NAMED[name])
        elif name in US and not US[name][1]:
            codes.append(US[name][0])
        else:
            raise KeyError(name)
    return codes


class Keyboard:
    """The virtual keyboard device. open() makes it; the system needs a moment before it listens to it."""

    def __init__(self, path="/dev/uinput", clipboard=None, pause=time.sleep):
        self.path, self.fd, self.pause = path, -1, pause
        self.clipboard = clipboard or Clipboard()

    def open(self):
        fd = os.open(self.path, os.O_WRONLY | os.O_NONBLOCK)
        fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
        for code in range(1, 249):
            fcntl.ioctl(fd, UI_SET_KEYBIT, code)
        os.write(fd, struct.pack("80sHHHHi", b"Surface Overdrive on-screen keyboard", 0x06, 0x1d6b, 0x0105, 1, 0) + bytes(4 * 64 * 4))
        fcntl.ioctl(fd, UI_DEV_CREATE)
        self.fd = fd

    def close(self):
        if self.fd >= 0:
            try:
                fcntl.ioctl(self.fd, UI_DEV_DESTROY)
            finally:
                os.close(self.fd)
                self.fd = -1

    def _event(self, kind, code, value):
        os.write(self.fd, struct.pack("llHHi", 0, 0, kind, code, value))

    def key(self, code, down):
        self._event(EV_KEY, code, 1 if down else 0)
        self._event(EV_SYN, 0, 0)

    def tap(self, code, held=()):
        """One key, with the key codes in `held` down around it."""
        for h in held:
            self.key(h, True)
        self.key(code, True)
        self.key(code, False)
        for h in reversed(held):
            self.key(h, False)

    def combo(self, names):
        codes = chord(names)
        self.tap(codes[-1], codes[:-1])

    def type(self, text, held=()):
        """Text as key presses; what the layout cannot type goes through the clipboard. `held`: modifier names that
        are latched on the keyboard (Ctrl, Alt...), applied to every key."""
        extra = [NAMED[m] for m in held]
        for step in plan(text):
            if step[0] == "key":
                self.tap(step[1], extra + ([NAMED["shift"]] if step[2] else []))
            else:
                self.paste(step[1])

    def paste(self, text, terminal=False):
        """text into the focused field through the clipboard, which gets its contents back."""
        before = self.clipboard.get()
        self.clipboard.set(text, sensitive=True)
        self.pause(0.06)
        self.combo(("ctrl", "shift", "v") if terminal else ("ctrl", "v"))
        self.pause(0.15)
        if before is not None:
            self.clipboard.set(before)

    def paste_kept(self, text, terminal=False):
        """An entry of the clipboard history: it becomes the clipboard and is pasted."""
        self.clipboard.set(text)
        self.pause(0.06)
        self.combo(("ctrl", "shift", "v") if terminal else ("ctrl", "v"))


class Clipboard:
    """The Wayland clipboard through wl-clipboard, and the history kept by Plasma's Klipper."""

    def get(self):
        try:
            done = subprocess.run(["wl-paste", "--no-newline", "--type", "text/plain"], capture_output=True, timeout=2)
            return done.stdout.decode("utf-8", "replace") if done.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            return None

    def set(self, text, sensitive=False):
        try:
            subprocess.run(["wl-copy"] + (["--sensitive"] if sensitive else []) + ["--type", "text/plain;charset=utf-8"],
                           input=text.encode(), timeout=2, check=False)
        except (OSError, subprocess.SubprocessError):
            pass

    def history(self, limit=12):
        """The newest entries of Klipper's history, as text (pictures and empty ones left out)."""
        try:
            out = subprocess.run(["busctl", "--user", "--json=short", "call", "org.kde.klipper", "/klipper", "org.kde.klipper.klipper",
                                  "getClipboardHistoryMenu"], capture_output=True, text=True, timeout=3).stdout
            import json
            items = json.loads(out)["data"][0]
        except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError):
            return []
        seen, found = set(), []
        for item in items:
            if isinstance(item, str) and item.strip() and item not in seen:
                seen.add(item)
                found.append(item)
        return found[:limit]
