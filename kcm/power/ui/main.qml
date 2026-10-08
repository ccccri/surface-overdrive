// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// "Power Management": the page of Plasma as it is, and under it one line with the battery figures (charge, power, time, wear).
Kirigami.Page {
    id: wrapper

    title: kcm.name
    padding: 0
    // A page that the Plasma page opens on top of itself (its "Configure..." entries) takes the whole view with a way back, as it
    // does in Plasma, instead of squeezing in as a second column: System Settings decides that from this property of the first page.
    Kirigami.ColumnView.fillWidth: true
    actions: kcm.stockPage ? kcm.stockPage.actions : []
    property var b: null
    Component.onCompleted: { kcm.loadStock("kcm_powerdevilprofilesconfig"); reload() }
    function reload() { kcm.call("battery", ["sensors"]) }
    Timer { interval: 5000; repeat: true; running: wrapper.visible; onTriggered: wrapper.reload() }
    Connections {
        target: kcm
        function onCallFinished(tag, ok, output, error) {
            if (tag === "battery" && ok) { try { wrapper.b = JSON.parse(output).battery } catch (e) {} }
        }
    }
    // One compact technical line: charge and flow now, then what the battery still holds.
    function hours(h) { return h >= 1 ? i18n("%1 h", h) : i18n("%1 min", Math.round(h * 60)) }
    function now() {
        const parts = [i18n("%1%", b.percent)]
        const watts = b.watts !== undefined && b.watts !== null && Math.abs(b.watts) >= 0.1 ? Math.abs(b.watts) : 0
        if (b.status === "Charging") parts.push(watts ? i18n("charging %1 W", watts) : i18n("charging"))
        else if (b.status === "Discharging") { if (watts) parts.push(i18n("discharging %1 W", watts)) }
        else if (b.status === "Full") parts.push(i18n("full"))
        else if (b.status) parts.push(String(b.status).toLowerCase())
        if (b.hours !== undefined && b.hours !== null) parts.push(b.status === "Charging" ? i18n("%1 to full", hours(b.hours)) : i18n("%1 left", hours(b.hours)))
        return parts.join("  ·  ")
    }
    function wear() {
        if (b.health === undefined || b.health === null) return ""
        const parts = [i18n("Health %1%", b.health)]
        if (b.full_mah && b.design_mah) parts.push(i18n("%1 / %2 mAh", b.full_mah, b.design_mah))
        if (b.cycles !== undefined && b.cycles !== null) parts.push(i18n("%1 cycles", b.cycles))
        return parts.join("  ·  ")
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Item {
            id: holder
            Layout.fillWidth: true
            Layout.fillHeight: true
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
        Kirigami.Separator { Layout.fillWidth: true; visible: batteryLine.visible }
        RowLayout {
            id: batteryLine
            visible: wrapper.b !== null && wrapper.b.percent !== undefined
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.largeSpacing
            Kirigami.Icon { source: "battery-symbolic"; implicitWidth: Kirigami.Units.iconSizes.small; implicitHeight: implicitWidth; opacity: 0.7 }
            QQC2.Label { text: batteryLine.visible ? wrapper.now() : ""; elide: Text.ElideRight; Layout.fillWidth: true }
            QQC2.Label { text: batteryLine.visible ? wrapper.wear() : ""; opacity: 0.7; visible: wrapper.width > Kirigami.Units.gridUnit * 34 }
        }
    }
}
