"""overdrive-stream-rotation: while Moonlight streams, the screen turns only between landscape and upside-down landscape.

The PC's screen for the Surface is landscape, 1800x1200: turned to portrait, KWin rotated the Surface's screen and Moonlight
shrank the whole picture into it. While a stream runs (Moonlight has its UDP ports open towards Sunshine), KWin's own
automatic rotation is turned off and this service turns the screen itself, from the accelerometer: upright or upside down,
never on its side. When the stream ends, the user's setting comes back and KWin follows the sensor again.

The setting in force before is kept in ~/.local/state/surface-overdrive/rotation-policy until it is put back, so a crash
mid-stream does not leave automatic rotation off.
"""
import json
import os
import subprocess
import sys
import time

from . import sensors

OUTPUT = "eDP-1"
# Sunshine's UDP ports a streaming Moonlight talks to: video, control, audio (47998-48000)
STREAM_PORTS = {47998, 47999, 48000}
STATE = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "surface-overdrive",
                     "rotation-policy")
# libkscreen's names
ROTATION = {1: "none", 2: "left", 4: "inverted", 8: "right"}
POLICY = {0: "never", 1: "inTabletMode", 2: "always"}
G_MIN = 3.0       # m/s^2 along the long axis before the screen counts as upright or upside down
DOMINANCE = 1.5   # the long axis must beat the short one by this much (not lying flat, not on its side)


def streaming(udp_tables):
    """True when a socket in /proc/net/udp(6) text talks to one of Sunshine's stream ports."""
    for text in udp_tables:
        for line in text.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 3 or ":" not in parts[2]:
                continue
            addr, port = parts[2].rsplit(":", 1)
            if int(port, 16) in STREAM_PORTS and set(addr) != {"0"}:
                return True
    return False


def orientation(x, y):
    """'none' (upright), 'inverted' (upside down) or None (on its side, flat, or unsure), from the accelerometer in m/s^2.
    On the Surface Go gravity points along -y when it stands upright in landscape."""
    if x is None or y is None or abs(y) < G_MIN or abs(y) < DOMINANCE * abs(x):
        return None
    return "none" if y < 0 else "inverted"


def read_udp():
    out = []
    for p in ("/proc/net/udp", "/proc/net/udp6"):
        try:
            with open(p) as f:
                out.append(f.read())
        except OSError:
            pass
    return out


def read_accel():
    a = sensors.iio_device("accel_3d")
    if not a:
        return None, None
    scale = sensors.number(a + "/in_accel_scale", 1)
    x, y = sensors.number(a + "/in_accel_x_raw"), sensors.number(a + "/in_accel_y_raw")
    if x is None or y is None:
        return None, None
    return x * scale, y * scale


def screen():
    """(rotation name, policy name) of the built-in screen, or (None, None)."""
    try:
        out = subprocess.run(["kscreen-doctor", "--json"], capture_output=True, text=True, timeout=10).stdout
        for o in json.loads(out).get("outputs", []):
            if o.get("name") == OUTPUT:
                return ROTATION.get(o.get("rotation")), POLICY.get(o.get("autoRotatePolicy"))
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None, None


def doctor(*ops):
    subprocess.run(["kscreen-doctor"] + ["output.%s.%s" % (OUTPUT, op) for op in ops], capture_output=True, timeout=15)


def tablet_mode():
    out = subprocess.run(["busctl", "--user", "get-property", "org.kde.KWin", "/org/kde/KWin", "org.kde.KWin.TabletModeManager",
                          "tabletMode"], capture_output=True, text=True, timeout=10).stdout
    return out.strip() == "b true"


def saved_policy():
    try:
        with open(STATE) as f:
            p = f.read().strip()
        return p if p in POLICY.values() else None
    except OSError:
        return None


def save_policy(p):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE + ".tmp", "w") as f:
        f.write(p + "\n")
    os.replace(STATE + ".tmp", STATE)


def restore():
    p = saved_policy()
    if p:
        doctor("autoRotatePolicy." + p)
        os.remove(STATE)
        print("stream over: automatic rotation back to %s" % p, flush=True)


def may_turn(policy):
    return policy == "always" or (policy == "inTabletMode" and tablet_mode())


def main():
    if not streaming(read_udp()):
        restore()   # left over from a stream this service did not see end
    active = False
    policy = None
    pending, since = None, 0.0
    while True:
        now_streaming = streaming(read_udp())
        if now_streaming and not active:
            rot, policy = screen()
            if policy is None:
                time.sleep(2)
                continue
            if not saved_policy():
                save_policy(policy)
            policy = saved_policy()
            doctor("autoRotatePolicy.never")
            active = True
            pending = None
            print("stream: rotation held to landscape (was %s, %s)" % (rot, policy), flush=True)
            if rot not in ("none", "inverted"):
                doctor("rotation." + (orientation(*read_accel()) or "none"))
        elif not now_streaming and active:
            active = False
            restore()
        if active:
            want = orientation(*read_accel())
            if want != pending:
                pending, since = want, time.monotonic()
            elif want and time.monotonic() - since >= 0.8:
                rot, _ = screen()
                if rot and rot != want and may_turn(policy):
                    doctor("rotation." + want)
                    print("turned %s" % want, flush=True)
                pending = None
        time.sleep(0.4 if active else 1.5)


if __name__ == "__main__":
    sys.exit(main())
