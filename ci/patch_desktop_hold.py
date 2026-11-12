#!/usr/bin/env python3
"""The desktop goes into edit mode after a longer hold (HOLD seconds) than Qt's press-and-hold.

Plasma's desktop enters edit mode (panels, widgets) when a finger stays on an empty spot, or on a widget, for Qt's
press-and-hold time, 0.8 s, which is also what opens context menus by touch everywhere else. On the tablet, touch gestures
and ordinary use kept hitting it. The desktop's own trigger is turned off (editModeCondition Manual, for the desktop and
the widgets on it, in main.qml) and the desktop's own press handler (FolderView.qml, which sees every press on the empty
desktop) turns edit mode on after HOLD seconds on an empty spot: the finger moving, lifting or being taken by a gesture
stops it. A three-finger swipe to another desktop (Moonlight's) took the finger without a release or a cancel reaching the
desktop, and edit mode came on behind the stream 2 s later (2026-11-12): the hold also stops when the virtual desktop
changes or another app's window becomes the active one. Context menus by touch keep Qt's time; edit mode is still in the
desktop's right-click menu.

When a file has a layout this was not written for, neither is changed (Plasma's own behaviour stays) and the build says so.

usage: patch_desktop_hold.py [containment ui directory]
"""
import sys
from pathlib import Path

DEFAULT = "/usr/share/plasma/plasmoids/org.kde.desktopcontainment/contents/ui"
HOLD_MS = 2000
MARK = "// Surface Overdrive:"

MAIN = [
    ("""                    : ContainmentLayoutManager.AppletsLayout.AfterPressAndHold""",
     """                    : ContainmentLayoutManager.AppletsLayout.Manual %s edit mode after a longer hold: FolderView.qml"""
     % MARK),
    ("""                    : ContainmentLayoutManager.ItemContainer.AfterPressAndHold""",
     """                    : ContainmentLayoutManager.ItemContainer.Manual"""),
]

FOLDER = [
    # the virtual desktops, to stop the hold when a swipe changes desktop
    ("""import org.kde.kquickcontrolsaddons
""",
     """import org.kde.kquickcontrolsaddons
import org.kde.taskmanager as TaskManager
"""),
    # start on a press on an empty spot of the desktop
    ("""            pressX = mouse.x;
            pressY = mouse.y;
""",
     """            pressX = mouse.x;
            pressY = mouse.y;
            %s edit mode after a hold of %d ms on an empty spot (Qt's 0.8 s press-and-hold kept catching touch
            // gestures; the desktop's own trigger is Manual in main.qml)
            if (root.isContainment && main.isRootView && (!hoveredItem || hoveredItem.blank)
                && !(mouse.buttons & Qt.RightButton)) {
                editHoldTimer.x0 = mouse.x;
                editHoldTimer.y0 = mouse.y;
                editHoldTimer.restart();
            }
""" % (MARK, HOLD_MS)),
    # moving stops it
    ("""        onPositionChanged: mouse => {
""",
     """        onPositionChanged: mouse => {
            if (editHoldTimer.running && root.isDrag(editHoldTimer.x0, editHoldTimer.y0, mouse.x, mouse.y)) {
                editHoldTimer.stop();
            }
"""),
    # lifting stops it
    ("""        onReleased: mouse => {
""",
     """        onReleased: mouse => {
            editHoldTimer.stop();
"""),
    # and so does a cancel (a gesture took the finger); not clearPressState(): Qt's own press-and-hold calls it at 0.8 s.
    # A swipe to another desktop or another app's window coming up stops it too: KWin's gestures took the finger without
    # either reaching the desktop.
    ("""        function pressCanceled() {
""",
     """        Timer {
            id: editHoldTimer
            property real x0
            property real y0
            interval: %d
            onTriggered: if (!Plasmoid.immutable) Plasmoid.containment.corona.editMode = true
        }
        TaskManager.VirtualDesktopInfo {
            onCurrentDesktopChanged: editHoldTimer.stop()
        }
        Connections {
            target: Qt.application
            function onStateChanged() {
                if (Qt.application.state !== Qt.ApplicationActive) {
                    editHoldTimer.stop();
                }
            }
        }

        function pressCanceled() {
            editHoldTimer.stop();
""" % HOLD_MS),
]


def apply(text, pairs):
    """The text with every pair replaced, or None when it is already patched or one anchor is not there exactly once."""
    if MARK in text:
        return None
    for old, _ in pairs:
        if text.count(old) != 1:
            return None
    for old, new in pairs:
        text = text.replace(old, new)
    return text


def main(directory=DEFAULT):
    d = Path(directory)
    files = {d / "main.qml": MAIN, d / "FolderView.qml": FOLDER}
    new = {}
    for path, pairs in files.items():
        if not path.exists():
            print("skipped: %s not found (Plasma's 0.8 s hold stays)" % path)
            return False
        new[path] = apply(path.read_text(), pairs)
        if new[path] is None:
            print("skipped: %s has another layout or is already patched (Plasma's 0.8 s hold stays)" % path)
            return False
    for path, text in new.items():
        path.write_text(text)
    print("patched: desktop edit mode after a %d ms hold" % HOLD_MS)
    return True


if __name__ == "__main__":
    main(*sys.argv[1:])
