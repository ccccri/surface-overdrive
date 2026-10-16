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
    Component.onCompleted: { if (active) pad.forceActiveFocus(); Qt.callLater(placeFooterToggle) }

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

    // Height the screen has for the pad (from under the name of the user to above its actions); 0 when it does not say. The keys or
    // dots are made as big as that allows, within reasonable bounds.
    property real room: 0
    readonly property real overhead: nameLabel.implicitHeight + shaken.spacing
    readonly property real smallest: Kirigami.Units.gridUnit * 2.4
    // never wider than four fifths of the screen (a phone held upright), and keys not bigger than a thumb needs
    readonly property real screenWidth: Window.window ? Window.window.width : Kirigami.Units.gridUnit * 40
    readonly property real biggest: Math.min(Kirigami.Units.gridUnit * (mode === "pattern" ? 8 : 5.5),
                                             screenWidth * 0.8 / (mode === "pattern" ? 3.4 : 3.44))
    readonly property real key: room <= 0 ? Kirigami.Units.gridUnit * 2.9
        : Math.max(smallest, Math.min(biggest, (mode === "pattern" ? patternPad : pinPad).keyFor(room - overhead)))
    // only when even the smallest classic keypad does not fit: four keys wide and three rows high
    readonly property bool wide: room > 0 && mode === "pin" && pinPadProbe.keyFor(room - overhead) < smallest
    QtObject {
        id: pinPadProbe
        function keyFor(h) { return (h - Kirigami.Units.gridUnit - Kirigami.Units.largeSpacing) / (4 + 3 * 0.22) }
    }

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
                id: nameLabel
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
                id: patternPad
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

    // A finger on a button outside the screen's own items arrives twice (as a touch and as the mouse click made from it), which
    // switched to the password and straight back: one switch per half second.
    property double lastToggle: 0
    function toggle() {
        const now = Date.now()
        if (now - lastToggle < 500) return
        lastToggle = now
        edited("")
        usePassword = !usePassword
        if (usePassword) passwordWanted()
    }
    // with the password field: the way back to the pad, under the field
    PlasmaComponents3.ToolButton {
        Layout.alignment: Qt.AlignHCenter
        visible: !pad.blocked && !pad.active
        text: pad.mode === "pin" ? "Use PIN" : "Use Pattern"
        icon.name: pad.mode === "pin" ? "input-dialpad-symbolic" : "view-grid-symbolic"
        onClicked: pad.toggle()
    }
    // with the pad: "Use Password" sits in the bottom row of the screen, between its keyboard button and the battery, so that the
    // pad has the height. It fades in and out with the rest of the screen (the product of the opacities above the pad).
    Component {
        id: footerToggleComponent
        PlasmaComponents3.ToolButton {
            z: 100
            // light on the dark picture, like the rest of the screen (outside the screen's items it would not inherit that)
            Kirigami.Theme.inherit: false
            Kirigami.Theme.colorSet: Kirigami.Theme.Complementary
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: Kirigami.Units.smallSpacing
            visible: pad.active && pad.visible && opacity > 0
            opacity: {
                let o = 1
                for (let item = pad; item; item = item.parent) o *= item.opacity
                return o
            }
            text: "Use Password"
            icon.name: "lock-symbolic"
            onClicked: pad.toggle()
        }
    }
    property Item footerToggle: null
    function placeFooterToggle() {
        if (footerToggle || !Window.window) return
        footerToggle = footerToggleComponent.createObject(Window.window.contentItem)
    }
}
