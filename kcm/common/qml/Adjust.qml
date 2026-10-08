// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// One adjustment: its name, a number that can be typed, a button back to the default and the slider.
// The explanation stays out of the way: it is a tooltip, shown under the mouse or the hovering pen and, for fingers, by a tap on
// the name (a second tap or a few seconds close it). It never takes room in the layout, so nothing moves when it shows.
ColumnLayout {
    id: adjust

    property string label
    property string help
    property real from: 0
    property real to: 1
    property real step: 0.1
    property real value: 0
    property real neutral: 0
    property string unit: ""
    property var names: null          // names of the steps instead of a number ("off", "low", ...)
    property bool showReset: true
    readonly property alias pressed: slider.pressed
    signal edited(real v)             // the user chose a value
    signal reset()

    readonly property int decimals: step >= 1 ? 0 : (step >= 0.1 ? 1 : 2)
    function snap(v) { return Math.max(from, Math.min(to, Math.round(v / step) * step)) }
    function shown(v) { return snap(v).toFixed(decimals) }

    Layout.fillWidth: true
    spacing: 0

    RowLayout {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing

        QQC2.Label {
            id: name
            text: adjust.label
            font.bold: true
            Layout.fillWidth: true
            elide: Text.ElideRight
            HoverHandler { id: hover; acceptedDevices: PointerDevice.Mouse | PointerDevice.Stylus | PointerDevice.TouchPad }
            TapHandler { onTapped: { tip.pinned = !tip.pinned; if (tip.pinned) unpin.restart() } }
            Timer { id: unpin; interval: 7000; onTriggered: tip.pinned = false }
            QQC2.ToolTip {
                id: tip
                property bool pinned: false
                text: adjust.help
                visible: adjust.help.length > 0 && (pinned || hover.hovered)
                delay: pinned ? 0 : Kirigami.Units.toolTipDelay
                timeout: -1
            }
        }
        QQC2.Label {
            visible: adjust.names !== null
            text: adjust.names ? adjust.names[Math.round(slider.value)] : ""
            opacity: 0.8
        }
        QQC2.TextField {
            id: field
            visible: adjust.names === null
            Layout.preferredWidth: Kirigami.Units.gridUnit * 4
            horizontalAlignment: Text.AlignRight
            inputMethodHints: Qt.ImhFormattedNumbersOnly
            selectByMouse: true
            enabled: slider.enabled
            onActiveFocusChanged: if (activeFocus) selectAll(); else text = adjust.shown(slider.value)
            onEditingFinished: {
                const v = parseFloat(text.replace(",", "."))
                if (isNaN(v)) { text = adjust.shown(slider.value); return }
                const s = adjust.snap(v)
                text = adjust.shown(s)
                if (Math.abs(s - slider.value) > adjust.step / 4) { slider.value = s; adjust.edited(s) }
            }
            Binding { target: field; property: "text"; value: adjust.shown(slider.value); when: !field.activeFocus; restoreMode: Binding.RestoreNone }
        }
        QQC2.Label { visible: adjust.unit.length > 0 && adjust.names === null; text: adjust.unit; opacity: 0.7 }
        QQC2.ToolButton {
            visible: adjust.showReset
            icon.name: "edit-undo"
            display: QQC2.AbstractButton.IconOnly
            opacity: Math.abs(slider.value - adjust.neutral) > adjust.step / 2 ? 1 : 0
            enabled: opacity > 0 && slider.enabled
            onClicked: { slider.value = adjust.neutral; adjust.reset() }
            QQC2.ToolTip.text: i18n("Back to the default")
            QQC2.ToolTip.visible: hovered
        }
    }
    QQC2.Slider {
        id: slider
        Layout.fillWidth: true
        from: adjust.from; to: adjust.to
        // no stepSize: the desktop style would draw a tick for every step. The value is rounded to the step here instead.
        onMoved: { value = adjust.snap(value); adjust.edited(value) }
        Binding { target: slider; property: "value"; value: adjust.value; when: !slider.pressed; restoreMode: Binding.RestoreNone }
    }
}
