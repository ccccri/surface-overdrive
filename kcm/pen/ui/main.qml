// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kcmutils as KCM
import org.kde.kirigami as Kirigami
import org.surfaceoverdrive.kcm

KCM.SimpleKCM {
    id: root

    property var info: ({ digitizer: [], fakeBattery: [], bluetooth: [], filter: "on" })

    // ---- what the pen test has seen ----
    property string state: "none"          // none | away | hover | touch
    property string tool: "-"
    property real pressure: 0
    property real maxPressure: 0
    property real xTilt: 0
    property real yTilt: 0
    property bool tiltSeen: false
    property int buttons: 0
    property bool eventsSeen: false
    property real lastX: -1
    property real lastY: -1
    readonly property bool barrelDown: (buttons & Qt.RightButton) !== 0
    readonly property bool eraserDown: tool === "Eraser" || (buttons & Qt.MiddleButton) !== 0

    function reload() { kcm.call("pen", ["pen"]) }
    Component.onCompleted: reload()
    Connections {
        target: kcm
        function onCallFinished(tag, ok, output, error) {
            if (tag === "pen" && ok) {
                try { root.info = JSON.parse(output) } catch (e) {}
            }
        }
    }
    Timer { interval: 5000; repeat: true; running: true; onTriggered: root.reload() }

    function clearTest() {
        canvas.clear()
        maxPressure = 0; tiltSeen = false
    }

    PenMonitor {
        active: root.visible
        onPenEvent: (kind, tool, x, y, pressure, tx, ty, rotation, buttons) => {
            root.eventsSeen = true
            root.tool = tool === "eraser" ? "Eraser" : "Tip"
            if (kind === "leave") { root.state = "away"; root.lastX = -1; return }
            root.pressure = pressure
            root.xTilt = tx; root.yTilt = ty
            if (Math.abs(tx) > 0.5 || Math.abs(ty) > 0.5) root.tiltSeen = true
            root.buttons = buttons
            const touching = pressure > 0 || (buttons & Qt.LeftButton)
            root.state = touching ? "touch" : "hover"
            if (pressure > 0) root.maxPressure = Math.max(root.maxPressure, pressure)
            const p = canvas.mapFromItem(null, x, y)
            if (touching && p.x >= 0 && p.y >= 0 && p.x <= canvas.width && p.y <= canvas.height) {
                if (root.lastX >= 0) canvas.addSegment(root.lastX, root.lastY, p.x, p.y, pressure, tool === "eraser")
                root.lastX = p.x; root.lastY = p.y
            } else root.lastX = -1
        }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: true
            type: root.info.digitizer.length > 0 ? Kirigami.MessageType.Positive : Kirigami.MessageType.Warning
            text: root.info.digitizer.length > 0 ? i18n("Touch and pen input detected.") : i18n("No touch or pen input found.")
        }

        Kirigami.Heading { level: 3; text: i18n("Pen test") }
        QQC2.Label {
            Layout.fillWidth: true; wrapMode: Text.WordWrap; opacity: 0.7
            text: i18n("Draw in the area below: the line gets thicker with pressure. Hold the top button (the eraser button) and draw to erase. Hover first, press the side button, tilt the pen: the readout shows what the tablet and the pen report.")
        }

        GridLayout {
            Layout.fillWidth: true
            columns: width > Kirigami.Units.gridUnit * 40 ? 2 : 1
            columnSpacing: Kirigami.Units.largeSpacing
            rowSpacing: Kirigami.Units.largeSpacing

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 16
                color: "white"
                border.color: Kirigami.Theme.disabledTextColor
                radius: 4
                clip: true
                Canvas {
                    id: canvas
                    anchors.fill: parent
                    property var queue: []
                    function clear() { const c = getContext("2d"); c.clearRect(0, 0, width, height); requestPaint() }
                    function addSegment(x1, y1, x2, y2, p, erase) { queue.push([x1, y1, x2, y2, p, erase]); requestPaint() }
                    onPaint: {
                        const c = getContext("2d")
                        c.lineCap = "round"
                        for (const s of queue) {
                            c.beginPath()
                            c.strokeStyle = s[5] ? "#ffffff" : "#1b3a6b"
                            c.lineWidth = s[5] ? 24 : 1 + s[4] * 14
                            c.moveTo(s[0], s[1]); c.lineTo(s[2], s[3]); c.stroke()
                        }
                        queue = []
                    }
                }
                QQC2.Label { anchors.centerIn: parent; text: i18n("Touch the screen with the pen here"); color: "#888"; visible: !root.eventsSeen }
                QQC2.Button {
                    anchors { right: parent.right; top: parent.top; margins: 6 }
                    text: i18n("Clear"); icon.name: "edit-clear-all"
                    onClicked: root.clearTest()
                }
            }

            // plain grid with fixed cells: the readout changes dozens of times a second
            GridLayout {
                Layout.alignment: Qt.AlignTop
                columns: 2
                columnSpacing: Kirigami.Units.largeSpacing
                rowSpacing: Kirigami.Units.smallSpacing
                component Name: QQC2.Label { Layout.preferredWidth: Kirigami.Units.gridUnit * 6; Layout.alignment: Qt.AlignRight; horizontalAlignment: Text.AlignRight; opacity: 0.7 }
                component Val: QQC2.Label { Layout.preferredWidth: Kirigami.Units.gridUnit * 13; elide: Text.ElideRight }

                Name { text: i18n("Pen:") }
                Val { text: root.state === "none" ? i18n("no pen seen yet") : root.state === "away" ? i18n("out of range") : root.state === "hover" ? i18n("hovering") : i18n("touching the screen") }
                Name { text: i18n("Tool:") }
                Val { text: root.tool }
                Name { text: i18n("Pressure:") }
                RowLayout {
                    QQC2.ProgressBar { Layout.preferredWidth: Kirigami.Units.gridUnit * 8; from: 0; to: 1; value: root.pressure }
                    QQC2.Label { text: Math.round(root.pressure * 100) + "%  (max " + Math.round(root.maxPressure * 100) + "%)" }
                }
                Name { text: i18n("Tilt:") }
                Val { text: root.tiltSeen ? "X " + root.xTilt.toFixed(0) + "°   Y " + root.yTilt.toFixed(0) + "°" : i18n("not reported") }
                Name { text: i18n("Buttons now:") }
                RowLayout {
                    spacing: Kirigami.Units.smallSpacing
                    Repeater {
                        model: [{ n: i18n("Barrel (side)"), on: root.barrelDown }, { n: i18n("Eraser (top)"), on: root.eraserDown }]
                        delegate: Rectangle {
                            Layout.preferredWidth: Kirigami.Units.gridUnit * 6; Layout.preferredHeight: Kirigami.Units.gridUnit * 1.6; radius: 4
                            color: modelData.on ? Kirigami.Theme.highlightColor : "transparent"
                            border.color: Kirigami.Theme.disabledTextColor
                            QQC2.Label { anchors.centerIn: parent; text: modelData.n; color: modelData.on ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor }
                        }
                    }
                }
            }
        }

        Kirigami.Heading { level: 3; text: i18n("Bluetooth pen") }
        QQC2.Label {
            Layout.fillWidth: true; wrapMode: Text.WordWrap
            text: root.info.bluetooth.length === 0 ? i18n("No paired pen found.")
                  : root.info.bluetooth.map(d => d.name + ": " + (d.connected ? i18n("connected") + (d.battery >= 0 ? i18n(", battery %1%", d.battery) : "")
                                                                   : i18n("paired, not connected (press a pen button to wake it)"))).join("\n")
        }

        Kirigami.Heading { level: 3; text: i18n("Fake battery") }
        QQC2.Switch {
            text: i18n("Hide the fake pen battery")
            checked: root.info.filter === "on"
            enabled: !kcm.busy
            onToggled: kcm.changeSetting("stylus-filter", checked ? "on" : "off")
        }
        QQC2.Label {
            Layout.fillWidth: true; wrapMode: Text.WordWrap; opacity: 0.7
            text: i18n("The touchscreen advertises a pen battery that never carries data, so Plasma shows a pen at 0% or a phantom device. A small filter in the kernel hides it. Turning the filter off applies after a restart.")
        }
        QQC2.Label {
            visible: root.info.fakeBattery.length > 0 && root.info.filter === "on"
            Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Kirigami.Theme.neutralTextColor
            text: i18n("The fake battery is still showing (%1): restart the tablet for the filter to take effect.", root.info.fakeBattery.join(", "))
        }
        Kirigami.InlineMessage {
            id: failNote
            Layout.fillWidth: true
            visible: text.length > 0
            type: Kirigami.MessageType.Error
        }
    }
    Connections {
        target: kcm
        function onChangeFinished(ok, message) {
            failNote.text = ok ? "" : (message || i18n("The change was not applied."))
            root.reload()
        }
    }
}
