// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// "Power Management": the page of Plasma as it is. How the battery is doing goes in the title bar of the page, next to its name,
// so that it takes no room of its own.
Kirigami.Page {
    id: wrapper

    padding: 0
    property var b: null
    title: b ? kcm.name + "   \u2022   " + line() : kcm.name
    Component.onCompleted: { kcm.loadStock("kcm_powerdevilprofilesconfig"); reload() }
    function reload() { kcm.call("battery", ["sensors"]) }
    Timer { interval: 5000; repeat: true; running: wrapper.visible; onTriggered: wrapper.reload() }
    Connections {
        target: kcm
        function onCallFinished(tag, ok, output, error) {
            if (tag === "battery" && ok) { try { wrapper.b = JSON.parse(output).battery } catch (e) {} }
        }
    }
    function line() {
        const parts = []
        if (b.percent !== null) parts.push(b.percent + "%")
        if (b.status === "Charging") parts.push(i18n("charging"))
        if (b.watts !== undefined && Math.abs(b.watts) >= 0.1) parts.push(Math.abs(b.watts) + " W")
        if (b.hours !== undefined) parts.push(b.status === "Charging" ? i18n("full in %1 h", b.hours) : i18n("%1 h left", b.hours))
        if (b.health !== null) parts.push(i18n("health %1%", b.health))
        if (b.cycles) parts.push(i18n("%1 cycles", b.cycles))
        return parts.join(" \u00b7 ")
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
