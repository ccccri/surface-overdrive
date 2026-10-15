// SPDX-License-Identifier: MIT
import QtQuick
import org.kde.kirigami as Kirigami

// Nine dots joined by dragging a finger (or the mouse) over them, as on a phone; lifting it hands over the dots joined, numbered
// 1-9 left to right and top to bottom (drawn). A dot passed over on the way (1 to 3 crosses 2) is joined too. Used by UnlockPad.qml
// (lock and login screens) and by the Screen Locking page of System Settings.
Item {
    id: pattern

    property real key: Kirigami.Units.gridUnit * 2.9
    signal drawn(string dots)

    implicitWidth: key * 3 + Kirigami.Units.largeSpacing * 4
    implicitHeight: implicitWidth

    readonly property real cell: width / 3
    property var dots: []
    property point finger: Qt.point(-1, -1)

    function centre(n) { return Qt.point(((n - 1) % 3 + 0.5) * cell, (Math.floor((n - 1) / 3) + 0.5) * cell) }
    function dotAt(x, y) {
        const col = Math.floor(x / cell), row = Math.floor(y / cell)
        if (col < 0 || col > 2 || row < 0 || row > 2) return 0
        const n = row * 3 + col + 1, c = centre(n)
        return Math.hypot(x - c.x, y - c.y) < cell * 0.38 ? n : 0
    }
    function join(n) {
        if (!n || dots.indexOf(n) >= 0) return
        const list = dots.slice()
        if (list.length) {
            const a = list[list.length - 1], mid = (a + n) / 2
            const ar = Math.floor((a - 1) / 3), ac = (a - 1) % 3, nr = Math.floor((n - 1) / 3), nc = (n - 1) % 3
            if (Number.isInteger(mid) && (ar + nr) % 2 === 0 && (ac + nc) % 2 === 0 && list.indexOf(mid) < 0) list.push(mid)
        }
        list.push(n)
        dots = list
    }
    onDotsChanged: lines.requestPaint()
    onFingerChanged: lines.requestPaint()

    Canvas {
        id: lines
        anchors.fill: parent
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            if (!pattern.dots.length) return
            ctx.strokeStyle = Kirigami.Theme.highlightColor
            ctx.lineWidth = Kirigami.Units.gridUnit * 0.3
            ctx.lineCap = "round"
            ctx.lineJoin = "round"
            ctx.beginPath()
            const first = pattern.centre(pattern.dots[0])
            ctx.moveTo(first.x, first.y)
            for (let i = 1; i < pattern.dots.length; i++) {
                const p = pattern.centre(pattern.dots[i])
                ctx.lineTo(p.x, p.y)
            }
            if (pattern.finger.x >= 0) ctx.lineTo(pattern.finger.x, pattern.finger.y)
            ctx.stroke()
        }
    }
    Repeater {
        model: 9
        Rectangle {
            required property int index
            readonly property bool on: pattern.dots.indexOf(index + 1) >= 0
            readonly property point c: pattern.centre(index + 1)
            width: on ? Kirigami.Units.gridUnit * 1.4 : Kirigami.Units.gridUnit * 0.9
            height: width
            radius: width / 2
            x: c.x - width / 2
            y: c.y - height / 2
            color: on ? Kirigami.Theme.highlightColor : Kirigami.Theme.textColor
            Behavior on width { NumberAnimation { duration: Kirigami.Units.shortDuration } }
        }
    }
    MouseArea {
        anchors.fill: parent
        preventStealing: true
        onPressed: mouse => { pattern.dots = []; pattern.join(pattern.dotAt(mouse.x, mouse.y)); pattern.finger = Qt.point(mouse.x, mouse.y) }
        onPositionChanged: mouse => { pattern.join(pattern.dotAt(mouse.x, mouse.y)); pattern.finger = Qt.point(mouse.x, mouse.y) }
        onReleased: {
            pattern.finger = Qt.point(-1, -1)
            const joined = pattern.dots.join("")
            pattern.dots = []
            if (joined.length > 0) pattern.drawn(joined)
        }
        onCanceled: { pattern.finger = Qt.point(-1, -1); pattern.dots = [] }
    }
}
