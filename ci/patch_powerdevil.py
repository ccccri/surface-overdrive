#!/usr/bin/env python3
"""The Brightness & Color popup of the panel (powerdevil's brightness applet) scrolls up and down only, in its source tree.

Its scroll view hides the horizontal scroll bar but leaves the content as wide as it would like to be, a little wider than the
popup: dragged with a finger, the whole page slid sideways too, cutting off labels and buttons. The content now takes the
popup's width (contentWidth: availableWidth), so a drag scrolls only vertically, as in the other popups of the panel. The QML
is compiled into the plugin, so the change is made in the source tree and the package is rebuilt (ci/build_powerdevil.sh).

When the file has a layout this was not written for, nothing is changed and the build goes on with Fedora's package. The
same when the scroll view already sets a contentWidth: that is Plasma's own fix (not there in 6.8.2 nor in master on
2026-11-07), and a second one would be a QML error that breaks the build; Fedora's package is then used as it is, and
this patch (with ci/build_powerdevil.sh and its stage in the Containerfile) can go.

usage: patch_powerdevil.py <source tree>
"""
import sys
from pathlib import Path

CHANGES = {
    "applets/brightness/PopupDialog.qml": [
        ("""    contentItem: PlasmaComponents3.ScrollView {
        id: scrollView
        PlasmaComponents3.ScrollBar.horizontal.visible: false
""", """    contentItem: PlasmaComponents3.ScrollView {
        id: scrollView
        PlasmaComponents3.ScrollBar.horizontal.visible: false
        // Surface Overdrive: as wide as the popup, so that a finger scrolls it up and down only, never sideways
        contentWidth: availableWidth
"""),
    ],
}


def patch(root):
    root = Path(root)
    edits = []
    for rel, pairs in CHANGES.items():
        path = root / rel
        if not path.exists():
            print("skipped: %s not found" % rel)
            return False
        text = path.read_text()
        if "contentWidth" in text:
            print("skipped: %s already sets contentWidth (fixed by Plasma, Fedora's package is fine)" % rel)
            return False
        for old, new in pairs:
            if text.count(old) != 1:
                print("skipped: %s has another layout" % rel)
                return False
            text = text.replace(old, new)
        edits.append((path, text))
    for path, text in edits:
        path.write_text(text)
    print("patched: brightness popup scrolls vertically only")
    return True


if __name__ == "__main__":
    patch(sys.argv[1])
