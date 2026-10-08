#!/usr/bin/env python3
"""Make Plasma's lock screen usable with a finger.

The lock screen shows the password field when the mouse moves and hides it when the mouse leaves. A finger arrives as a mouse that is
pressed and then leaves at once, so on a tablet the password field shows while swiping and is gone the moment the finger lifts. This
changes the lock screen so that after a touch
  - lifting the finger does not hide the password field, which goes away after the usual ten seconds without input, and
  - it stays for as long as the on-screen keyboard is open or something is typed, as it does with a mouse over the screen.

The file belongs to Fedora's plasma-desktop package, so it is edited in the image build. When its layout changes the file is left as it
is and the build goes on with a warning: the lock screen then behaves like the stock one.

usage: patch_lockscreen.py [path]
"""
import sys
from pathlib import Path

DEFAULT = "/usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen/LockScreenUi.qml"
MARK = "// Surface Overdrive:"

CHANGES = [
    ("""        property bool blockUI: containsMouse && (""",
     """        %s a finger leaves no pointer behind, so once the screen was touched, lifting the finger is not the mouse going away
        property bool touched: false
        property bool blockUI: (containsMouse || touched) && (""" % MARK),
    ("""        onExited: {
            uiVisible = false;
        }
""",
     """        onExited: {
            if (!touched) {
                uiVisible = false;
            }
        }
        PointHandler {
            acceptedDevices: PointerDevice.TouchScreen
            onActiveChanged: {
                if (active) {
                    lockScreenRoot.touched = true;
                    lockScreenRoot.uiVisible = true;
                }
                fadeoutTimer.restart();
            }
        }
"""),
    ("""                    lockScreenRoot.uiVisible = false;
                }
            }
        }
""",
     """                    lockScreenRoot.uiVisible = false;
                    lockScreenRoot.touched = false;
                }
            }
        }
"""),
]


def patch(text):
    """The changed text, or None when the file does not look like the one this was written for."""
    if MARK in text:
        return text                                   # already done
    for old, new in CHANGES:
        if text.count(old) != 1:
            return None
        text = text.replace(old, new)
    return text


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
    original = path.read_text()
    patched = patch(original)
    if patched is None:
        print("WARNING: the layout of %s changed, the lock screen is left as it is (password field hides when the finger lifts)" % path)
    elif patched != original:
        path.write_text(patched)
        print("patched", path)
    else:
        print("already patched", path)


if __name__ == "__main__":
    main()
