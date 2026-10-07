"""overdrive-helper: the few actions that need root, run through polkit (pkexec) by overdrivectl and the settings page.

Every action is on a fixed list and takes a fixed set of arguments: this is the only privileged entry point of the project.
"""
import subprocess
import sys
from pathlib import Path

VOLUME_PARAM = Path("/sys/module/intel_hid/parameters/volume_hold")
VOLUME_CONF = Path("/etc/modprobe.d/overdrive-intel-hid.conf")
STYLUS_MASK = Path("/etc/udev/rules.d/80-overdrive-stylus.rules")


def volume_hold_state(param=VOLUME_PARAM):
    """"on", "off" or "unavailable" (the patched intel_hid module is not loaded)."""
    try:
        value = param.read_text().strip()
    except OSError:
        return "unavailable"
    return "on" if value in ("Y", "1") else "off"


def set_volume_hold(on, param=VOLUME_PARAM, conf=VOLUME_CONF):
    """Apply to the running module and keep the choice for the next boot."""
    if volume_hold_state(param) == "unavailable":
        raise RuntimeError("the patched intel_hid module is not loaded")
    param.write_text("Y" if on else "N")
    conf.parent.mkdir(parents=True, exist_ok=True)
    conf.write_text("# Written by overdrivectl: hold-to-repeat of the device volume buttons\n"
                    "options intel_hid volume_hold=%d\n" % (1 if on else 0))


def stylus_filter_state(mask=STYLUS_MASK):
    """"on" unless an empty rule file in /etc masks the one of the image."""
    return "off" if mask.exists() else "on"


def set_stylus_filter(on, mask=STYLUS_MASK, reload_udev=True):
    if on:
        mask.unlink(missing_ok=True)
    else:
        mask.parent.mkdir(parents=True, exist_ok=True)
        mask.write_text("")
    if reload_udev:
        subprocess.run(["udevadm", "control", "--reload"], check=False)
        if on:                                   # the program loads when the digitizer is added: do it now
            subprocess.run(["udevadm", "trigger", "--action=add", "--subsystem-match=hid"], check=False)


ACTIONS = {
    "volume-hold": (volume_hold_state, set_volume_hold),
    "stylus-filter": (stylus_filter_state, set_stylus_filter),
}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2 or argv[0] not in ACTIONS or argv[1] not in ("on", "off", "status"):
        print("usage: overdrive-helper volume-hold|stylus-filter on|off|status", file=sys.stderr)
        return 2
    state, setter = ACTIONS[argv[0]]
    try:
        if argv[1] == "status":
            print(state())
        else:
            setter(argv[1] == "on")
            print("%s: %s" % (argv[0], argv[1]))
    except (OSError, RuntimeError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
