"""overdrive-tablet-mode: a desktop made for fingers while the tablet has no keyboard.

KWin switches to its tablet mode when the type cover is taken off (or no mouse or touchpad is there), but Plasma 6.7 then only
enlarges the icons of the system tray. This user service follows KWin's tablet mode and, while it is on, makes the parts that
fingers hit bigger:
  - the panel is taller (TABLET_PANEL pixels),
  - the icons of the task manager are spaced wider (iconSpacing "large"),
  - the buttons of the window title bars are large (Breeze's button size).
Back with a keyboard or a mouse, each goes back to what it was before, unless it was changed by hand meanwhile: then the hand
wins. What it was before is kept in ~/.local/state/surface-overdrive/tablet-mode.json, so a restart in between loses nothing.
"""
import json
import os
import subprocess
import sys

TABLET_PANEL = 62          # pixels; the default panel of the image is 46
TABLET_SPACING = 3         # iconSpacing of the task manager: 0 small, 1 normal, 3 large
TABLET_BUTTONS = "ButtonLarge"

PANEL_READ = """
var out = [];
panels().forEach(function (p) {
    var t = p.widgets("org.kde.plasma.icontasks").concat(p.widgets("org.kde.plasma.taskmanager"));
    var s = -1;
    if (t.length > 0) { t[0].currentConfigGroup = ["General"]; s = t[0].readConfig("iconSpacing", 1); }
    out.push(p.id + ":" + p.height + ":" + s);
});
print(out.join(","));
"""


def panel_write_script(values):
    """values: {panel id: (height or None, spacing or None)}."""
    lines = ["var want = %s;" % json.dumps({str(k): list(v) for k, v in values.items()}),
             """panels().forEach(function (p) {
    var w = want[String(p.id)];
    if (!w) return;
    if (w[0] !== null) p.height = w[0];
    if (w[1] !== null) {
        var t = p.widgets("org.kde.plasma.icontasks").concat(p.widgets("org.kde.plasma.taskmanager"));
        if (t.length > 0) { t[0].currentConfigGroup = ["General"]; t[0].writeConfig("iconSpacing", w[1]); }
    }
});"""]
    return "\n".join(lines)


def parse_panels(text):
    """{panel id: (height, spacing)} from what PANEL_READ prints."""
    out = {}
    for part in (text or "").strip().split(","):
        bits = part.split(":")
        if len(bits) == 3:
            try:
                out[bits[0]] = (int(float(bits[1])), int(float(bits[2])))
            except ValueError:
                continue
    return out


def state_path():
    d = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "surface-overdrive")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "tablet-mode.json")


def load_state():
    try:
        with open(state_path()) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(data):
    tmp = state_path() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, state_path())


def plan_enter(panels, buttons):
    """From the values of now: what tablet mode sets, and what to remember. Returns (panel values to write, buttons to write,
    state to keep)."""
    normal = {"panels": {k: list(v) for k, v in panels.items()}, "buttons": buttons}
    want = {k: (TABLET_PANEL if h < TABLET_PANEL else None, TABLET_SPACING if 0 <= s < TABLET_SPACING else None)
            for k, (h, s) in panels.items()}
    kept = {"on": True, "normal": normal,
            "set": {"panels": {k: [w[0] if w[0] is not None else panels[k][0], w[1] if w[1] is not None else panels[k][1]]
                               for k, w in want.items()},
                    "buttons": TABLET_BUTTONS}}
    return want, TABLET_BUTTONS, kept


def plan_leave(state, panels, buttons):
    """Back to the values before tablet mode, for each one still at what tablet mode set (changed by hand meanwhile: left)."""
    normal, done = state.get("normal", {}), state.get("set", {})
    want = {}
    for k, (h, s) in panels.items():
        was = normal.get("panels", {}).get(k)
        put = done.get("panels", {}).get(k)
        if not was or not put:
            continue
        want[k] = (was[0] if h == put[0] and h != was[0] else None, was[1] if s == put[1] and s != was[1] else None)
    restore = normal.get("buttons") if buttons == done.get("buttons") and buttons != normal.get("buttons") else None
    return {k: v for k, v in want.items() if v != (None, None)}, restore


