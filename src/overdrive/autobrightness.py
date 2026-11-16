"""Automatic screen brightness from the tablet's light sensor (a beta: off until switched on, `overdrivectl brightness auto on`).

Plasma has none. The Surface Go has an ambient light sensor, and a tablet is carried from a window to a sofa to a bed:
the brightness that was right in one place is wrong in the next. This service reads the sensor once a second and moves
Plasma's own brightness (the same value the slider in the panel shows) along a curve from the light in the room.

How it stays out of the way:
  - It follows the light slowly: the reading is smoothed, a change has to last (2 s towards brighter, 5 s towards
    darker, as a hand over the sensor or a shadow must do nothing), and the brightness moves in small steps.
  - It never fights the user. A brightness it did not set itself (the slider, the keys, Plasma dimming an idle screen)
    is left alone until the light in the room really changes (by half or by double); the difference to the curve is
    then kept as the user's taste ("bias") for this session.
  - It only ever writes through Plasma (org.kde.Solid.PowerManagement), so the OSD-less "silent" call, the limits and
    the dimming of Plasma stay what they are.

The decisions are in Controller, which knows nothing of D-Bus or files and is what the tests drive.
"""
import json
import math
import os
import subprocess
import sys
import time

from . import sensors

CONFIG = os.path.expanduser("~/.config/surface-overdrive/autobrightness.json")
UNIT = "overdrive-autobrightness.service"
BUS = ["org.kde.Solid.PowerManagement", "/org/kde/Solid/PowerManagement/Actions/BrightnessControl",
       "org.kde.Solid.PowerManagement.Actions.BrightnessControl"]

# Light in the room (lux) -> brightness (0 to 1), between the points a straight line over the logarithm of the light.
# Indoors in the evening is 20 to 80 lux, an office 300 to 500, a window by day 1000 and more, outdoors 10000 and more.
CURVE = ((0, 0.05), (5, 0.10), (20, 0.20), (80, 0.32), (300, 0.50), (1000, 0.72), (4000, 0.92), (10000, 1.0))

SMOOTHING = 0.35          # weight of a new reading in the smoothed light
BRIGHTER_AFTER = 2.0      # seconds a wish for more light has to last
DARKER_AFTER = 5.0        # seconds a wish for less
DEADBAND = 0.04           # a wish this close to what is set is no wish
STEP = 0.02               # the most the brightness moves in one tick (ticks come fast while it moves)
RELEASE = 2.0             # the light has to change by this factor before a brightness of the user is touched again
BIAS_LIMIT = 0.35


def curve(lux, points=CURVE):
    """The brightness (0 to 1) the curve gives for this much light."""
    lux = max(0.0, float(lux))
    if lux <= points[0][0]:
        return points[0][1]
    for (l0, b0), (l1, b1) in zip(points, points[1:]):
        if lux <= l1:
            t = (math.log10(lux + 1) - math.log10(l0 + 1)) / (math.log10(l1 + 1) - math.log10(l0 + 1))
            return b0 + (b1 - b0) * t
    return points[-1][1]


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


class Controller:
    """What to set the brightness to, from the readings so far. tick() is called about once a second with the light
    (lux, or None when the sensor gave nothing) and the brightness Plasma has now (0 to 1); it answers the brightness
    to set, or None to leave things alone."""

    def __init__(self, bias=0.0, floor=0.02):
        self.bias = clamp(bias, -BIAS_LIMIT, BIAS_LIMIT)
        self.floor = floor            # never darker than this: a black screen cannot be turned up again by touch
        self.light = None             # smoothed lux
        self.ours = None              # the brightness we set last (None: nothing yet)
        self.held_at = None           # the light at which the user set a brightness of their own (None: not held)
        self.wish_since = None        # when the present wish (up or down) began
        self.wish_up = None

    def wanted(self):
        return clamp(curve(self.light) + self.bias, self.floor, 1.0)

    def tick(self, lux, brightness, now):
        if lux is None or brightness is None:
            return None
        self.light = lux if self.light is None else self.light + (lux - self.light) * SMOOTHING

        # A brightness that is not the one we set: somebody else did (the user, or Plasma dimming). Hands off.
        if self.ours is not None and abs(brightness - self.ours) > 0.011:
            if self.held_at is None or abs(brightness - self.held) > 0.011:
                self.held_at, self.held = self.light, brightness
            self.ours = brightness
            self.wish_since = None
        if self.held_at is not None:
            low, high = self.held_at / RELEASE, self.held_at * RELEASE
            # in the dark a factor means little (0.5 lux to 1 lux): there the light has to move by 3 lux at least
            if abs(self.light - self.held_at) < 3.0 or low <= self.light <= high:
                return None
            # the room changed: back to work, keeping how much brighter or darker than the curve the user wanted
            self.bias = clamp(self.held - curve(self.held_at), -BIAS_LIMIT, BIAS_LIMIT)
            self.held_at = None

        wanted = self.wanted()
        if self.ours is None:
            self.ours = brightness
        if abs(wanted - brightness) < DEADBAND:
            self.wish_since = None
            return None
        up = wanted > brightness
        if self.wish_since is None or self.wish_up != up:
            self.wish_since, self.wish_up = now, up
            return None
        if now - self.wish_since < (BRIGHTER_AFTER if up else DARKER_AFTER):
            return None
        step = clamp(wanted - brightness, -STEP, STEP)
        self.ours = clamp(brightness + step, self.floor, 1.0)
        return self.ours


