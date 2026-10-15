// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// A keypad for a PIN: one dot per digit typed above the keys. The digits are not kept here: code comes from whoever owns them and
// every key asks for a new value (edited), so that the lock screen can keep the PIN in its password field. Used by UnlockPad.qml
// (lock and login screens) and by the Screen Locking page of System Settings.
ColumnLayout {
    id: pin

    property string code
    property real key: Kirigami.Units.gridUnit * 2.9
    // four keys wide and three rows high, Delete and 0 at the end of the first two rows: for a screen short of height
    property bool wide: false
    readonly property int longest: 12

    signal edited(string code)
    signal submit()

    spacing: Kirigami.Units.largeSpacing

    function type(digit) { if (code.length < longest) edited(code + digit) }
    function erase() { edited(code.slice(0, -1)) }

    Row {
        Layout.alignment: Qt.AlignHCenter
        Layout.preferredHeight: Kirigami.Units.gridUnit
        spacing: Kirigami.Units.smallSpacing * 2
        Repeater {
            model: pin.code.length
            Rectangle {
                width: Kirigami.Units.gridUnit * 0.6
                height: width
                radius: width / 2
                color: Kirigami.Theme.textColor
            }
        }
    }

    Grid {
        Layout.alignment: Qt.AlignHCenter
        columns: pin.wide ? 4 : 3
        spacing: Kirigami.Units.largeSpacing
        Repeater {
            model: pin.wide ? ["1", "2", "3", "back", "4", "5", "6", "0", "7", "8", "9", "go"]
                            : ["1", "2", "3", "4", "5", "6", "7", "8", "9", "back", "0", "go"]
            delegate: QQC2.AbstractButton {
                id: keyButton
                required property string modelData
                readonly property bool digit: modelData.length === 1
                width: pin.key
                height: pin.key
                enabled: modelData !== "go" || pin.code.length >= 4
                focusPolicy: Qt.NoFocus
                Accessible.name: modelData === "back" ? "Delete" : modelData === "go" ? "Done" : modelData
                background: Rectangle {
                    radius: width / 2
                    color: Kirigami.Theme.textColor
                    opacity: keyButton.pressed ? 0.3 : keyButton.digit ? 0.12 : 0
                }
                contentItem: Item {
                    QQC2.Label {
                        anchors.centerIn: parent
                        visible: keyButton.digit
                        text: keyButton.modelData
                        font.pointSize: Kirigami.Theme.defaultFont.pointSize * 2
                    }
                    Kirigami.Icon {
                        anchors.centerIn: parent
                        visible: !keyButton.digit
                        width: Kirigami.Units.iconSizes.smallMedium
                        height: width
                        opacity: keyButton.enabled ? 1 : 0.4
                        source: keyButton.modelData === "back" ? "edit-clear-symbolic"
                                : (keyButton.LayoutMirroring.enabled ? "go-previous" : "go-next")
                    }
                }
                onClicked: {
                    if (modelData === "back") pin.erase()
                    else if (modelData === "go") pin.submit()
                    else pin.type(modelData)
                }
            }
        }
    }
}
