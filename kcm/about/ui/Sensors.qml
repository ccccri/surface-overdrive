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

    spacing: Kirigami.Units.largeSpacing
    Layout.fillWidth: true

    // One reading at a time. Each one asks the sensor hub seven values and takes 0.4 s or more; the timer used to start
    // the next without waiting, and on a slow moment (2026-11-15, after a resume, the tablet busy) they piled up behind
    // the hub: 627 readers, the memory full, nothing shown. A reading that never answers is given up after 10 s.
    property bool reading: false
    function reload() {
        if (reading) return
        reading = true
        giveUp.restart()
        kcm.call("sensors", ["sensors"])
    }
    Timer { id: giveUp; interval: 10000; onTriggered: root.reading = false }
    // the motion sensors report 10 times a second by default: 50 while somebody is watching the bars
    Component.onCompleted: { kcm.call("rate", ["sensors", "rate", "50"]); reload() }
    Component.onDestruction: kcm.call("rate", ["sensors", "rate", "10"])
    Timer { interval: 400; repeat: true; running: root.live && root.visible; onTriggered: root.reload() }
    Connections {
        target: kcm
        function onCallFinished(tag, ok, output, error) {
            if (tag !== "sensors") return
            root.reading = false
            giveUp.stop()
            if (ok) { try { root.s = JSON.parse(output) } catch (e) {} }
        }
    }

    component Bar: RowLayout {
        property string label
        property real value: 0
        property real range: 10
        property string text: ""
        Layout.fillWidth: true
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
        HelpLabel { text: i18n("%1 lux", root.s.lux); font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.6; help: i18n("Cover the sensor, near the front camera, or point the tablet at a lamp to see it change. Automatic brightness uses this value.") }
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
