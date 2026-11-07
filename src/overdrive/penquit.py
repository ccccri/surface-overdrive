"""The Surface Pen's barrel button as the way out of a Moonlight stream.

Moonlight on a touch screen has no control to leave a stream, only keyboard shortcuts. Holding the barrel (side) button of
the pen for HOLD seconds while Moonlight runs ends the stream with Moonlight's own "quit", so that the PC ends its session
too (the Surface's screen goes, the PC's monitor comes back). A short press is left alone: it still reaches Moonlight, and
outside Moonlight nothing changes. Runs as root (the pen's input device is root's), the quit as the user who runs Moonlight.
"""
import os
import pwd
import re
import select
import struct
import subprocess
import sys
import time

EVENT = struct.Struct("llHHi")      # struct input_event on 64-bit: time, type, code, value
EV_KEY = 1
BTN_STYLUS = 0x14b
HOLD = 0.8
APP = "com.moonlight_stream.Moonlight"


def stylus_device(devices_text):
    """/dev/input/eventN of the pen ("... Stylus" in /proc/bus/input/devices), or None."""
    for block in devices_text.split("\n\n"):
        if re.search(r'^N: Name=".*Stylus"', block, flags=re.M):
            m = re.search(r"^H: Handlers=.*\b(event\d+)\b", block, flags=re.M)
            if m:
                return "/dev/input/" + m.group(1)
    return None


def moonlight_process():
    """(pid, uid, argv) of a running Moonlight, or None."""
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            with open("/proc/%s/comm" % pid) as f:
                if f.read().strip() != "moonlight":
                    continue
            with open("/proc/%s/cmdline" % pid, "rb") as f:
                argv = [a.decode(errors="replace") for a in f.read().split(b"\0") if a]
            return int(pid), os.stat("/proc/" + pid).st_uid, argv
        except OSError:
            continue
    return None


def stream_host(argv, home):
    """The host of the stream: from "moonlight stream <host> <app>", else the first host Moonlight knows."""
    if "stream" in argv and argv.index("stream") + 1 < len(argv):
        return argv[argv.index("stream") + 1]
    conf = os.path.join(home, ".var/app", APP, "config/Moonlight Game Streaming Project/Moonlight.conf")
    try:
        text = open(conf).read()
    except OSError:
        return None
    for key in ("manualaddress", "localaddress", "hostname"):
        m = re.search(r"^1\\%s=(.+)$" % key, text, flags=re.M)
        if m:
            return m.group(1).strip()
    return None


def quit_stream():
    found = moonlight_process()
    if not found:
        return
    pid, uid, argv = found
    user = pwd.getpwuid(uid)
    host = stream_host(argv, user.pw_dir)
    try:
        os.kill(pid, 15)
    except OSError:
        pass
    if host:
        env = ["XDG_RUNTIME_DIR=/run/user/%d" % uid, "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/%d/bus" % uid]
        subprocess.run(["runuser", "-u", user.pw_name, "--", "env", *env, "flatpak", "run", APP, "quit", host],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60, check=False)


def main():
    while True:
        try:
            dev = stylus_device(open("/proc/bus/input/devices").read())
        except OSError:
            dev = None
        if not dev:
            time.sleep(10)
            continue
        try:
            fd = os.open(dev, os.O_RDONLY)
        except OSError:
            time.sleep(10)
            continue
        pressed = None
        try:
            while True:
                ready, _, _ = select.select([fd], [], [], 0.2 if pressed else None)
                if pressed and time.monotonic() - pressed >= HOLD:
                    pressed = None
                    if moonlight_process():
                        quit_stream()
                if not ready:
                    continue
                data = os.read(fd, EVENT.size * 64)
                for i in range(0, len(data) - EVENT.size + 1, EVENT.size):
                    _, _, typ, code, value = EVENT.unpack_from(data, i)
                    if typ == EV_KEY and code == BTN_STYLUS:
                        pressed = time.monotonic() if value else None
        except OSError:
            pass            # the device went (suspend, a new pen): look for it again
        finally:
            os.close(fd)
        time.sleep(1)


if __name__ == "__main__":
    sys.exit(main())
