// SPDX-License-Identifier: MIT
import QtQuick
import org.kde.kirigami as Kirigami

// Frequency response of the ten bands with a handle per band: drag to change frequency and gain.
Item {
    id: g
    property var bands: []
    property int selected: 4
    readonly property real fmin: 20
    readonly property real fmax: 20000
    readonly property real dbRange: 15
    signal bandMoved(int index, real freq, real gain)
    signal bandSelected(int index)
    implicitHeight: Kirigami.Units.gridUnit * 14

    // The curve and the handles live in the graph minus a margin of half a handle, so that a handle at the very edge of the
    // frequency or gain range still sits wholly inside the graph.
    readonly property real handle: Kirigami.Units.gridUnit * 1.8
    readonly property real pad: handle / 2
    readonly property real plotWidth: Math.max(1, width - 2 * pad)
    readonly property real plotHeight: Math.max(1, height - 2 * pad)
    function clamp(v, low, high) { return Math.max(low, Math.min(high, v)) }
    function xOf(f) { return pad + Math.log(clamp(f, fmin, fmax) / fmin) / Math.log(fmax / fmin) * plotWidth }
    function fOf(x) { return fmin * Math.pow(fmax / fmin, clamp((x - pad) / plotWidth, 0, 1)) }
    function yOf(db) { return pad + plotHeight / 2 - clamp(db, -dbRange, dbRange) / dbRange * plotHeight / 2 }
    function dbOf(y) { return clamp((pad + plotHeight / 2 - y) / (plotHeight / 2) * dbRange, -dbRange, dbRange) }

    // RBJ cookbook biquad: the same maths as the filter chain
    function coef(b) {
        if (!b.on) return [1, 0, 0, 1, 0, 0]
        const rate = 48000
        const f = Math.min(b.freq, rate / 2 * 0.98), q = Math.max(0.1, b.q), gn = b.gain
        if ((b.type === "peak" || b.type === "lowshelf" || b.type === "highshelf") && Math.abs(gn) < 1e-4) return [1, 0, 0, 1, 0, 0]
        const A = Math.pow(10, gn / 40), w = 2 * Math.PI * f / rate, cw = Math.cos(w), sw = Math.sin(w), al = sw / (2 * q)
        const s = 2 * Math.sqrt(A) * al
        switch (b.type) {
        case "peak": return [1 + al * A, -2 * cw, 1 - al * A, 1 + al / A, -2 * cw, 1 - al / A]
        case "lowshelf": return [A * ((A + 1) - (A - 1) * cw + s), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - s),
                                 (A + 1) + (A - 1) * cw + s, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - s]
        case "highshelf": return [A * ((A + 1) + (A - 1) * cw + s), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - s),
                                  (A + 1) - (A - 1) * cw + s, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - s]
        case "lowpass": return [(1 - cw) / 2, 1 - cw, (1 - cw) / 2, 1 + al, -2 * cw, 1 - al]
        case "highpass": return [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2, 1 + al, -2 * cw, 1 - al]
        }
        return [1, 0, 0, 1, 0, 0]
    }
    function responseDb(cs, freq) {
        const w = 2 * Math.PI * freq / 48000, c1 = Math.cos(w), c2 = Math.cos(2 * w)
        let total = 0
        for (const c of cs) {
            const num = c[0] * c[0] + c[1] * c[1] + c[2] * c[2] + 2 * (c[0] * c[1] + c[1] * c[2]) * c1 + 2 * c[0] * c[2] * c2
            const den = c[3] * c[3] + c[4] * c[4] + c[5] * c[5] + 2 * (c[3] * c[4] + c[4] * c[5]) * c1 + 2 * c[3] * c[5] * c2
            total += 10 * Math.log10(Math.max(num, 1e-30) / Math.max(den, 1e-30))
        }
        return total
    }
    onBandsChanged: canvas.requestPaint()
    onSelectedChanged: canvas.requestPaint()
    onWidthChanged: canvas.requestPaint()
    onHeightChanged: canvas.requestPaint()

    Rectangle { anchors.fill: parent; radius: 4; color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.05) }
    Canvas {
        id: canvas
        anchors.fill: parent
        onPaint: {
            const c = getContext("2d")
            c.clearRect(0, 0, width, height)
            c.lineWidth = 1
            c.font = "10px sans-serif"
            c.fillStyle = Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.6)
            c.strokeStyle = Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.15)
            for (const f of [50, 100, 200, 500, 1000, 2000, 5000, 10000]) {
                const x = g.xOf(f)
                c.beginPath(); c.moveTo(x, 0); c.lineTo(x, height); c.stroke()
                c.fillText(f >= 1000 ? (f / 1000) + "k" : f, x + 2, height - 3)
            }
            for (const db of [-10, -5, 0, 5, 10]) {
                const y = g.yOf(db)
                c.beginPath(); c.moveTo(0, y); c.lineTo(width, y); c.stroke()
                c.fillText((db > 0 ? "+" : "") + db + " dB", 3, y - 2)
            }
            const cs = g.bands.map(b => g.coef(b))
            c.strokeStyle = Kirigami.Theme.highlightColor
            c.lineWidth = 2
            c.beginPath()
            for (let x = g.pad; x <= width - g.pad; x += 2) {
                const y = g.yOf(g.responseDb(cs, g.fOf(x)))
                if (x === g.pad) c.moveTo(x, y); else c.lineTo(x, y)
            }
            c.stroke()
        }
    }
    Repeater {
        // One handle per band, by number: with the list of bands as the model every change of a band would build all the handles
        // again, also the one under the finger, and the drag would break.
        model: g.bands.length
        delegate: Rectangle {
            id: h
            readonly property var b: g.bands[index] || ({ freq: 1000, gain: 0, on: false })
            width: g.handle; height: width; radius: width / 2
            x: g.xOf(b.freq) - width / 2
            y: g.yOf(b.gain) - height / 2
            color: index === g.selected ? Kirigami.Theme.highlightColor : Kirigami.Theme.backgroundColor
            opacity: b.on ? 1 : 0.4
            border.width: 2
            border.color: Kirigami.Theme.highlightColor
            Text { anchors.centerIn: parent; text: index + 1; font.pixelSize: parent.width * 0.5; color: index === g.selected ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor }
            MouseArea {
                anchors.fill: parent
                anchors.margins: -Kirigami.Units.smallSpacing      // a little larger than the dot: easier to catch with a finger
                preventStealing: true                               // the page must not scroll while a band is dragged
                onPressed: g.bandSelected(index)
                onPositionChanged: mouse => {
                    if (!pressed) return
                    const p = mapToItem(g, mouse.x, mouse.y)
                    g.bandMoved(index, g.fOf(p.x), g.dbOf(p.y))
                }
            }
        }
    }
}
