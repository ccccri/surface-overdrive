#!/usr/bin/env python3
"""Keep the on-screen keyboard bright while KWin dims the screen behind a password dialog.

KWin's "Dim Screen for Administrator Mode" effect darkens every window except the authentication dialog (polkit, kdesu) while it is
active. On a tablet the on-screen keyboard is how that password is typed, and it was darkened like the windows behind, as if it
were not part of the dialog. The effect is a script in KWin's data directory: one check more makes it leave the input method
window alone. When the script has changed shape the file is left as it is, with a warning (the keyboard is then dimmed as before).

usage: patch_dimscreen.py [path]
"""
import sys
from pathlib import Path

DEFAULT = "/usr/share/kwin-wayland/effects/dimscreen/contents/code/main.js"
MARK = "// Surface Overdrive:"
ANCHOR = """        if (window.popupWindow) {
            return;
        }
"""
ADDED = ANCHOR + """        %s the on-screen keyboard is how the password gets typed on a tablet: it stays bright, like the dialog
        // KWin does not tell scripts which window is the input method, and does not give it a program name either; it is the only
        // window that is a utility, cannot be moved and is left out of the window switcher (KWin's InputPanelV1Window)
        if (window.utility && !window.moveable && window.skipSwitcher) {
            return;
        }
""" % MARK


def patch(text):
    if MARK in text:
        return text
    if text.count(ANCHOR) != 1:
        return None
    return text.replace(ANCHOR, ADDED)


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
    try:
        original = path.read_text()
    except OSError as e:
        print("WARNING: %s: %s, the on-screen keyboard is dimmed with the windows behind a password dialog" % (path, e))
        return 0
    patched = patch(original)
    if patched is None:
        print("WARNING: the layout of %s changed, the on-screen keyboard is dimmed with the windows behind a password dialog" % path)
    elif patched != original:
        path.write_text(patched)
        print("patched", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