# ---- the service --------------------------------------------------------------------------------------------------

def _busctl(method, *args, run=subprocess.run):
    try:
        done = run(["busctl", "--user", "call"] + BUS + [method] + list(args), capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    parts = done.stdout.split()
    return int(parts[1]) if len(parts) == 2 and parts[0] == "i" else 0


def load(path=CONFIG):
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data, path=CONFIG):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".new", "w") as f:
        json.dump(data, f, indent=1)
    os.replace(path + ".new", path)


def backlight(read=sensors.read, glob=None):
    """The brightness of the screen now, 0 to 1, read from the kernel (no process started: this is asked every second)."""
    import glob as _glob
    for d in sorted((glob or _glob.glob)("/sys/class/backlight/*")):
        try:
            return int(read(d + "/brightness")) / max(1, int(read(d + "/max_brightness")))
        except (TypeError, ValueError):
            continue
    return None


def serve(tick=1.0, moving=0.15, clock=time.monotonic, sleep=time.sleep, light=sensors.light, level=backlight, call=_busctl,
          dry=False, out=sys.stderr, rounds=None):
    """Runs until stopped (or for `rounds` ticks, for the tests). dry: says what it would set and sets nothing."""
    maximum = call("brightnessMax")
    if not maximum or light() is None or level() is None:
        print("no light sensor or no brightness to set: nothing to do", file=out)
        return 0
    config = load()
    controller = Controller(bias=float(config.get("bias", 0.0)), floor=max(0.02, 1.0 / maximum))
    saved_bias = controller.bias
    while rounds is None or rounds > 0:
        rounds = None if rounds is None else rounds - 1
        target = controller.tick(light(), level(), clock())
        if target is not None:
            if dry:
                print("would set %d%% (light %.0f lux)" % (round(target * 100), controller.light), file=out, flush=True)
                controller.ours = level()                       # nothing was set: do not take our own wish for done
            else:
                call("setBrightnessSilent", "i", str(max(1, round(target * maximum))))
                controller.ours = max(1, round(target * maximum)) / maximum
        if abs(controller.bias - saved_bias) > 0.02:            # the user's taste, for the next start
            saved_bias = controller.bias
            config = load()
            config["bias"] = round(saved_bias, 3)
            save(config)
        sleep(moving if target is not None and not dry else tick)
    return 0


def command(argv, run=subprocess.run):
    """overdrivectl brightness auto [on|off|status|dry]: one JSON object."""
    verb = argv[0] if argv else "status"
    if verb in ("on", "off"):
        done = run(["systemctl", "--user", "enable" if verb == "on" else "disable", "--now", UNIT], capture_output=True, text=True)
        if done.returncode != 0:
            return {"error": (done.stderr or "").strip() or "systemctl failed"}
    elif verb == "dry":
        return serve(dry=True, out=sys.stdout)
    elif verb != "status":
        return {"error": "usage: overdrivectl brightness auto [on|off|status|dry]"}
    active = run(["systemctl", "--user", "is-active", UNIT], capture_output=True, text=True).stdout.strip() == "active"
    lux = sensors.light()
    return {"auto": active, "light": lux, "curve": None if lux is None else round(curve(lux), 2), "bias": load().get("bias", 0.0)}


def main():
    sys.exit(serve())
