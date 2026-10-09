// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// "Drawing Tablet": the page of Plasma with our pen test next to its Pen tab (on a window wide enough for both; a narrow window
// shows the settings of Plasma alone). The tabs of Plasma (Display, Pen, Pad) are shown by
// our own row of buttons, which presses the hidden ones of Plasma: that is how "Pad" is left out (the Surface has none) and how we
// know when the Pen tab is in front. If a future Plasma builds its page differently, the row falls back to two buttons: its page,
// and the pen test alone.
Kirigami.Page {
    id: wrapper

    title: kcm.name
    padding: 0
    // A page that the Plasma page opens on top of itself (its "Configure..." entries) takes the whole view with a way back, as it
    // does in Plasma, instead of squeezing in as a second column: System Settings decides that from this property of the first page.
    Kirigami.ColumnView.fillWidth: true
    property Item bar: null                // the tab bar of Plasma, once found
    property var tabs: []                  // [{ text, icon, index }] of the Plasma tabs we show
    property int stockTab: 0
    property bool test: false              // fallback only: the pen test alone, when the tabs of Plasma could not be taken over
    readonly property bool penTab: tabs.length > 0 && tabs.some(t => t.index === stockTab && /pen/i.test(t.text))
    readonly property bool wide: width > Kirigami.Units.gridUnit * 50
    actions: kcm.stockPage ? kcm.stockPage.actions : []
    // The page of Plasma is loaded half a second after ours shows, not at once. It opens its own connection to the pen
    // (the Wayland tablet protocol) when it is made and closes it when it goes; made and gone again within a few milliseconds,
    // as when one runs through the sidebar, the answers of the compositor arrive for a connection that is already closed and the
    // whole of System Settings dies with a Wayland protocol error ("not a valid new object id ... tablet_added").
    Timer { interval: 500; running: true; onTriggered: kcm.loadStock("kcm_tablet") }
    Bars { target: wrapper }

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
            // out of sight, but still laid out: hidden for real, the tab bar of Plasma loses track of its own buttons
            found.Layout.maximumHeight = 0
            found.Layout.preferredHeight = 0
            found.clip = true
            found.opacity = 0
            bar = found
            tabs = list
            const pen = list.find(t => /pen/i.test(t.text))
            stockTab = list[0].index
            if (kcm.startTab === "pen" && pen) { first.index = pen.index; first.start() }      // once the tabs of Plasma are all there
        } catch (e) {
            console.warn("Surface Control: could not take over the tabs of the Drawing Tablet page:", e)
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
        test = false
        stockTab = index
        // press the hidden tab of Plasma: through its action, as a click would, and by its number
        let how = ""
        try { const button = stockButton(bar, bar.actions[index].text, 0); if (button) { button.checked = true; if (button.action) button.action.trigger(); how += "button " } } catch (e) { how += "(button: " + e + ") " }
        try { bar.actions[index].checked = true; bar.actions[index].trigger(); how += "action " } catch (e) { how += "(action: " + e + ") " }
        try { bar.currentIndex = index; how += "index " } catch (e) { how += "(index: " + e + ") " }
        if (how.indexOf("(") >= 0) console.warn("Surface Control: switching the tab of the Drawing Tablet page:", how)
    }
    // the page of Plasma builds its tabs a moment after it loads, and only when it has found the pen
    Timer { interval: 400; repeat: true; running: kcm.stockPage !== null && wrapper.bar === null && triggeredCount < 15; property int triggeredCount: 0; onTriggered: { triggeredCount++; wrapper.adopt() } }

    // The Pen tab of Plasma shows a tall drawing of a pen (not the Surface Pen) with lines to the button settings; it only takes
    // room. The drawing and its lines are the tall vector shapes of the tab (the pressure curve is made of shapes too, and stays).
    function hidePicture(item, depth) {
        if (!item || depth > 9) return
        const type = String(item)
        if (type.indexOf("PressureCurve") >= 0) return
        if (type.indexOf("QQuickShape") >= 0 && item.height >= Kirigami.Units.gridUnit * 12) {
            item.visible = false
            // the drawing sits alone in a spacer that keeps its room
            if (item.parent && item.parent.children.length === 1 && String(item.parent).indexOf("QQuickItem") === 0) item.parent.visible = false
            return
        }
        for (let i = 0; item.children && i < item.children.length; i++) hidePicture(item.children[i], depth + 1)
    }
    // A setting the pen of this tablet cannot have is left out: Plasma shows it greyed out ("Left-handed mode", which is for
    // tablets that lie on the desk and can be turned around). That is a labelled line of the form whose check box is disabled.
    function firstCheck(item, depth) {
        if (!item || depth > 4) return null
        if (item.checkable !== undefined && item.checked !== undefined) return item
        for (let i = 0; item.children && i < item.children.length; i++) {
            const found = firstCheck(item.children[i], depth + 1)
            if (found) return found
        }
        return null
    }
    function hideUnsupported(item, depth) {
        if (!item || depth > 9) return
        if (item.Kirigami.FormData.label.length > 0) {
            // only an on/off setting counts (a slider that is greyed out until the pen wakes up stays), and it comes back by
            // itself should the tablet ever support it
            const check = firstCheck(item, 0)
            if (check && String(check).indexOf("CheckBox") >= 0) item.visible = Qt.binding(() => check.enabled)
            return
        }
        for (let i = 0; item.children && i < item.children.length; i++) hideUnsupported(item.children[i], depth + 1)
    }
    // The pressure curve of Plasma is a large square; a lower one lets the whole tab fit the screen of the tablet without scrolling.
    function shrinkCurve(item, depth) {
        if (!item || depth > 12) return
        if (String(item).indexOf("PressureCurve") >= 0) {
            const side = Kirigami.Units.gridUnit * 9
            if (item.implicitHeight > side) { item.implicitHeight = side; item.Layout.maximumHeight = side }
            return
        }
        for (let i = 0; item.children && i < item.children.length; i++) shrinkCurve(item.children[i], depth + 1)
    }
    Timer { id: first; property int index: 0; interval: 500; onTriggered: wrapper.choose(index) }
    Timer {
        id: tidy; interval: 400
        onTriggered: {
            if (!wrapper.penTab) return
            try { wrapper.hidePicture(kcm.stockPage.flickable.contentItem, 0) } catch (e) {}
            try { wrapper.shrinkCurve(kcm.stockPage.flickable.contentItem, 0) } catch (e) {}
            try {
                const f = kcm.stockPage.flickable
                f.boundsBehavior = Flickable.StopAtBounds
                f.interactive = Qt.binding(() => f.contentHeight > f.height + 1)
            } catch (e) {}
            try { wrapper.hideUnsupported(kcm.stockPage.flickable.contentItem, 0) } catch (e) { console.warn("Surface Control: could not tidy the Pen tab:", e) }
        }
    }
    onPenTabChanged: tidy.restart()

    // Our own slim row of tabs; a click presses the hidden tab of the Plasma page.
    readonly property var shownTabs: tabs.length > 0 ? tabs : [{ text: i18n("Settings"), icon: "preferences-desktop-tablet", index: -1 }, { text: i18n("Pen Test"), icon: "draw-freehand", index: -2 }]
    header: QQC2.Control {
        padding: Kirigami.Units.largeSpacing
        bottomPadding: 0
        contentItem: Tabs {
            model: wrapper.shownTabs
            current: Math.max(0, wrapper.shownTabs.findIndex(t => t.index === -2 ? wrapper.test : t.index === -1 ? !wrapper.test : (!wrapper.test && wrapper.stockTab === t.index)))
            onChosen: i => {
                const index = wrapper.shownTabs[i].index
                if (index === -2) wrapper.test = true; else if (index === -1) wrapper.test = false; else wrapper.choose(index)
            }
        }
    }

    // Display tab: the page of Plasma alone. Pen tab: its settings and our test side by side when the window has room for both,
    // else the settings alone (the test needs its width, and one part above the other would mean scrolling to reach it).
    RowLayout {
        anchors.fill: parent
        spacing: 0

        Item {
            id: holder
            visible: !wrapper.test
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: Kirigami.Units.gridUnit * 28
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
        Kirigami.Separator { Layout.fillHeight: true; Layout.topMargin: Kirigami.Units.largeSpacing; Layout.bottomMargin: Kirigami.Units.largeSpacing; visible: penTest.visible && holder.visible }
        PenTest {
            id: penTest
            visible: wrapper.test || (wrapper.penTab && wrapper.wide)
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: Kirigami.Units.gridUnit * 28
        }
    }
}
