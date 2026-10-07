"""overdrivectl: command line for the Surface Overdrive settings.

Reading a state needs no privileges; changing one asks for the administrator password through polkit.
"""
import json
import subprocess
import sys

from . import camera, health, helper, pen

HELPER = "/usr/libexec/overdrive/helper"
USAGE = """usage: overdrivectl <command>

  status [--json] [-v]     health of every fix (-v adds what it does and what to do when it is not green)
  volume-hold [on|off]     hold-to-repeat of the device volume buttons
  stylus-filter [on|off]   hide the pen's fake battery (a change of "off" applies at the next restart)
  pen                      state of the pen, digitizer and Bluetooth pen battery, in JSON
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
    except (KeyError, IndexError, ValueError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    out.update(camera.describe(cam))
    print(json.dumps(out))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "status":
        return show_status(argv[1:])
    if argv and argv[0] == "pen":
        print(json.dumps(pen.describe(read_state("stylus-filter"))))
        return 0
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
