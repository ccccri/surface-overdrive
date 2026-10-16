"""overdrive-osk-guard: keeps the on-screen keyboard reachable while the screen is locked.

The keyboard button in the panel switches the on-screen keyboard off for good. On a tablet without a keyboard that leaves no way to type
the password once the screen locks, and the button is out of reach there. This service switches the keyboard back on when the screen
locks and, if it was the one that did it, off again after unlocking, so the choice made in the panel still holds in the session.

As it watches the lock state anyway, it also tells the PIN and pattern unlock (unlock.py) that the user is in, when the session starts
and at every unlock: wrong codes typed before are forgotten and a pad blocked by them is back.
"""
import getpass
import subprocess
import sys

from . import unlock

KWIN = ["org.kde.KWin", "/VirtualKeyboard", "org.kde.kwin.VirtualKeyboard"]
OFF = 0
TOUCH = 1


def decide(locked, mode, forced):
    """(mode to set or None, new forced). forced: the keyboard is on only because of the lock screen."""
    if locked:
        return (TOUCH, True) if mode == OFF else (None, forced)
    if forced and mode == TOUCH:
        return OFF, False
    return None, False


def parse(line):
    """True/False for a lock state change in a line of gdbus monitor output, None for anything else."""
    if "ActiveChanged" not in line:
        return None
    tail = line.rsplit("(", 1)[-1]
    if tail.startswith("true"):
        return True
    if tail.startswith("false"):
        return False
    return None


def get_mode():
    out = subprocess.run(["busctl", "--user", "get-property"] + KWIN + ["mode"], capture_output=True, text=True, timeout=10).stdout.split()
    return int(out[1]) if len(out) == 2 else None


def set_mode(mode):
    subprocess.run(["busctl", "--user", "set-property"] + KWIN + ["mode", "i", str(mode)], capture_output=True, timeout=10)


def is_locked():
    out = subprocess.run(["busctl", "--user", "call", "org.freedesktop.ScreenSaver", "/ScreenSaver", "org.freedesktop.ScreenSaver", "GetActive"],
                         capture_output=True, text=True, timeout=10).stdout
    return out.strip() == "b true"


def apply(locked, forced):
    mode = get_mode()
    if mode is None:
        return forced
    new, forced = decide(locked, mode, forced)
    if new is not None:
        set_mode(new)
        print("screen %s: on-screen keyboard switched %s" % ("locked" if locked else "unlocked", "on" if new else "off again"), flush=True)
    return forced


def user_is_in():
    try:
        unlock.passed(getpass.getuser())
    except (OSError, ValueError, KeyError):
        pass


def main():
    watch = subprocess.Popen(["gdbus", "monitor", "--session", "--dest", "org.freedesktop.ScreenSaver", "--object-path", "/ScreenSaver"],
                             stdout=subprocess.PIPE, text=True)
    locked_now = is_locked()
    forced = apply(True, False) if locked_now else False
    if not locked_now:
        user_is_in()
    for line in watch.stdout:
        locked = parse(line)
        if locked is not None:
            print("screen %s" % ("locked" if locked else "unlocked"), flush=True)
            forced = apply(locked, forced)
            if not locked:
                user_is_in()
    sys.exit(watch.wait() or 1)
