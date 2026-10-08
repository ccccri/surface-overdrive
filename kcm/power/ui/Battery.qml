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
    Component.onCompleted: reload()
    onVisibleChanged: if (visible) reload()
    Timer { interval: 2000; repeat: true; running: root.visible; onTriggered: root.reload() }
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
    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: root.s.battery === null
            type: Kirigami.MessageType.Information
            text: i18n("No battery found.")
        }
        Section {
            visible: root.s.battery !== null
            title: i18n("Battery")
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

    }
}
