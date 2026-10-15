// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PlasmaComponents3
import org.kde.coreaddons as KCoreAddons
import Qt.labs.folderlistmodel

// The keypad of a PIN (PinPad.qml) or the nine dots of a pattern (PatternPad.qml), under the user on the lock screen and on the login screen (both load this file;
// see ci/patch_unlock_pad.py). The text typed or drawn is kept in the password field of the screen, which stays
// the only place the screen reads it from: this pad edits it (edited) and asks the screen to try it (submit), as Enter would.
//
// Which pad the user has chosen is told by an empty picture in /var/lib/surface-overdrive/unlock/<user>/ (see overdrive/unlock.py):
// pin.svg or pattern.svg, and state/blocked.svg after too many wrong tries, when only the password is accepted until it is used.
ColumnLayout {
    id: pad

    property string user                    // login name of the user the screen is about to unlock; empty: the user running it
    readonly property string login: user || me.loginName
    property string code                    // what is in the password field of the screen (bound by the screen)
    property string displayName             // shown above the pad, which takes the place of the face and name of the user
    property bool usePassword: false        // the user asked for the password field instead of the pad
    readonly property string folder: login ? "file:///var/lib/surface-overdrive/unlock/" + encodeURIComponent(login) : ""
    readonly property string mode: marks.has("pin.svg") ? "pin" : marks.has("pattern.svg") ? "pattern" : ""
    readonly property bool blocked: mode !== "" && stateMarks.has("blocked.svg")
    readonly property int pinLength: mode === "pin" ? marks.number("pin-length-") : 0
    // the screen hides its password field while this is true
    readonly property bool active: mode !== "" && !usePassword && !blocked

    signal edited(string code)
    signal submit()
    signal passwordWanted()

    // a wrong code: shake and clear (whether that was one try too many shows by itself: the folders are watched)
    function failed() {
        shake.restart()
        edited("")
    }
    onLoginChanged: usePassword = false
    // with the password field out of the way the pad takes the keys: digits, Backspace and Enter of a keyboard work as on the pad
    onActiveChanged: if (active) Qt.callLater(() => pad.forceActiveFocus())
    Keys.onPressed: event => {
        if (!active) return
        if (event.key === Qt.Key_Backspace) { edited(code.slice(0, -1)); event.accepted = true }
        else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { if (mode === "pin" && code.length >= 4) submit(); event.accepted = true }
        else if (mode === "pin" && event.text.length === 1 && event.text >= "0" && event.text <= "9") { pinPad.type(event.text); event.accepted = true }
    }
    onBlockedChanged: if (blocked) passwordWanted()
    Component.onCompleted: if (active) pad.forceActiveFocus()

    KCoreAddons.KUser { id: me }
    component Marks: FolderListModel {
        showDirs: false
        nameFilters: ["*.svg"]
        // revision is what bindings see change (a file replaced by another leaves count as it was); the names are looked up then
        property int revision: 0
        onRowsInserted: revision++
        onRowsRemoved: revision++
        onModelReset: revision++
        // n of the first file named <prefix><n>.svg, 0 when there is none
        function number(prefix) {
            if (revision < 0) return 0
            for (let i = 0; i < count; i++) {
                const name = get(i, "fileName")
                if (name.startsWith(prefix) && name.endsWith(".svg")) return parseInt(name.slice(prefix.length, -4)) || 0
            }
            return 0
        }
        function has(name) {
            if (revision < 0) return false
            for (let i = 0; i < count; i++) if (get(i, "fileName") === name) return true
            return false
        }
    }
    Marks { id: marks; folder: pad.folder }
    Marks { id: stateMarks; folder: pad.folder ? pad.folder + "/state" : "" }

    spacing: Kirigami.Units.largeSpacing
    visible: mode !== ""

    readonly property real key: Kirigami.Units.gridUnit * 2.9
    // only on a screen too short for the classic keypad: four keys wide and three rows high, Delete and 0 at the end of the first two
    // rows, so that the actions of the screen (Sleep, Restart...) still fit under it
    readonly property bool wide: Window.window ? Window.window.height < Kirigami.Units.gridUnit * 36 : false

    SequentialAnimation {
        id: shake
        loops: 1
        NumberAnimation { target: shaken; property: "x"; to: -Kirigami.Units.gridUnit; duration: 50 }
        NumberAnimation { target: shaken; property: "x"; to: Kirigami.Units.gridUnit; duration: 80 }
        NumberAnimation { target: shaken; property: "x"; to: -Kirigami.Units.gridUnit * 0.5; duration: 70 }
        NumberAnimation { target: shaken; property: "x"; to: 0; duration: 60 }
    }

    Item {
        Layout.alignment: Qt.AlignHCenter
        visible: pad.active
        implicitWidth: shaken.implicitWidth
        implicitHeight: shaken.implicitHeight

        ColumnLayout {
            id: shaken
            spacing: Kirigami.Units.largeSpacing
            PlasmaComponents3.Label {
                Layout.alignment: Qt.AlignHCenter
                visible: pad.displayName.length > 0
                text: pad.displayName
                font.pointSize: Kirigami.Theme.defaultFont.pointSize + 4
                textFormat: Text.PlainText
            }
            PinPad {
                id: pinPad
                visible: pad.mode === "pin"
                code: pad.code
                key: pad.key
                wide: pad.wide
                length: pad.pinLength
                onEdited: code => pad.edited(code)
                onSubmit: pad.submit()
            }
            PatternPad {
                Layout.alignment: Qt.AlignHCenter
                visible: pad.mode === "pattern"
                key: pad.key
                onDrawn: dots => {
                    if (dots.length < 4) {
                        pad.failed()
                        return
                    }
                    pad.edited(dots)
                    pad.submit()
                }
            }
        }
    }

    PlasmaComponents3.Label {
        Layout.alignment: Qt.AlignHCenter
        Layout.maximumWidth: Kirigami.Units.gridUnit * 20
        visible: pad.blocked
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
        text: pad.mode === "pin" ? "Too many wrong PINs. Use your password; the PIN works again after that."
                                 : "Too many wrong patterns. Use your password; the pattern works again after that."
    }

    PlasmaComponents3.ToolButton {
        Layout.alignment: Qt.AlignHCenter
        visible: !pad.blocked
        text: pad.active ? "Use Password" : pad.mode === "pin" ? "Use PIN" : "Use Pattern"
        icon.name: pad.active ? "lock-symbolic" : pad.mode === "pin" ? "input-dialpad-symbolic" : "view-grid-symbolic"
        onClicked: {
            pad.edited("")
            pad.usePassword = !pad.usePassword
            if (pad.usePassword) pad.passwordWanted()
        }
    }
}
