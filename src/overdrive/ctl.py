"""overdrivectl: command line for the Surface Overdrive settings.

Reading a state needs no privileges; changing one asks for the administrator password through polkit.
"""
import subprocess
import sys

from . import helper

HELPER = "/usr/libexec/overdrive/helper"
USAGE = """usage: overdrivectl <command>

  volume-hold [on|off]     hold-to-repeat of the device volume buttons
  stylus-filter [on|off]   hide the pen's fake battery (a change of "off" applies at the next restart)
"""


def read_state(name):
    state, _setter = helper.ACTIONS[name]
    return state()


def change(name, value):
    return subprocess.run(["pkexec", HELPER, name, value]).returncode


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
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
