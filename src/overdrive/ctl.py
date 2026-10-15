"""overdrivectl: command line for the Surface Overdrive settings.

Reading a state needs no privileges; changing one asks for the administrator password through polkit.
"""
import json
import subprocess
import sys

import getpass

from . import maintenance, camera, health, helper, pen, sensors, unlock
from .audio import eq, mic, pw, sounds

HELPER = "/usr/libexec/overdrive/helper"
UNLOCK = "/usr/libexec/overdrive/unlock"
USAGE = """usage: overdrivectl <command>

  status [--json] [-v]     health of every fix (-v adds what it does and what to do when it is not green)
  volume-hold [on|off]     hold-to-repeat of the device volume buttons
  stylus-filter [on|off]   hide the pen's fake battery (a change of "off" applies at the next restart)
  pen                      state of the pen, digitizer and Bluetooth pen battery, in JSON
  audio describe | eq ... | mic ... | play <kind> | record | stop | volume <sink|source> <0-1.5>
         | mute <sink|source>                                  output equaliser, microphone, test sounds, in JSON
  nfc                      state of the NFC reader and its services, in JSON
  settings export|inspect|import <file> | settings undo     all the settings of the user in one file, and back
  repair <check id>        try the repair of one fix (restarts its service), then check again
  image [changes|go-back|cancel]   the system images on the disk, what differs, start the previous one next time
  report                   write a report of the state and the logs for a bug report
  sensors                  battery, light sensor, motion and device facts, in JSON
  unlock [set pin|pattern | clear]   PIN or pattern that also unlocks the screen, in JSON (set: the code on standard input)
  camera <front|rear> describe | set <key> <value> | reset [<key>] | ui <key> <value>
         | preset save|apply|rename|delete|duplicate <args>    live camera settings, answers in JSON
"""
LABEL = {health.OK: "ok  ", health.WARN: "warn", health.FAIL: "FAIL", health.NA: "n/a "}


def read_state(name):
    state, _setter = helper.ACTIONS[name]
    return state()


def change(name, value):
    return subprocess.run(["pkexec", HELPER, name, value]).returncode


def show_status(args):
    checks = health.run_all()
    if "--json" in args:
        data = json.loads(health.as_json(checks))
        for check in data.get("checks", []):
            check["repair"] = maintenance.REPAIRS[check["id"]][0] if maintenance.repairable(check["id"]) else ""
        data["settings"] = {"volume_hold": read_state("volume-hold"), "stylus_filter": read_state("stylus-filter")}
        print(json.dumps(data, indent=2))
        return 0 if health.overall(checks) != health.FAIL else 1
    verbose = "-v" in args or "--verbose" in args
    group = None
    for c in checks:
        if c.group != group:
            group = c.group
            print("\n%s" % group)
        print("  [%s] %s: %s" % (LABEL[c.status], c.title, c.detail))
        if verbose and c.status != health.OK:
            for label, text in (("What it does", c.what), ("How it works", c.how), ("What to do", c.fix)):
                if text:
                    print("         %s: %s" % (label, text))
    print("\nOverall: %s" % health.overall(checks))
    return 0 if health.overall(checks) != health.FAIL else 1


