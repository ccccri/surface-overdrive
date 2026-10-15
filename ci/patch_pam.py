#!/usr/bin/env python3
"""Let the lock screen and the login screen accept the PIN or pattern of the user (src/overdrive/unlock.py).

One line goes in front of the password check of the two PAM services that unlock the screen or start a session:
  - "kde": the lock screen of Plasma (kscreenlocker),
  - "plasmalogin": the login screen.
It asks /usr/libexec/overdrive/unlock-check with the typed text. When that is the code, the user is in ("done": the rest of the auth
stack is skipped, also the keyring modules, which could not open the wallet with a PIN anyway); otherwise nothing happened ("ignore")
and the password check runs with the same text, without asking again (pam_exec keeps what was typed as the password).
sudo, polkit and every other service keep asking for the password only.

When a file is missing or its layout has changed it is left as it is and the build goes on with a warning: the screen then accepts
the password only.

usage: patch_pam.py [file ...]
"""
import sys
from pathlib import Path

FILES = ["/etc/pam.d/kde", "/usr/lib/pam.d/plasmalogin"]
ANCHOR = "auth        substack      password-auth\n"
LINE = ("# Surface Overdrive: the PIN or pattern of the user unlocks too (see /usr/lib/overdrive/python/overdrive/unlock.py)\n"
        "auth        [success=done default=ignore] pam_exec.so quiet expose_authtok /usr/libexec/overdrive/unlock-check\n")


def patch(text):
    """The patched text, the same text when already patched, None when the anchor is not there exactly once."""
    if LINE in text:
        return text
    if text.count(ANCHOR) != 1:
        return None
    return text.replace(ANCHOR, LINE + ANCHOR)


def main(paths):
    for p in map(Path, paths or FILES):
        try:
            new = patch(p.read_text())
        except OSError as e:
            print("warning: %s: %s, the screen will accept the password only" % (p, e))
            continue
        if new is None:
            print("warning: %s has an unknown layout, the screen will accept the password only" % p)
            continue
        p.write_text(new)
        print("patched %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
