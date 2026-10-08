// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// "Power Management": the page of Plasma, with one line above it that tells how the battery is doing.
Kirigami.Page {
    id: wrapper

    title: kcm.name
    padding: 0
    property var b: null
    Component.onCompleted: { kcm.loadStock("kcm_powerdevilprofilesconfig"); reload() }
    function reload() { kcm.call("battery", ["sensors"]) }
    Timer { interval: 3000; repeat: true; running: wrapper.visible; onTriggered: wrapper.reload() }
    Connections {
        target: kcm
        function onCallFinished(tag, ok, output, error) {
            if (tag === "battery" && ok) { try { wrapper.b = JSON.parse(output).battery } catch (e) {} }
        }
    }
    function line() {
        if (!b) return ""
        const parts = []
        if (b.percent !== null) parts.push(b.percent + "%")
        if (b.status === "Charging") parts.push(i18n("charging"))
        else if (b.status === "Discharging") parts.push(i18n("on battery"))
        else if (b.status) parts.push(b.status.toLowerCase())
        if (b.watts !== undefined && Math.abs(b.watts) >= 0.1) parts.push(Math.abs(b.watts) + " W")
        if (b.hours !== undefined) parts.push(b.status === "Charging" ? i18n("full in about %1 h", b.hours) : i18n("about %1 h left", b.hours))
        return parts.join("  ·  ")
    }

    header: QQC2.Control {
        visible: wrapper.b !== null
        padding: Kirigami.Units.largeSpacing
        contentItem: RowLayout {
            spacing: Kirigami.Units.largeSpacing
            Kirigami.Icon { source: "battery"; implicitWidth: Kirigami.Units.iconSizes.medium; implicitHeight: implicitWidth }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                QQC2.Label { Layout.fillWidth: true; elide: Text.ElideRight; font.bold: true; text: wrapper.line() }
                QQC2.Label {
                    Layout.fillWidth: true; elide: Text.ElideRight; opacity: 0.7
                    visible: wrapper.b && wrapper.b.health !== null
                    text: wrapper.b ? i18n("Battery health %1% (%2 of %3 mAh), %4 charge cycles", wrapper.b.health, wrapper.b.full_mah, wrapper.b.design_mah, wrapper.b.cycles) : ""
                }
            }
        }
        background: Rectangle {
            color: Kirigami.Theme.backgroundColor
            Kirigami.Separator { anchors { left: parent.left; right: parent.right; bottom: parent.bottom } }
        }
    }

    Item {
        id: holder
        anchors.fill: parent
        readonly property Item page: kcm.stockPage
        onPageChanged: if (page) { page.parent = holder; page.anchors.fill = holder; page.visible = true }
        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            width: parent.width - Kirigami.Units.gridUnit * 4
            visible: kcm.stockError.length > 0
            icon.name: "dialog-warning"
            text: i18n("This page could not be loaded")
            explanation: kcm.stockError
        }
    }
}