# ---- the desktop ----
def _bus():
    from gi.repository import Gio
    return Gio.bus_get_sync(Gio.BusType.SESSION, None)


def evaluate(script):
    from gi.repository import GLib, Gio
    res = _bus().call_sync("org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell", "evaluateScript",
                           GLib.Variant("(s)", (script,)), GLib.VariantType("(s)"), Gio.DBusCallFlags.NONE, 10000, None)
    return res.unpack()[0]


def read_buttons():
    done = subprocess.run(["kreadconfig6", "--file", "breezerc", "--group", "Windeco", "--key", "ButtonSize"],
                          capture_output=True, text=True)
    return done.stdout.strip() or "ButtonDefault"


def write_buttons(value):
    if value == "ButtonDefault":
        subprocess.run(["kwriteconfig6", "--file", "breezerc", "--group", "Windeco", "--key", "ButtonSize", "--delete"])
    else:
        subprocess.run(["kwriteconfig6", "--file", "breezerc", "--group", "Windeco", "--key", "ButtonSize", value])
    from gi.repository import Gio
    _bus().call_sync("org.kde.KWin", "/KWin", "org.kde.KWin", "reconfigure", None, None, Gio.DBusCallFlags.NONE, 5000, None)


def apply(tablet):
    """Make the desktop match the mode. True when done (False: Plasma is not up yet, try again)."""
    state = load_state()
    try:
        panels = parse_panels(evaluate(PANEL_READ))
    except Exception as exc:                     # plasmashell not there yet, or busy
        print("the panels cannot be read yet: %s" % exc, flush=True)
        return False
    buttons = read_buttons()
    if tablet and not state.get("on"):
        want, wbuttons, kept = plan_enter(panels, buttons)
        save_state(kept)                         # first: a crash half way still knows the way back
        if want:
            evaluate(panel_write_script(want))
        if wbuttons != buttons:
            write_buttons(wbuttons)
        print("tablet mode: bigger panel, wider task icons, large title bar buttons", flush=True)
    elif not tablet and state.get("on"):
        want, restore = plan_leave(state, panels, buttons)
        if want:
            evaluate(panel_write_script(want))
        if restore:
            write_buttons(restore)
        save_state({"on": False})
        print("desktop mode: panel and title bar buttons back", flush=True)
    return True


def main():
    from gi.repository import GLib, Gio

    bus = _bus()
    pending = {"tablet": None}

    def tablet_now():
        res = bus.call_sync("org.kde.KWin", "/org/kde/KWin", "org.freedesktop.DBus.Properties", "Get",
                            GLib.Variant("(ss)", ("org.kde.KWin.TabletModeManager", "tabletMode")),
                            GLib.VariantType("(v)"), Gio.DBusCallFlags.NONE, 5000, None)
        return bool(res.unpack()[0])

    def attempt():
        if pending["tablet"] is None:
            return False
        if apply(pending["tablet"]):
            pending["tablet"] = None
            return False
        return True                              # Plasma not ready: the timer tries again

    def changed(_conn, _sender, _path, _iface, _signal, params):
        pending["tablet"] = bool(params.unpack()[0])
        if not attempt():
            return
        GLib.timeout_add_seconds(5, attempt)

    bus.signal_subscribe("org.kde.KWin", "org.kde.KWin.TabletModeManager", "tabletModeChanged", "/org/kde/KWin", None,
                         Gio.DBusSignalFlags.NONE, changed)
    try:
        pending["tablet"] = tablet_now()
    except GLib.Error as exc:
        print("KWin does not answer: %s" % exc.message, flush=True)
        return 1
    if attempt():
        GLib.timeout_add_seconds(5, attempt)
    GLib.MainLoop().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
