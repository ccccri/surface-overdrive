"""overdrive-welcome: the introduction to Surface Overdrive, once per user, in Plasma's Welcome Center.

The pages are in /usr/share/plasma/plasma-welcome/extra-pages (50- to 52-Surface*). Plasma's Welcome Center shows them
after its own pages on a user's very first login; a user who started on stock Kinoite and then switched to the image
saw Plasma's already, so at the first login on the image this opens the Welcome Center with our pages only. It runs from
the session's autostart, once (a state file); "Surface Overdrive Tour" in the application menu opens them again.
"""
import configparser
import os
import subprocess
import sys
import time

from . import userconfig

PAGES = "50-SurfaceOverdrive,51-SurfaceOverdriveSetup,52-SurfaceOverdriveUpdates"
DONE = "welcome-shown"


def plasma_welcome_will_show(path):
    """True when Plasma's own Welcome Center has never run for this user: it opens by itself, with our pages in it."""
    cfg = configparser.ConfigParser(strict=False, interpolation=None)
    try:
        cfg.read(path)
    except configparser.Error:
        return False
    return not cfg.get("General", "LastSeenVersion", fallback="")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--now" in argv:
        os.execvp("plasma-welcome", ["plasma-welcome", "--pages", PAGES])
    state = os.path.join(userconfig.CONFIG, DONE)
    if os.path.exists(state):
        return 0
    config = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    userconfig.write_atomic(state, time.strftime("%F %T\n"))     # once, even if the window is closed at once
    if plasma_welcome_will_show(os.path.join(config, "plasma-welcomerc")):
        return 0
    time.sleep(6)                                                # after the desktop and the panel are up
    subprocess.Popen(["plasma-welcome", "--pages", PAGES], start_new_session=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
