// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// "About this System": the page of Plasma, with the firmware version added to its hardware list and the light and motion sensors
// next to it.
StockWithSide {
    id: page
    stock: "kcm_about-distro"

    // The Plasma page is a form that puts each label next to its value only when it is wide enough (about 32 grid units, Kirigami
    // 6.31): narrower, every label goes above its value and the page gets twice as long and scrolls. The sensors do with less, so
    // that on the tablet (1242 points wide at the 145% scale a fresh install picks) the whole page shows at once, nothing to scroll.
    sideWidth: Kirigami.Units.gridUnit * 19
    sideCentered: true

    // The lists of the Plasma page are form groups made of entries (Kirigami.FormEntry since Plasma 6.8, a FormLayout before): one
    // more entry after the last one of the hardware list shows the firmware. If that does not work on a future Plasma, the firmware
    // stays in a box with the sensors.
    function forms(item, depth, found) {
        if (!item || depth > 10) return found
        if (String(item).indexOf("FormLayout") >= 0) found.push(item)
        for (let i = 0; item.children && i < item.children.length; i++) forms(item.children[i], depth + 1, found)
        return found
    }
    function entries(item, depth, found) {
        if (!item || depth > 30) return found
        if (item.contentItem !== undefined && item.subtitle !== undefined && item.leadingItems !== undefined && item.trailingItems !== undefined) {
            found.push(item)
            return found
        }
        for (let i = 0; item.children && i < item.children.length; i++) entries(item.children[i], depth + 1, found)
        return found
    }
    property bool firmwareAdded: false
    property int seenEntries: -1
    function addFirmware() {
        if (firmwareAdded || !kcm.stockPage) return
        try {
            const content = kcm.stockPage.flickable.contentItem
            const found = forms(content, 0, [])
            if (found.length > 0) {
                firmwareLine.createObject(found[found.length - 1])
            } else {
                // Plasma adds lines for a moment after the page opens (the machine's names come from a helper): ours goes in
                // once their number has stopped changing, so that it is the last one
                const list = entries(content, 0, [])
                if (list.length === 0 || list.length !== seenEntries) { seenEntries = list.length; return }
                const last = list[list.length - 1]
                const entry = Qt.createQmlObject('import QtQuick.Controls as QQC2\nimport org.kde.kirigami as Kirigami\n'
                    + 'Kirigami.FormEntry { id: e; property string value; visible: value.length > 0; contentItem: QQC2.Label { text: e.value } }', last.parent)
                entry.title = i18n("Firmware Version:")
                entry.value = Qt.binding(() => sensors.s.device.firmware ? sensors.s.device.firmware + " (" + (sensors.s.device.firmware_date || "") + ")" : "")
            }
            firmwareAdded = true
            sensors.showFirmware = false
        } catch (e) {
            firmwareAdded = true                              // once: the box with the sensors keeps it
            console.warn("Surface Control: could not add the firmware to the hardware list:", e)
        }
    }
    // Nothing to drag when everything shows: the page stays still, in the middle of the height.
    function still() {
        try {
            const f = kcm.stockPage.flickable
            f.boundsBehavior = Flickable.StopAtBounds
            f.interactive = Qt.binding(() => f.contentHeight > f.height + 1)
            // and what is left of the height goes half above, half below: the list and the sensors sit in the middle of the page
            // instead of leaving the bottom third empty
            // (the Plasma page is moved down inside its place: a margin on its own scrolling area made a binding loop)
            const stock = kcm.stockPage
            stock.anchors.topMargin = Qt.binding(() => Math.max(0, Math.round((stock.parent.height - f.contentHeight) / 2)))
        } catch (e) {}
    }
    // Hidden entries of the Plasma page (the serial number) come with a "Show" button that opens a dialog, placed off centre inside
    // our page. Each of them gets instead two small buttons on its own line: show or hide the value in place, and copy it. Every
    // line of the page has that button (the only one with a "dialog" property), visible only while its entry is hidden: it is kept,
    // out of sight, as the sign of whether the line is a hidden one. Lines can come later ("show more"), so the page is looked at
    // again every second while it is open.
    property var reworked: []
    function showButtons(item, depth, found) {
        if (!item || depth > 40) return found         // Plasma 6.8 nests the button 20 items deep (14 was enough before)
        if (("dialog" in item) && ("clicked" in item) && item.parent) found.push(item)
        for (let i = 0; item.children && i < item.children.length; i++) showButtons(item.children[i], depth + 1, found)
        return found
    }
    function reworkHidden() {
        if (!kcm.stockPage) return
        for (const button of showButtons(kcm.stockPage.flickable.contentItem, 0, [])) {
            if (reworked.indexOf(button) >= 0) continue
            const row = button.parent
            let label = null
            for (let i = 0; i < row.children.length; i++)
                if (row.children[i] !== button && ("selectedText" in row.children[i])) label = row.children[i]
            if (!label) continue
            reworked.push(button)
            button.opacity = 0
            button.enabled = false
            button.Layout.maximumWidth = 0
            hiddenControls.createObject(row, { label: label, sign: button })
        }
    }
    Timer { interval: 1000; repeat: true; running: page.visible; triggeredOnStart: true; onTriggered: { page.reworkHidden(); page.addFirmware() } }
    onLoaded: stockPage => { page.still(); page.addFirmware() }

    Sensors { id: sensors; live: page.visible }
    Component {
        id: hiddenControls
        RowLayout {
            id: controls
            property Item label
            property Item sign                              // the "Show" button of Plasma: visible while the entry is hidden
            property bool shown: false
            visible: sign && sign.visible
            spacing: 0
            // The value stays in the label of the Plasma page: shown in place, or a row of dots of the same length.
            QQC2.Label {
                visible: !controls.shown
                text: "\u2022".repeat(Math.min(Math.max(controls.label ? controls.label.text.length : 8, 6), 16))
            }
            Component.onCompleted: label.visible = Qt.binding(() => !controls.sign.visible || controls.shown)
            QQC2.ToolButton {
                icon.name: controls.shown ? "view-hidden" : "view-visible"
                display: QQC2.AbstractButton.IconOnly
                text: controls.shown ? i18n("Hide") : i18n("Show")
                QQC2.ToolTip.text: text
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                onClicked: controls.shown = !controls.shown
            }
            QQC2.ToolButton {
                icon.name: "edit-copy"
                display: QQC2.AbstractButton.IconOnly
                text: i18n("Copy")
                QQC2.ToolTip.text: copied.running ? i18n("Copied") : text
                QQC2.ToolTip.visible: hovered || copied.running
                QQC2.ToolTip.delay: copied.running ? 0 : Kirigami.Units.toolTipDelay
                onClicked: {
                    clip.text = controls.label.text
                    clip.selectAll()
                    clip.copy()
                    clip.text = ""
                    copied.restart()
                }
                Timer { id: copied; interval: 1500 }
            }
            // A text field that is never shown, used only to put the value on the clipboard.
            TextEdit { id: clip; visible: false }
        }
    }
    Component {
        id: firmwareLine
        QQC2.Label {
            Kirigami.FormData.label: i18n("Firmware Version:")
            visible: text.length > 0
            text: sensors.s.device.firmware ? sensors.s.device.firmware + " (" + (sensors.s.device.firmware_date || "") + ")" : ""
        }
    }
}
