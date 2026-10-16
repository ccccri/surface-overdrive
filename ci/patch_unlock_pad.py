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

LOADER = """    %(mark)s the keypad of a PIN or the dots of a pattern, when the user chose one (/usr/share/surface-overdrive/unlock/UnlockPad.qml).
    // While it is in use the face and name of the user give way to it: the pad shows the name itself and the column of the prompts
    // moves up into their place (moving the column, not the pad: a screen delivers touches only inside the item that holds them),
    // so that the classic keypad fits above the actions.
    Item {
        id: overdrivePadSlot
        readonly property real lift: overdrivePad.padActive && overdrivePad.users ? overdrivePad.users.height : 0
        Layout.alignment: Qt.AlignHCenter
        Layout.preferredWidth: overdrivePad.implicitWidth
        // all the room the screen has (the actions stay at the bottom), the pad in its middle
        Layout.preferredHeight: overdrivePad.padActive ? Math.max(overdrivePad.implicitHeight, overdrivePad.item.room) : overdrivePad.implicitHeight
        Loader {
            id: overdrivePad
            anchors.horizontalCenter: parent.horizontalCenter
            y: Math.max(0, (parent.height - height) / 2)
            readonly property bool padActive: item !== null && item.active
            readonly property Item users: %(users)s
            source: "%(pad)s"
            onLoaded: {
                item.user = Qt.binding(() => %(user)s)          // "": the user of this session
                item.code = Qt.binding(() => passwordBox.text)
                item.displayName = Qt.binding(() => overdrivePad.padActive && overdrivePad.users && overdrivePad.users.currentItem
                                              ? overdrivePad.users.currentItem.name : "")
                try {
                    // hidden and out of the way: on the login screen the list scrolls, and would take the drags of a pattern
                    overdrivePad.users.opacity = Qt.binding(() => overdrivePad.padActive ? 0 : 1)
                    overdrivePad.users.enabled = Qt.binding(() => !overdrivePad.padActive)
                    // the column of the prompts is at most ten grid units high, made for a password field: give the pad the room
                    // it needs (only taken when the screen has it; the action buttons below stay where they are)
                    const box = overdrivePadSlot.parent.parent
                    box.Layout.maximumHeight = Qt.binding(() => Math.max(Kirigami.Units.gridUnit * 10,
                                                                         overdrivePadSlot.Layout.preferredHeight + Kirigami.Units.largeSpacing))
                    // and as wide as the pad (the column is made sixteen grid units wide at most, for a password field)
                    box.Layout.maximumWidth = Qt.binding(() => Math.max(Kirigami.Units.gridUnit * 16, overdrivePadSlot.Layout.preferredWidth))
                    const prompts = box.parent
                    prompts.anchors.topMargin = Qt.binding(() => Kirigami.Units.largeSpacing - overdrivePadSlot.lift)
                    // the column is: messages, prompts, actions, filler, and it runs past the bottom of the screen. The pad gets the
                    // height from the top of the column to the bottom of the window that the messages, the actions and the bottom row
                    // of the screen (keyboard button, battery) leave, so that the actions stay above that row
                    const messages = prompts.children[0], actions = prompts.children[2]
                    const top = () => { let y = 0; for (let i = prompts; i; i = i.parent) y += i.y; return y }
                    item.room = Qt.binding(() => (prompts.Window.window ? prompts.Window.window.height : prompts.height) - top()
                                                 - messages.height - actions.height - 3 * prompts.spacing - Kirigami.Units.gridUnit * 3)
                } catch (e) {
                    console.warn("Surface Overdrive: could not make room for the unlock pad:", e)
                }
            }
            // inside the Loader: the column of the screen takes visual items only
            Connections {
                target: overdrivePad.item
                function onEdited(code) { passwordBox.text = code }
                function onSubmit() { if (passwordBox.text.length > 0) %(login)s }
                function onPasswordWanted() { Qt.callLater(() => passwordBox.forceActiveFocus()) }
            }
            Connections {
                target: %(auth)s
                %(failed)s
            }
        }
    }

"""

TARGETS = {
    "lockscreen": {
        "path": "/usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen/MainBlock.qml",
        "changes": [
            (FIELD_ROW, FIELD_ROW_NEW),
            ("    component FailableLabel : PlasmaComponents3.Label {\n",
             LOADER % dict(mark=MARK, pad=PAD, user='""', users="sessionManager.userList", login="sessionManager.startLogin()",
                           auth="authenticator",
                           failed="function onFailed(kind) { if (kind == 0 && overdrivePad.item) overdrivePad.item.failed() }")
             + "    component FailableLabel : PlasmaComponents3.Label {\n"),
        ],
    },
    "login": {
        "path": None,
        "changes": [
            (FIELD_ROW, FIELD_ROW_NEW),
            ("    // Synchronise state\n",
             LOADER % dict(mark=MARK, pad=PAD, user="root.showUsernamePrompt ? userNameInput.text : root.userList.selectedUser",
                           users="root.showUsernamePrompt ? null : root.userList", login="root.startLogin()",
                           auth="PlasmaLogin.Authenticator",
                           failed="function onLoginFailed() { if (overdrivePad.item) overdrivePad.item.failed() }")
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
