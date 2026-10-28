#!/usr/bin/env python3
"""Defaults of Plasma that the owner chose, made in the image build.

  panel   The panel of a new desktop: at the bottom, centred, out of the way of windows (dodge windows), translucent and
          floating. Appended to Plasma's default panel template, which every global theme loads, so it also applies when the
          desktop layout is reset from the global theme.
  noface  No user picture on the lock screen, the login screen and the shutdown screen: the name stays, in the same place. The
          picture is drawn by UserDelegate.qml of the module org.kde.breeze.components, which all three use. The module is
          compiled into its plugin and its qmldir says to prefer the compiled files, so the edited file on disk counts only
          once that "prefer" line is gone (the other files of the module on disk are the same as the compiled ones).
          The picture can still be chosen in System Settings, and the launcher (Kickoff, compiled) still shows it.

When a file has a layout this was not written for, it is left as it is and the build goes on with a warning.

usage: patch_plasma_defaults.py panel|noface [path]
"""
import sys
from pathlib import Path

MARK = "// Surface Overdrive:"

PANEL_DEFAULT = "/usr/share/plasma/layout-templates/org.kde.plasma.desktop.defaultPanel/contents/layout.js"
PANEL_ANCHOR = 'panel.addWidget("org.kde.plasma.kickoff")'
PANEL_LINES = """%s the owner's panel: at the bottom, centred, out of the way of windows, translucent, floating
panel.location = "bottom"
panel.alignment = "center"
panel.hiding = "dodgewindows"
panel.opacity = "translucent"
panel.floating = true

""" % MARK

FACE_DIR = "/usr/lib64/qt6/qml/org/kde/breeze/components"
FACE_CHANGES = [
    # the translucent circle under the picture
    ("""        color: Kirigami.Theme.backgroundColor
        opacity: 0.6
    }
""",
     """        color: Kirigami.Theme.backgroundColor
        opacity: 0.6
        %s no user picture anywhere (the name stays where it was)
        visible: false
    }
""" % MARK),
    # the picture (or icon) itself: it keeps its size, so that the name does not move
    ("""        id: imageSource
""",
     """        id: imageSource
        visible: false
"""),
    # the rounded copy of the picture that is actually drawn
    ("""    ShaderEffect {
""",
     """    ShaderEffect {
        visible: false
"""),
]


def patch_panel(text):
    if MARK in text:
        return text
    if text.count(PANEL_ANCHOR) != 1:
        return None
    return text.replace(PANEL_ANCHOR, PANEL_LINES + PANEL_ANCHOR)


def patch_face(text):
    if MARK in text:
        return text
    for old, new in FACE_CHANGES:
        if text.count(old) != 1:
            return None
        text = text.replace(old, new)
    return text


def patch_qmldir(text):
    """Without the "prefer" line the files on disk are used (None when there is no such line to drop)."""
    lines = text.splitlines(keepends=True)
    kept = [line for line in lines if not line.startswith("prefer ")]
    if len(kept) == len(lines):
        return None
    return "".join(kept)


def write(path, original, patched, what):
    if patched is None:
        print("WARNING: the layout of %s changed, %s is left as Plasma has it" % (path, what))
        return False
    if patched != original:
        path.write_text(patched)
        print("patched", path)
    else:
        print("already patched", path)
    return True


def main(argv):
    if len(argv) < 2 or argv[1] not in ("panel", "noface"):
        print(__doc__)
        return 2
    if argv[1] == "panel":
        path = Path(argv[2] if len(argv) > 2 else PANEL_DEFAULT)
        text = path.read_text()
        write(path, text, patch_panel(text), "the default panel")
        return 0
    folder = Path(argv[2] if len(argv) > 2 else FACE_DIR)
    delegate, qmldir = folder / "UserDelegate.qml", folder / "qmldir"
    text = delegate.read_text()
    patched = patch_face(text)
    if patched is None:
        print("WARNING: the layout of %s changed, the user picture stays" % delegate)
        return 0
    qtext = qmldir.read_text()
    qpatched = qtext if MARK in text else patch_qmldir(qtext)
    if qpatched is None and "prefer " in qtext:
        print("WARNING: cannot read %s, the user picture stays" % qmldir)
        return 0
    write(delegate, text, patched, "the user picture")
    if qpatched is not None and qpatched != qtext:
        qmldir.write_text(qpatched)
        print("patched", qmldir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
