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
    Bars { target: wrapper }

    // The three power states (On AC Power, On Battery, On Low Battery) are a bar of tabs in the Plasma page. They show as our slim
    // row of buttons instead, as in Cameras and Drawing Tablet: the bar of Plasma is put out of sight and our buttons press its
    // tabs. If a future Plasma builds the page differently, its own bar simply stays.
    property Item bar: null
    property var tabs: []                  // [{ text, icon }] in the order of the Plasma tabs
    property int current: 0
    function findBar(item, depth) {
        if (!item || depth > 8) return null
        if (item.currentIndex !== undefined && item.count !== undefined && item.actions !== undefined) return item
        for (let i = 0; item.children && i < item.children.length; i++) {
            const found = findBar(item.children[i], depth + 1)
            if (found) return found
        }
        return null
    }
    function adopt() {
        const page = kcm.stockPage
        if (!page || bar) return
        try {
            const found = findBar(page.header, 0) || findBar(page, 0)
            if (!found || !found.actions || found.actions.length < 2) return
            const list = []
            for (let i = 0; i < found.actions.length; i++) list.push({ text: found.actions[i].text, icon: found.actions[i].icon.name })
            // out of sight, but still laid out: hidden for real, the tab bar of Plasma loses track of its own buttons
            found.height = 0
            found.implicitHeight = 0
            found.Layout.maximumHeight = 0
            found.Layout.preferredHeight = 0
            found.clip = true
            found.opacity = 0
            found.enabled = false
            current = Math.max(0, found.currentIndex)
            bar = found
            tabs = list
        } catch (e) {
            console.warn("Surface Control: could not take over the tabs of the Power Management page:", e)
        }
    }
    function stockButton(item, text, depth) {
        if (!item || depth > 4) return null
        if (item.text === text && item.checkable !== undefined) return item
        for (let i = 0; item.children && i < item.children.length; i++) {
            const found = stockButton(item.children[i], text, depth + 1)
            if (found) return found
        }
        return null
    }
    function choose(index) {
        current = index
        try { const button = stockButton(bar, bar.actions[index].text, 0); if (button) { button.checked = true; if (button.action) button.action.trigger() } } catch (e) {}
        try { bar.actions[index].checked = true; bar.actions[index].trigger() } catch (e) {}
        try { bar.currentIndex = index } catch (e) {}
    }
    Timer { interval: 400; repeat: true; running: kcm.stockPage !== null && wrapper.bar === null && tries < 15; property int tries: 0; onTriggered: { tries++; wrapper.adopt() } }
    header: QQC2.Control {
        visible: wrapper.tabs.length > 0
        padding: Kirigami.Units.largeSpacing
        bottomPadding: 0
        contentItem: Tabs {
            model: wrapper.tabs
            current: wrapper.current
            onChosen: index => wrapper.choose(index)
        }
    }
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