def camera_command(args):
    """Settings of one camera. Always prints one JSON object; 'restart' tells that the camera service restarted."""
    if len(args) < 2 or args[0] not in camera.SENSORS:
        print(USAGE, file=sys.stderr)
        return 2
    cam, verb, rest = args[0], args[1], args[2:]
    out = {}
    try:
        if verb == "set" and len(rest) == 2:
            out["restart"] = camera.set_setting(cam, rest[0], float(rest[1]))
        elif verb == "reset":
            camera.reset_setting(cam, rest[0]) if rest else camera.reset_all(cam)
        elif verb == "ui" and len(rest) == 2:
            camera.set_ui_setting(rest[0], rest[1] in ("1", "true", "on"))
        elif verb == "preset" and rest:
            action, pargs = rest[0], rest[1:]
            fn = {"save": lambda: camera.save_preset(cam, pargs[0], len(pargs) > 1 and pargs[1] == "overwrite"),
                  "apply": lambda: camera.apply_preset(cam, pargs[0]),
                  "rename": lambda: camera.rename_preset(cam, pargs[0], pargs[1]),
                  "duplicate": lambda: camera.duplicate_preset(cam, pargs[0], pargs[1]),
                  "delete": lambda: camera.delete_preset(cam, pargs[0])}[action]
            out["result"] = fn()
        elif verb != "describe":
            print(USAGE, file=sys.stderr)
            return 2
    except (KeyError, IndexError, ValueError, OSError, TypeError, AttributeError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    out.update(camera.describe(cam))
    print(json.dumps(out))
    return 0


def audio_describe():
    out_vol, out_muted = pw.default_volume("@DEFAULT_AUDIO_SINK@")
    in_vol, in_muted = pw.default_volume("@DEFAULT_AUDIO_SOURCE@")
    state = eq.load()
    return {"eq": state, "active": pw.active_output(), "presets": eq.preset_names(), "mic": mic.describe(),
            "output": {"volume": out_vol, "muted": out_muted}, "input": {"volume": in_vol, "muted": in_muted},
            "volume_hold": read_state("volume-hold")}


def audio_command(args):
    """Audio settings of the user. Prints one JSON object; 'result' carries the outcome of the action."""
    if not args:
        print(USAGE, file=sys.stderr)
        return 2
    verb, rest = args[0], args[1:]
    out = {}
    try:
        if verb == "eq" and rest:
            action, a = rest[0], rest[1:]
            if action == "set":
                out["result"] = eq.set_output(a[0], json.loads(a[1]))
            elif action == "sync":
                eq.set_sync(a[0] == "on")
            elif action == "swap":
                if a[0] not in eq.OUTPUTS:
                    raise KeyError(a[0])
                eq.set_swap(a[0], a[1] == "on")
            elif action == "flat":
                out["result"] = eq.reset_bands(a[0])
            elif action == "preset":
                sub = a[0]
                if sub == "apply":
                    if a[1] not in eq.OUTPUTS:
                        raise KeyError(a[1])
                    out["result"] = eq.apply_preset(a[1], a[2])
                elif sub == "save":
                    out["result"] = eq.save_preset(a[1], eq.load()["sets"][a[2]])
                elif sub == "delete":
                    eq.delete_preset(a[1])
                else:
                    raise IndexError(sub)
            elif action == "import":
                s, notes = eq.parse_apo(open(a[1]).read())
                out["notes"] = notes
                out["result"] = s is not None and eq.set_output(a[0], s)
            elif action == "export":
                open(a[1], "w").write(eq.export_apo(eq.load()["sets"][a[0]]))
                out["result"] = True
            else:
                raise IndexError(action)
        elif verb == "mic" and rest:
            action, a = rest[0], rest[1:]
            if action == "set":
                out["result"] = mic.set_one(a[0], a[1])
            elif action == "set-all":
                out["result"] = mic.set_all(json.loads(a[0]))
            elif action == "enable":
                out["result"] = mic.enable()
            elif action == "disable":
                out["result"] = mic.disable()
            elif action == "preset":
                sub = a[0]
                if sub == "apply":
                    out["result"] = mic.apply_preset(a[1])
                elif sub == "save":
                    out["result"] = mic.save_preset(a[1])
                elif sub == "delete":
                    mic.delete_preset(a[1])
                else:
                    raise IndexError(sub)
            else:
                raise IndexError(action)
        elif verb == "play":
            return sounds.play(rest[0])
        elif verb == "record":
            return sounds.record_and_play()
        elif verb == "stop":
            sounds.stop()
        elif verb in ("volume", "mute") and rest and rest[0] in ("sink", "source"):
            target = "@DEFAULT_AUDIO_SINK@" if rest[0] == "sink" else "@DEFAULT_AUDIO_SOURCE@"
            if verb == "volume":
                pw.run(["wpctl", "set-volume", target, "%.2f" % max(0.0, min(1.5, float(rest[1])))])
            else:
                pw.run(["wpctl", "set-mute", target, "toggle"])
        elif verb != "describe":
            print(USAGE, file=sys.stderr)
            return 2
    except (KeyError, IndexError, ValueError, OSError, TypeError, AttributeError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    out.update(audio_describe())
    print(json.dumps(out))
    return 0


def maintenance_command(argv):
    """settings export|inspect|import <file> | settings undo; repair <check>; image [changes|go-back|cancel]; report. One JSON object."""
    verb, rest = argv[0], argv[1:]
    try:
        if verb == "settings" and len(rest) == 2 and rest[0] in ("export", "inspect", "import"):
            out = {"export": maintenance.export_settings, "inspect": maintenance.inspect_settings, "import": maintenance.import_settings}[rest[0]](rest[1])
        elif verb == "settings" and rest == ["undo"]:
            out = maintenance.undo_import()
        elif verb == "repair" and len(rest) == 1:
            out = maintenance.repair(rest[0])
        elif verb == "image" and not rest:
            out = maintenance.images()
        elif verb == "image" and rest in (["changes"], ["go-back"], ["cancel"]):
            out = {"changes": maintenance.changes, "go-back": maintenance.go_back, "cancel": maintenance.cancel_next}[rest[0]]()
        elif verb == "report" and not rest:
            out = maintenance.write_report()
        else:
            print(USAGE, file=sys.stderr)
            return 2
    except (OSError, ValueError, KeyError, TypeError) as e:
        out = {"result": "failed", "error": str(e)}
    print(json.dumps(out))
    return 0


def unlock_command(argv):
    """unlock: the state for this user; unlock set pin|pattern (code on stdin) / unlock clear: through polkit, after the password."""
    user = getpass.getuser()
    if not argv:
        print(json.dumps(unlock.status(user)))
        return 0
    if argv in (["set", "pin"], ["set", "pattern"]):
        code = sys.stdin.read(4096).strip()
        if not unlock.valid(argv[1], code):
            print(json.dumps({"result": "failed", "error": "a PIN is 4 to 12 digits, a pattern joins at least 4 dots"}))
            return 0
        run = subprocess.run(["pkexec", UNLOCK] + argv, input=code, capture_output=True, text=True)
    elif argv == ["clear"]:
        run = subprocess.run(["pkexec", UNLOCK, "clear"], capture_output=True, text=True)
    else:
        print(USAGE, file=sys.stderr)
        return 2
    if run.returncode == 0:
        out = dict(unlock.status(user), result="done")
    elif run.returncode in (126, 127):              # pkexec: the password was not given, or the dialog was closed
        out = dict(unlock.status(user), result="cancelled")
    else:
        out = dict(unlock.status(user), result="failed", error=run.stderr.strip().removeprefix("error: "))
    print(json.dumps(out))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "status":
        return show_status(argv[1:])
    if argv and argv[0] == "nfc":
        print(json.dumps(sensors.nfc_info()))
        return 0
    if argv and argv[0] == "sensors":
        if argv[1:2] == ["rate"] and len(argv) == 3:
            sensors.set_rate(argv[2])
        print(json.dumps(sensors.describe()))
        return 0
    if argv and argv[0] == "audio":
        return audio_command(argv[1:])
    if argv and argv[0] in ("settings", "repair", "image", "report"):
        return maintenance_command(argv)
    if argv and argv[0] == "pen":
        print(json.dumps(pen.describe(read_state("stylus-filter"))))
        return 0
    if argv and argv[0] == "unlock":
        return unlock_command(argv[1:])
    if argv and argv[0] == "camera":
        return camera_command(argv[1:])
    if not argv or argv[0] in ("-h", "--help") or argv[0] not in helper.ACTIONS:
        print(USAGE, file=sys.stderr if argv and argv[0] not in ("-h", "--help") else sys.stdout)
        return 0 if argv and argv[0] in ("-h", "--help") else 2
    name = argv[0]
    if len(argv) == 1:
        print("%s: %s" % (name, read_state(name)))
        return 0
    if argv[1] not in ("on", "off"):
        print(USAGE, file=sys.stderr)
        return 2
    return change(name, argv[1])


if __name__ == "__main__":
    sys.exit(main())
