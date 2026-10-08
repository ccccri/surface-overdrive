// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// "Power Management": the page of Plasma as it is, and under it one quiet line that tells how the battery is doing, in full words.
Kirigami.Page {
    id: wrapper

    title: kcm.name
    padding: 0
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
    function now() {
        let text = i18n("Battery at %1%", b.percent)
        const watts = b.watts !== undefined && Math.abs(b.watts) >= 0.1 ? Math.abs(b.watts) : 0
        if (b.status === "Charging") text += watts ? i18n(", charging at %1 W", watts) : i18n(", charging")
        else if (b.status === "Discharging") text += watts ? i18n(", using %1 W", watts) : ""
        else if (b.status === "Full") text += i18n(", full")
        if (b.hours !== undefined) text += b.status === "Charging" ? i18n(", full in about %1 hours", b.hours) : i18n(", about %1 hours left", b.hours)
        return text
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
        RowLayout {
            visible: wrapper.b !== null
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.largeSpacing
            Kirigami.Icon { source: "battery-good"; implicitWidth: Kirigami.Units.iconSizes.smallMedium; implicitHeight: implicitWidth; opacity: 0.8 }
            QQC2.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                opacity: 0.8
                text: wrapper.b ? wrapper.now() + (wrapper.b.health !== null
                        ? "\n" + i18n("Battery health: it holds %1% of what it held when new (%2 of %3 mAh), after %4 charge cycles.", wrapper.b.health, wrapper.b.full_mah, wrapper.b.design_mah, wrapper.b.cycles) : "") : ""
            }
        }
    }
}
