"""overdrivectl: command line for the Surface Overdrive settings.

Reading a state needs no privileges; changing one asks for the administrator password through polkit.
"""
import subprocess
import sys

from . import health, helper

HELPER = "/usr/libexec/overdrive/helper"
USAGE = """usage: overdrivectl <command>

  status [--json] [-v]     health of every fix (-v adds what it does and what to do when it is not green)
  volume-hold [on|off]     hold-to-repeat of the device volume buttons
  stylus-filter [on|off]   hide the pen's fake battery (a change of "off" applies at the next restart)
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
        print(health.as_json(checks))
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


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "status":
        return show_status(argv[1:])
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
