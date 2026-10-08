// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// "Drawing Tablet": the page of Plasma with one more tab, the pen test. The tabs of Plasma (Display, Pen, Pad) are shown by our own
// row of buttons, which presses the hidden ones of Plasma: that is how the test sits next to them and how "Pad" is left out (the
// Surface has none). If a future Plasma builds its page differently, the row falls back to two buttons: its page, and the test.
Kirigami.Page {
    id: wrapper

    title: kcm.name
    padding: 0
    property Item bar: null                // the tab bar of Plasma, once found
    property var tabs: []                  // [{ text, icon, index }] of the Plasma tabs we show
    property int stockTab: 0
    property bool test: kcm.startTab === "test"
    onTestChanged: kcm.showStockButtons(!test)
    Component.onCompleted: { kcm.showStockButtons(!test); kcm.loadStock("kcm_tablet") }

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
            const found = findBar(page.flickable ? page.flickable.contentItem : page.contentItem, 0)
            if (!found || !found.actions || found.actions.length === 0) return
            const list = []
            for (let i = 0; i < found.actions.length; i++) {
                const a = found.actions[i]
                if (/pad/i.test(a.text)) continue
                list.push({ text: a.text, icon: a.icon.name, index: i })
            }
            if (list.length === 0) return
            found.visible = false
            bar = found
            tabs = list
            stockTab = list[0].index
        } catch (e) {
            console.warn("Surface Control: could not take over the tabs of the Drawing Tablet page:", e)
        }
    }
    function choose(index) {
        test = false
        stockTab = index
        try { bar.actions[index].trigger() } catch (e) {}
        try { bar.currentIndex = index } catch (e) {}
    }
    // the page of Plasma builds its tabs a moment after it loads, and only when it has found the pen
    Timer { interval: 400; repeat: true; running: kcm.stockPage !== null && wrapper.bar === null && triggeredCount < 15; property int triggeredCount: 0; onTriggered: { triggeredCount++; wrapper.adopt() } }

    header: QQC2.Control {
        padding: Kirigami.Units.largeSpacing
        bottomPadding: Kirigami.Units.smallSpacing
        contentItem: RowLayout {
            spacing: Kirigami.Units.smallSpacing
            Repeater {
                model: wrapper.tabs.length > 0 ? wrapper.tabs : [{ text: i18n("Settings"), icon: "preferences-desktop-tablet", index: -1 }]
                delegate: QQC2.Button {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    text: modelData.text
                    icon.name: modelData.icon
                    checkable: true
                    autoExclusive: true
                    checked: !wrapper.test && (modelData.index < 0 || wrapper.stockTab === modelData.index)
                    highlighted: checked
                    onClicked: modelData.index < 0 ? wrapper.test = false : wrapper.choose(modelData.index)
                }
            }
            QQC2.Button {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                text: i18n("Pen test")
                icon.name: "draw-freehand"
                checkable: true
                autoExclusive: true
                checked: wrapper.test
                highlighted: checked
                onClicked: wrapper.test = true
            }
        }
    }

    Item {
        anchors.fill: parent
        Item {
            id: holder
            anchors.fill: parent
            visible: !wrapper.test
            readonly property Item page: kcm.stockPage
            onPageChanged: if (page) { page.parent = holder; page.anchors.fill = holder; page.visible = true; wrapper.adopt() }
            Kirigami.PlaceholderMessage {
                anchors.centerIn: parent
                width: parent.width - Kirigami.Units.gridUnit * 4
                visible: kcm.stockError.length > 0
                icon.name: "dialog-warning"
                text: i18n("This page could not be loaded")
                explanation: kcm.stockError
            }
        }
        PenTest { anchors.fill: parent; visible: wrapper.test }
    }
}
