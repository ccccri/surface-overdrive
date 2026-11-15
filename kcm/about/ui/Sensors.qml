// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// What the Surface adds to "About this System": the firmware, the light sensor and the motion sensors, read live.
ColumnLayout {
    id: root

    property var s: ({ lux: null, motion: null, device: {} })
    property bool live: true          // false while the page is hidden: nothing is read then

    spacing: Kirigami.Units.gridUnit
    Layout.fillWidth: true

    // One reader for as long as the page lives: "overdrivectl sensors follow" reads the sensors again and again and answers
    // a line each time (the whole picture first, then the motion each round and the light every fifth). The page used to
    // start a new overdrivectl every 0.4 s: two values a second at best, and on a slow moment (2026-11-15) the readers
    // queued behind the sensor hub by the hundred. A single reader cannot queue, and the bars move as fast as the hub answers.
    // It is paused while the page is hidden and started again if it ever ends.
    readonly property bool watching: live && visible
    function tell(word) { kcm.stream("sensors", ["sensors", "follow"], word) }
    onWatchingChanged: tell(watching ? "go" : "pause")
    Component.onCompleted: tell(watching ? "go" : "pause")
    Timer { id: again; interval: 3000; onTriggered: if (root.watching) root.tell("go") }
    Connections {
        target: kcm
        function onCallFinished(tag, ok, output, error) {
            if (tag !== "sensors") return
            if (!ok) { again.restart(); return }
            try {
                const m = JSON.parse(output)
                root.s = m.device !== undefined ? m : Object.assign({}, root.s, m)
            } catch (e) {}
        }
    }

    component Bar: RowLayout {
        property string label
        property real value: 0
        property real range: 10
        property string text: ""
        Layout.fillWidth: true
        Layout.minimumHeight: Kirigami.Units.gridUnit * 1.9          // roomy rows: the panel is as tall as Plasma's list next to it
        QQC2.Label { text: parent.label; Layout.preferredWidth: Kirigami.Units.gridUnit * 1.5 }
        QQC2.ProgressBar { Layout.fillWidth: true; from: -parent.range; to: parent.range; value: parent.value }
        QQC2.Label { text: parent.text; Layout.preferredWidth: Kirigami.Units.gridUnit * 3.5; horizontalAlignment: Text.AlignRight }
    }

    property bool showFirmware: true  // false once the firmware line sits in the hardware list of the Plasma page

    Section {
        title: i18n("Firmware")
        visible: root.showFirmware && (root.s.device.firmware || "").length > 0
        QQC2.Label { text: (root.s.device.firmware || "") + "   " + (root.s.device.firmware_date || "") }
    }

    Section {
        title: i18n("Light Sensor")
        visible: root.s.lux !== null
        HelpLabel { text: i18n("%1 lux", root.s.lux); font.pointSize: Kirigami.Theme.defaultFont.pointSize * 2.4; help: i18n("Cover the sensor, near the front camera, or point the tablet at a lamp to see it change. Automatic brightness uses this value.") }
    }

    Section {
        title: i18n("Motion")
        visible: root.s.motion !== null
        QQC2.Label { text: i18n("Acceleration (m/s²): about 9.8 on the axis that points down"); opacity: 0.7; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        Repeater {
            model: ["x", "y", "z"]
            delegate: Bar { label: modelData.toUpperCase(); range: 12; value: root.s.motion ? root.s.motion.accel[index] : 0; text: root.s.motion ? root.s.motion.accel[index].toFixed(2) : "" }
        }
        QQC2.Label { text: i18n("Rotation (°/s): turn the tablet and watch the bars"); opacity: 0.7; wrapMode: Text.WordWrap; Layout.fillWidth: true; visible: root.s.motion && root.s.motion.gyro !== undefined }
        Repeater {
            model: root.s.motion && root.s.motion.gyro !== undefined ? ["x", "y", "z"] : []
            delegate: Bar { label: modelData.toUpperCase(); range: 200; value: root.s.motion.gyro[index]; text: root.s.motion.gyro[index].toFixed(1) }
        }
    }

}
