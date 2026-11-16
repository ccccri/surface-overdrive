// SPDX-License-Identifier: MIT
// The floating on-screen keyboard (prototype). One transparent window over the whole screen; the keyboard is `panel`,
// moved inside it. Only the rectangles given to backend.setTouchRects take touches, the rest goes to what is under.
import QtQuick
import QtQuick.Window
import org.kde.layershell as LayerShell

Window {
    id: win
    visible: true
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus
    width: Screen.width
    height: Screen.height
    LayerShell.Window.scope: "overdrive-osk"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorTop | LayerShell.Window.AnchorBottom | LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorRight
    LayerShell.Window.exclusionZone: -1
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone

    // ---- settings (kept by the backend) ----
    property var s: JSON.parse(backend.settingsJson)
    property bool shown: s.visible
    readonly property bool floating: s.floating
    readonly property real u: Math.round(Math.min(width / 23, 54) * s.scale)        // the size of a key
    readonly property real gap: Math.max(3, Math.round(u * 0.09))

    // ---- state ----
    property string page: "letters"            // letters | symbols | emoji
    property int shift: 0                      // 0 off, 1 the next letter, 2 locked
    property var latched: []                   // "ctrl", "alt", "meta" waiting for the next key
    property bool clipsOpen: false
    property var alt: null                     // the open long-press popup: { key, list, index, x, y }
    function toggleLatch(name) {
        const l = latched.slice(); const i = l.indexOf(name)
        if (i >= 0) l.splice(i, 1); else l.push(name)
        latched = l
    }

    Connections {
        target: backend
        function onCommand(word) { backend.setSetting("visible", word === "show" ? true : word === "hide" ? false : !win.shown) }
        function onShiftWanted() { if (win.shift === 0) win.shift = 1 }
    }

    // ---- what the keys are ----
    readonly property var alternates: ({
        "a": "àáâäæ", "e": "èéêë€", "i": "ìíîï", "o": "òóôöœ", "u": "ùúûü", "c": "ç", "n": "ñ", "s": "ß$", "y": "ÿ",
        ".": ",?!:;…", ",": ";:'\"", "?": "¿!", "!": "¡", "-": "–—_", "'": "\"’‘`", "\"": "“”«»", "0": "°", "1": "¹½", "2": "²", "3": "³",
        "$": "€£¥", "(": "[{<", ")": "]}>", "/": "\\|", "+": "±", "=": "≠≈", "%": "‰", "&": "§"
    })
    readonly property var pages: ({
        "letters": [
            ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
            ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
            ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
            ["@shift", "z", "x", "c", "v", "b", "n", "m", "@backspace"],
            ["@symbols", ",", "@emoji", "@space", ".", "@enter"]
        ],
        "symbols": [
            ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
            ["@", "#", "€", "$", "%", "&", "-", "+", "(", ")"],
            ["*", "\"", "'", ":", ";", "!", "?", "/", "\\"],
            ["~", "`", "|", "<", ">", "{", "}", "[", "]", "@backspace"],
            ["@letters", "=", "_", "@space", "^", "@enter"]
        ],
        "emoji": [
            ["😀", "😂", "🙂", "😉", "😍", "😘", "😎", "🤔", "😅", "😭"],
            ["👍", "👎", "👏", "🙏", "💪", "👋", "🤝", "✌️", "👌", "🤷"],
            ["❤️", "🔥", "✨", "🎉", "✅", "❌", "⚠️", "⭐", "💡", "📌"],
            ["☀️", "🌙", "☕", "🍕", "🚗", "✈️", "🏠", "💻", "📱", "@backspace"],
            ["@letters", "📷", "🎵", "@space", "⏰", "@enter"]
        ]
    })
    readonly property var extras: [
        ["esc", "Esc"], ["tab", "Tab"], ["@ctrl", "Ctrl"], ["@alt", "Alt"], ["left", "←"], ["down", "↓"], ["up", "↑"], ["right", "→"],
        ["home", "Home"], ["end", "End"], ["delete", "Del"],
        ["+ctrl+z", "Undo"], ["+ctrl+x", "Cut"], ["+ctrl+c", "Copy"], ["+ctrl+v", "Paste"], ["+ctrl+a", "All"]
    ]
    function keyWidth(k) {
        if (k === "@space") return 4.6
        if (k === "@shift" || k === "@backspace" || k === "@enter" || k === "@symbols" || k === "@letters") return 1.5
        return 1
    }
    function keyLabel(k) {
        switch (k) {
        case "@shift": return win.shift === 2 ? "⇪" : "⇧"
        case "@backspace": return "⌫"
        case "@enter": return "⏎"
        case "@space": return ""
        case "@symbols": return "?123"
        case "@letters": return "ABC"
        case "@emoji": return "☺"
        }
        return win.shift > 0 && win.page === "letters" ? k.toUpperCase() : k
    }

    // ---- what a key does ----
    function commit(k) {
        if (k === "@shift") { shift = shift === 0 ? 1 : shift === 1 ? 2 : 0; return }
        if (k === "@symbols") { page = "symbols"; return }
        if (k === "@letters") { page = "letters"; return }
        if (k === "@emoji") { page = "emoji"; return }
        if (k === "@backspace") { backend.backspace(); return }
        if (k === "@enter") { backend.pressKey("enter", latched); latched = []; return }
        if (k === "@space") { backend.typeText(" ", latched); latched = []; return }
        let text = k
        if (page === "letters" && shift > 0) text = k.toUpperCase()
        backend.typeText(text, latched)
        latched = []
        if (shift === 1) shift = 0
    }
    function commitExtra(e) {
        const id = e[0]
        if (id === "@ctrl" || id === "@alt") { toggleLatch(id.substring(1)); return }
        if (id[0] === "+") { backend.combo(id.substring(1).split("+")); latched = []; return }
        backend.pressKey(id, latched)
        if (id !== "left" && id !== "right" && id !== "up" && id !== "down") latched = []
    }

    // ---- the tab that brings the keyboard back ----
    Rectangle {
        id: tab
        visible: !win.shown
        width: Math.round(win.u * 0.62); height: win.u * 2
        x: win.width - width; y: Math.round(win.height * 0.55)
        radius: 8; color: "#e6202124"; border.color: "#50ffffff"
        Text { anchors.centerIn: parent; text: "⌨"; color: "white"; font.pixelSize: win.u * 0.42 }
        TapHandler { onTapped: backend.setSetting("visible", true) }
    }

    // ---- the keyboard ----
    Rectangle {
        id: panel
        visible: win.shown
        readonly property real cols: 10
        readonly property real innerW: cols * win.u + (cols - 1) * win.gap
        width: win.floating ? innerW + 2 * pad : win.width
        readonly property real pad: Math.round(win.u * 0.22)
        height: column.height + 2 * pad
        // where it is: free while floating (kept inside the screen), along the bottom edge when docked
        property real fx: win.s.x < 0 ? (win.width - width) / 2 : win.s.x
        property real fy: win.s.y < 0 ? win.height - height - win.u * 1.2 : win.s.y
        x: win.floating ? Math.max(0, Math.min(win.width - width, fx)) : 0
        y: win.floating ? Math.max(0, Math.min(win.height - height, fy)) : win.height - height
        radius: win.floating ? 14 : 0
        color: "#202124"
        opacity: win.s.opacity
        border.color: win.floating ? "#40ffffff" : "transparent"

        Column {
            id: column
            x: (panel.width - width) / 2; y: panel.pad
            width: panel.innerW
            spacing: win.gap

            // -- the bar: move, and the choices
            Item {
                width: parent.width; height: Math.round(win.u * 0.62)
                Rectangle {             // the grip: drag it to move the keyboard
                    id: grip
                    anchors.centerIn: parent
                    width: win.u * 2.6; height: parent.height
                    radius: height / 2; color: dragger.active ? "#5f6368" : "transparent"
                    Rectangle { anchors.centerIn: parent; width: win.u * 1.2; height: 5; radius: 3; color: "#9aa0a6"; visible: win.floating }
                    DragHandler {
                        id: dragger
                        enabled: win.floating
                        target: null
                        property real sx: 0
                        property real sy: 0
                        onActiveChanged: {
                            if (active) { sx = panel.x; sy = panel.y }
                            else { backend.setSetting("x", Math.round(panel.x)); backend.setSetting("y", Math.round(panel.y)) }
                        }
                        // the translation is measured in the window, which stands still: the panel follows the finger
                        onTranslationChanged: if (active) { panel.fx = sx + translation.x; panel.fy = sy + translation.y }
                    }
                }
                Row {
                    anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; spacing: win.gap
                    BarButton { label: win.floating ? "⤓" : "⤒"; onTapped: { backend.setSetting("x", -1); backend.setSetting("y", -1); panel.fx = Qt.binding(() => win.s.x < 0 ? (win.width - panel.width) / 2 : win.s.x); panel.fy = Qt.binding(() => win.s.y < 0 ? win.height - panel.height - win.u * 1.2 : win.s.y); backend.setSetting("floating", !win.floating) } }
                    BarButton { label: "A−"; onTapped: backend.setSetting("scale", Math.max(0.7, win.s.scale - 0.1)) }
                    BarButton { label: "A+"; onTapped: backend.setSetting("scale", Math.min(1.6, win.s.scale + 0.1)) }
                    BarButton { label: "◐"; onTapped: backend.setSetting("opacity", win.s.opacity > 0.9 ? 0.75 : win.s.opacity > 0.7 ? 0.55 : 0.96) }
                }
                Row {
                    anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: win.gap
                    BarButton { label: "📋"; lit: win.clipsOpen; onTapped: { win.clipsOpen = !win.clipsOpen; if (win.clipsOpen) backend.refreshClips() } }
                    BarButton { label: "⌥"; lit: win.s.extras; onTapped: backend.setSetting("extras", !win.s.extras) }
                    BarButton { label: "✕"; onTapped: backend.setSetting("visible", false) }
                }
            }

            // -- suggestions, or the clipboard history
            Item {
                width: parent.width; height: Math.round(win.u * 0.74)
                Text {
                    visible: backend.error.length > 0
                    anchors.fill: parent; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
                    text: backend.error; color: "#f28b82"; font.pixelSize: win.u * 0.3
                }
                Row {                   // word suggestions
                    visible: !win.clipsOpen && backend.error.length === 0
                    anchors.fill: parent; spacing: win.gap
                    Repeater {
                        model: backend.suggestions
                        Chip { width: (column.width - 2 * win.gap) / 3; text: modelData; centered: true; onTapped: backend.pick(modelData) }
                    }
                }
                ListView {              // the clipboard history: a tap pastes the entry
                    visible: win.clipsOpen
                    anchors.fill: parent; orientation: ListView.Horizontal; spacing: win.gap; clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    model: backend.clips
                    delegate: Chip { width: Math.min(win.u * 4.2, implicitWidth); height: ListView.view.height; text: String(modelData).replace(/\s+/g, " "); onTapped: backend.pasteClip(modelData) }
                    Text { visible: parent.count === 0; anchors.centerIn: parent; text: "Nothing copied yet"; color: "#9aa0a6"; font.pixelSize: win.u * 0.3 }
                }
            }

            // -- the keys a tablet lacks
            ListView {
                visible: win.s.extras
                width: parent.width; height: Math.round(win.u * 0.74)
                orientation: ListView.Horizontal; spacing: win.gap; clip: true
                boundsBehavior: Flickable.StopAtBounds
                model: win.extras
                delegate: Chip {
                    height: ListView.view.height
                    width: Math.max(win.u * 1.02, implicitWidth)
                    centered: true
                    text: modelData[1]
                    lit: modelData[0][0] === "@" && win.latched.indexOf(modelData[0].substring(1)) >= 0
                    repeats: ["left", "right", "up", "down", "delete"].indexOf(modelData[0]) >= 0
                    onTapped: win.commitExtra(modelData)
                }
            }

            // -- the keys
            Item {
                id: keysArea
                width: parent.width
                height: 5 * win.u + 4 * win.gap
                property var items: []          // the key rectangles, for finding the one under a finger
                Column {
                    id: rows
                    anchors.fill: parent; spacing: win.gap
                    Repeater {
                        model: win.pages[win.page]
                        Row {
                            id: rowItem
                            required property var modelData
                            anchors.horizontalCenter: parent.horizontalCenter
                            spacing: win.gap
                            readonly property real units: { let n = 0; for (const k of modelData) n += win.keyWidth(k); return n }
                            // a row is as wide as the ten keys of the first one: its keys share what is left
                            readonly property real unit: (keysArea.width - (modelData.length - 1) * win.gap) / Math.max(units, 10 - (10 - modelData.length) * 0)
                            Repeater {
                                model: rowItem.modelData
                                Rectangle {
                                    id: keyItem
                                    required property string modelData
                                    readonly property string key: modelData
                                    property bool down: false
                                    width: Math.floor(Math.min(rowItem.unit, win.u * (rowItem.modelData.length < 10 && win.keyWidth(key) === 1 ? 1.0 : 99)) * win.keyWidth(key))
                                    height: win.u
                                    radius: 7
                                    color: down ? "#8ab4f8" : key[0] === "@" && key !== "@space" ? "#3c4043" : "#5f6368"
                                    border.color: key === "@shift" && win.shift > 0 ? "#8ab4f8" : "transparent"; border.width: 2
                                    Text {
                                        anchors.centerIn: parent
                                        text: win.keyLabel(keyItem.key)
                                        color: keyItem.down ? "#202124" : "white"
                                        font.pixelSize: keyItem.key.length > 1 && keyItem.key[0] === "@" ? win.u * 0.36 : win.u * 0.44
                                    }
                                    Text {              // a hint that a long press has more
                                        visible: win.alternates[keyItem.key] !== undefined && win.page !== "emoji"
                                        anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 4
                                        text: visible ? win.alternates[keyItem.key][0] : ""; color: "#bdc1c6"; font.pixelSize: win.u * 0.2
                                    }
                                    Rectangle { visible: keyItem.key === "@space"; anchors.centerIn: parent; width: parent.width * 0.5; height: 3; radius: 2; color: "#9aa0a6" }
                                    Component.onCompleted: keysArea.items = keysArea.items.concat([keyItem])
                                    Component.onDestruction: keysArea.items = keysArea.items.filter(i => i !== keyItem)
                                }
                            }
                        }
                    }
                }

                function keyAt(x, y) {
                    let best = null, bestD = 1e9
                    for (const it of items) {
                        const p = it.mapToItem(keysArea, 0, 0)
                        if (x >= p.x - win.gap / 2 && x < p.x + it.width + win.gap / 2 && y >= p.y - win.gap / 2 && y < p.y + it.height + win.gap / 2) return it
                        const d = Math.abs(x - (p.x + it.width / 2)) + Math.abs(y - (p.y + it.height / 2))
                        if (d < bestD) { bestD = d; best = it }
                    }
                    return bestD < win.u ? best : null
                }

                // Every finger is followed by itself, so that two can type one right after the other. A key is sent when the
                // finger leaves it (a long press first opens its accents; sliding on the space bar moves the cursor instead).
                property var fingers: ({})
                MultiPointTouchArea {
                    anchors.fill: parent
                    maximumTouchPoints: 4
                    onPressed: points => { for (const p of points) keysArea.press(p) }
                    onUpdated: points => { for (const p of points) keysArea.move(p) }
                    onReleased: points => { for (const p of points) keysArea.release(p, true) }
                    onCanceled: points => { for (const p of points) keysArea.release(p, false) }
                }
                function press(p) {
                    const it = keyAt(p.x, p.y)
                    if (!it) return
                    it.down = true
                    fingers[p.pointId] = { item: it, x0: p.x, steps: 0, cursor: false, fired: false }
                    if (it.key === "@backspace") { backend.backspace(); fingers[p.pointId].fired = true; repeat.finger = p.pointId; repeat.interval = 420; repeat.restart() }
                    else if (win.alternates[it.key] !== undefined && win.page !== "emoji") { hold.finger = p.pointId; hold.restart() }
                }
                function move(p) {
                    const f = fingers[p.pointId]
                    if (!f) return
                    if (win.alt && win.alt.finger === p.pointId) {
                        const i = Math.max(0, Math.min(win.alt.list.length - 1, Math.floor((p.x - win.alt.x0) / win.u + win.alt.start)))
                        if (i !== win.alt.index) win.alt = Object.assign({}, win.alt, { index: i })
                        return
                    }
                    if (f.item.key === "@space") {
                        const steps = Math.trunc((p.x - f.x0) / (win.u * 0.38))
                        if (steps !== f.steps) {
                            f.cursor = true
                            const name = steps > f.steps ? "right" : "left"
                            for (let n = Math.abs(steps - f.steps); n > 0; n--) backend.pressKey(name, [])
                            f.steps = steps
                        }
                        return
                    }
                    if (f.fired) return
                    const it = keyAt(p.x, p.y)
                    if (it && it !== f.item) {             // slid to the neighbour before letting go: that one counts
                        f.item.down = false; it.down = true; f.item = it
                        hold.stop()
                        if (win.alternates[it.key] !== undefined && win.page !== "emoji") { hold.finger = p.pointId; hold.restart() }
                    }
                }
                function release(p, send) {
                    const f = fingers[p.pointId]
                    if (!f) return
                    delete fingers[p.pointId]
                    f.item.down = false
                    if (hold.finger === p.pointId) hold.stop()
                    if (repeat.finger === p.pointId) repeat.stop()
                    if (win.alt && win.alt.finger === p.pointId) {
                        const text = win.alt.list[win.alt.index]
                        win.alt = null
                        if (send) { backend.typeText(win.shift > 0 && win.page === "letters" ? text.toUpperCase() : text, win.latched); win.latched = []; if (win.shift === 1) win.shift = 0 }
                        return
                    }
                    if (send && !f.fired && !f.cursor) win.commit(f.item.key)
                }
                Timer {                 // a long press: the accents of the key
                    id: hold
                    property int finger: -1
                    interval: 380
                    onTriggered: {
                        const f = keysArea.fingers[finger]
                        if (!f) return
                        const list = [f.item.key].concat(Array.from(win.alternates[f.item.key]))
                        const p = f.item.mapToItem(win.contentItem, 0, 0)
                        // the list opens above the key, shifted so that it stays on the screen; the finger starts on the first accent
                        const w = list.length * win.u
                        const left = Math.max(4, Math.min(win.width - w - 4, p.x + f.item.width / 2 - win.u * 1.5))
                        const start = Math.max(0, Math.min(list.length - 1, Math.floor((p.x + f.item.width / 2 - left) / win.u)))
                        win.alt = { finger: finger, list: list, index: start, start: start, x0: f.x0, left: left, top: p.y - win.u * 1.15 }
                    }
                }
                Timer {                 // backspace held: again and again, faster after a while
                    id: repeat
                    property int finger: -1
                    property int count: 0
                    repeat: true
                    onRunningChanged: if (!running) count = 0
                    onTriggered: { backend.backspace(); count++; interval = count > 12 ? 35 : 70 }
                }
            }
        }
    }

    // ---- the accents of a key, above it ----
    Rectangle {
        id: altBox
        visible: win.alt !== null
        x: win.alt ? win.alt.left : 0
        y: win.alt ? Math.max(0, win.alt.top) : 0
        width: win.alt ? win.alt.list.length * win.u : 0
        height: win.u * 1.05
        radius: 9; color: "#3c4043"; border.color: "#60ffffff"
        Row {
            anchors.fill: parent
            Repeater {
                model: win.alt ? win.alt.list : []
                Rectangle {
                    width: win.u; height: altBox.height; radius: 9
                    color: win.alt && index === win.alt.index ? "#8ab4f8" : "transparent"
                    Text { anchors.centerIn: parent; text: win.shift > 0 && win.page === "letters" ? modelData.toUpperCase() : modelData; color: win.alt && index === win.alt.index ? "#202124" : "white"; font.pixelSize: win.u * 0.46 }
                }
            }
        }
    }

    // ---- which parts of the window take touches ----
    function tellRects() {
        const r = []
        if (win.shown) {
            r.push([panel.x, panel.y, panel.width, panel.height])
            if (win.alt) r.push([altBox.x, altBox.y, altBox.width, altBox.height])
        } else {
            r.push([tab.x, tab.y, tab.width, tab.height])
        }
        backend.setTouchRects(r)
    }
    Timer { id: rects; interval: 0; onTriggered: win.tellRects() }
    Connections { target: panel; function onXChanged() { rects.restart() } function onYChanged() { rects.restart() } function onWidthChanged() { rects.restart() } function onHeightChanged() { rects.restart() } }
    onShownChanged: rects.restart()
    onAltChanged: rects.restart()
    onWidthChanged: rects.restart()
    onHeightChanged: rects.restart()
    Component.onCompleted: { rects.restart(); settle.start(); shift = 1 }      // a text usually starts with a capital
    Timer { id: settle; interval: 600; onTriggered: win.tellRects() }      // once more when the window has its size

    // ---- small parts ----
    component BarButton: Rectangle {
        property string label
        property bool lit: false
        signal tapped()
        width: Math.round(win.u * 0.86); height: Math.round(win.u * 0.62); radius: 6
        color: tap.pressed ? "#8ab4f8" : lit ? "#4a6da7" : "#3c4043"
        Text { anchors.centerIn: parent; text: parent.label; color: "white"; font.pixelSize: win.u * 0.3 }
        TapHandler { id: tap; onTapped: parent.tapped() }
    }
    component Chip: Rectangle {
        id: chip
        property string text
        property bool centered: false
        property bool lit: false
        property bool repeats: false
        signal tapped()
        implicitWidth: label.implicitWidth + win.u * 0.5
        height: parent ? parent.height : win.u * 0.74
        radius: 6
        color: chipTap.pressed ? "#8ab4f8" : lit ? "#4a6da7" : "#3c4043"
        Text {
            id: label
            anchors.fill: parent; anchors.leftMargin: win.u * 0.2; anchors.rightMargin: win.u * 0.2
            horizontalAlignment: chip.centered ? Text.AlignHCenter : Text.AlignLeft; verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight; text: chip.text; color: "white"; font.pixelSize: win.u * 0.3
        }
        TapHandler {
            id: chipTap
            onTapped: if (!again.fired) chip.tapped()
            onPressedChanged: { if (pressed && chip.repeats) { again.fired = false; again.interval = 420; again.start() } else again.stop() }
        }
        Timer { id: again; property bool fired: false; repeat: true; onTriggered: { fired = true; interval = 80; chip.tapped() } }
    }
}
