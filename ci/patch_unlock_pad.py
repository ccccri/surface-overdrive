#!/usr/bin/env python3
"""Put the PIN keypad or pattern dots (image/rootfs/usr/share/surface-overdrive/unlock/UnlockPad.qml) under the user on the lock screen
and on the login screen.

The pad itself lives in its own file, loaded at run time; the screens get a Loader for it, hide their password field while the pad is
in use, and give the pad what it needs: the user, the text of the password field (the pad edits that field, so the screen logs in
with it exactly as with a typed password) and the news of a wrong try.

  lockscreen   MainBlock.qml of Plasma's lock screen (plasma-desktop's look and feel, patched in the image build)
  login        Login.qml in the source tree of plasma-login-manager (compiled into the greeter, see ci/build_srpm.sh)

When a file has a layout this was not written for, it is left alone with a warning: that screen then has the password field only.

usage: patch_unlock_pad.py lockscreen|login [path]
"""
import sys
from pathlib import Path

MARK = "// Surface Overdrive:"
PAD = "file:///usr/share/surface-overdrive/unlock/UnlockPad.qml"

FIELD_ROW = """    RowLayout {
        Layout.fillWidth: true

        PlasmaExtras.PasswordField {
            id: passwordBox
"""
FIELD_ROW_NEW = """    RowLayout {
        Layout.fillWidth: true
        %s the pad below takes the place of the password field while it is in use; disabled too, so that the field
        // does not keep the focus and bring up the on-screen keyboard over the pad
        visible: !overdrivePad.padActive
        enabled: !overdrivePad.padActive

        PlasmaExtras.PasswordField {
            id: passwordBox
""" % MARK

LOADER = """    %s the keypad of a PIN or the dots of a pattern, when the user chose one (/usr/share/surface-overdrive/unlock/UnlockPad.qml)
    Loader {
        id: overdrivePad
        readonly property bool padActive: item !== null && item.active
        Layout.alignment: Qt.AlignHCenter
        source: "%s"
        onLoaded: {
            item.user = Qt.binding(() => %s)          // "": the user of this session
            item.code = Qt.binding(() => passwordBox.text)
            // the column of the prompts is at most ten grid units high, made for a password field: give the pad the room it needs
            // (only taken when the screen has it; the action buttons below stay where they are)
            try {
                const box = overdrivePad.parent.parent
                box.Layout.maximumHeight = Qt.binding(() => Math.max(Kirigami.Units.gridUnit * 10, overdrivePad.implicitHeight + Kirigami.Units.largeSpacing))
            } catch (e) {
                console.warn("Surface Overdrive: could not make room for the unlock pad:", e)
            }
        }
        // inside the Loader: the column of the screen takes visual items only
        Connections {
            target: overdrivePad.item
            function onEdited(code) { passwordBox.text = code }
            function onSubmit() { if (passwordBox.text.length > 0) %s }
            function onPasswordWanted() { Qt.callLater(() => passwordBox.forceActiveFocus()) }
        }
        Connections {
            target: %s
            %s
        }
    }

"""

TARGETS = {
    "lockscreen": {
        "path": "/usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen/MainBlock.qml",
        "changes": [
            (FIELD_ROW, FIELD_ROW_NEW),
            ("    component FailableLabel : PlasmaComponents3.Label {\n",
             LOADER % (MARK, PAD, '""', "sessionManager.startLogin()", "authenticator",
                       "function onFailed(kind) { if (kind == 0 && overdrivePad.item) overdrivePad.item.failed() }")
             + "    component FailableLabel : PlasmaComponents3.Label {\n"),
        ],
    },
    "login": {
        "path": None,
        "changes": [
            (FIELD_ROW, FIELD_ROW_NEW),
            ("    // Synchronise state\n",
             LOADER % (MARK, PAD, "root.showUsernamePrompt ? userNameInput.text : root.userList.selectedUser", "root.startLogin()",
                       "PlasmaLogin.Authenticator",
                       "function onLoginFailed() { if (overdrivePad.item) overdrivePad.item.failed() }")
             + "    // Synchronise state\n"),
        ],
    },
}


def patch(text, target):
    """The changed text, the same text when already changed, None when the file does not look like the one this was written for."""
    if MARK in text:
        return text
    for old, new in TARGETS[target]["changes"]:
        if text.count(old) != 1:
            return None
        text = text.replace(old, new)
    return text


def main(argv):
    if not argv or argv[0] not in TARGETS or (len(argv) < 2 and not TARGETS[argv[0]]["path"]):
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    path = Path(argv[1] if len(argv) > 1 else TARGETS[argv[0]]["path"])
    original = path.read_text()
    patched = patch(original, argv[0])
    if patched is None:
        print("WARNING: the layout of %s changed, that screen keeps the password field only (no PIN or pattern pad)" % path)
    elif patched != original:
        path.write_text(patched)
        print("patched", path)
    else:
        print("already patched", path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
