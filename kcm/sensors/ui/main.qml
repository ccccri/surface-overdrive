// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kcmutils as KCM
import org.kde.kirigami as Kirigami

KCM.SimpleKCM {
    id: root

    property var s: ({ battery: null, lux: null, motion: null, device: {} })

    function reload() { kcm.call("sensors", ["sensors"]) }
    Component.onCompleted: { kcm.call("rate", ["sensors", "rate", "50"]); reload() }
    Component.onDestruction: kcm.call("rate", ["sensors", "rate", "10"])
    Timer { interval: 400; repeat: true; running: root.visible; onTriggered: root.reload() }
    Connections {
        target: kcm
        function onCallFinished(tag, ok, output, error) {
            if (tag === "sensors" && ok) { try { root.s = JSON.parse(output) } catch (e) {} }
        }
    }

    component Section: Kirigami.AbstractCard {
        id: sec
        property string title
        default property alias content: body.data
        Layout.fillWidth: true
        header: Kirigami.Heading { level: 4; text: sec.title; padding: Kirigami.Units.smallSpacing }
        contentItem: ColumnLayout { id: body; spacing: Kirigami.Units.smallSpacing }
    }
    component Bar: RowLayout {
        property string label
        property real value: 0
        property real range: 10
        property string text: ""
        Layout.fillWidth: true
        QQC2.Label { text: parent.label; Layout.preferredWidth: Kirigami.Units.gridUnit * 3 }
        QQC2.ProgressBar { Layout.fillWidth: true; from: -parent.range; to: parent.range; value: parent.value }
        QQC2.Label { text: parent.text; Layout.preferredWidth: Kirigami.Units.gridUnit * 6; horizontalAlignment: Text.AlignRight }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        Section {
            title: i18n("Battery")
            visible: root.s.battery !== null
            QQC2.ProgressBar {
                Layout.fillWidth: true; from: 0; to: 100
                value: root.s.battery && root.s.battery.percent !== null ? root.s.battery.percent : 0
            }
            Kirigami.FormLayout {
                Layout.fillWidth: true
                QQC2.Label { Kirigami.FormData.label: i18n("Charge:"); text: root.s.battery ? root.s.battery.percent + "%  (" + root.s.battery.status + ")" : "" }
                QQC2.Label { Kirigami.FormData.label: i18n("Power:"); visible: root.s.battery && root.s.battery.watts !== undefined; text: root.s.battery && root.s.battery.watts !== undefined ? Math.abs(root.s.battery.watts) + " W" : "" }
                QQC2.Label {
                    Kirigami.FormData.label: root.s.battery && root.s.battery.status === "Charging" ? i18n("Time to full:") : i18n("Time left:")
                    visible: root.s.battery && root.s.battery.hours !== undefined
                    text: root.s.battery && root.s.battery.hours !== undefined ? i18n("about %1 h", root.s.battery.hours) : ""
                }
                QQC2.Label { Kirigami.FormData.label: i18n("Health:"); visible: root.s.battery && root.s.battery.health !== null; text: root.s.battery ? root.s.battery.health + "% of the original capacity (" + root.s.battery.full_mah + " of " + root.s.battery.design_mah + " mAh)" : "" }
                QQC2.Label { Kirigami.FormData.label: i18n("Charge cycles:"); text: root.s.battery ? root.s.battery.cycles : "" }
                QQC2.Label { Kirigami.FormData.label: i18n("Cell:"); text: root.s.battery ? (root.s.battery.maker + " " + root.s.battery.model).trim() : "" }
            }
        }

        Section {
            title: i18n("Light sensor")
            visible: root.s.lux !== null
            QQC2.Label { text: i18n("%1 lux", root.s.lux); font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.6 }
            QQC2.Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; opacity: 0.6; text: i18n("Cover the sensor, near the front camera, or point the tablet at a lamp to see it change. Automatic brightness uses this value.") }
        }

        Section {
            title: i18n("Motion")
            visible: root.s.motion !== null
            QQC2.Label { text: i18n("Acceleration (m/s²): about 9.8 on the axis that points down"); opacity: 0.7 }
            Repeater {
                model: ["x", "y", "z"]
                delegate: Bar { label: modelData.toUpperCase(); range: 12; value: root.s.motion ? root.s.motion.accel[index] : 0; text: root.s.motion ? root.s.motion.accel[index].toFixed(2) : "" }
            }
            QQC2.Label { text: i18n("Rotation (°/s): turn the tablet and watch the bars"); opacity: 0.7; visible: root.s.motion && root.s.motion.gyro !== undefined }
            Repeater {
                model: root.s.motion && root.s.motion.gyro !== undefined ? ["x", "y", "z"] : []
                delegate: Bar { label: modelData.toUpperCase(); range: 200; value: root.s.motion.gyro[index]; text: root.s.motion.gyro[index].toFixed(1) }
            }
        }

        Section {
            title: i18n("This tablet")
            Kirigami.FormLayout {
                Layout.fillWidth: true
                QQC2.Label { Kirigami.FormData.label: i18n("Model:"); text: root.s.device.model || "" }
                QQC2.Label { Kirigami.FormData.label: i18n("Firmware:"); text: (root.s.device.firmware || "") + "  " + (root.s.device.firmware_date || "") }
                QQC2.Label { Kirigami.FormData.label: i18n("Processor:"); text: root.s.device.cpu || "" }
                QQC2.Label { Kirigami.FormData.label: i18n("Memory:"); text: root.s.device.memory_gb ? root.s.device.memory_gb + " GB" : "" }
                QQC2.Label { Kirigami.FormData.label: i18n("Kernel:"); text: root.s.device.kernel || "" }
            }
        }
    }
}
