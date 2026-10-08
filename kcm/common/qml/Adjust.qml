// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// One adjustment: its name, the value, and the slider.
//  - The value looks like plain text at the right edge; touch or click it and it becomes a field to type in.
//  - The arrow back to the default sits left of the value and only exists while the value is not the default, so the values of
//    all the adjustments line up at the right whether the arrow is there or not.
//  - The explanation is a tooltip: under the mouse or the hovering pen, or after a tap on the name. It never takes room in the
//    layout, so nothing moves when it shows.
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

        HelpLabel {
            text: adjust.label
            help: adjust.help
            font.bold: true
            Layout.fillWidth: true
        }
        QQC2.ToolButton {
            visible: adjust.showReset && slider.enabled && Math.abs(slider.value - adjust.neutral) > adjust.step / 2
            icon.name: "edit-undo"
            display: QQC2.AbstractButton.IconOnly
            implicitHeight: field.implicitHeight
            implicitWidth: implicitHeight
            onClicked: { slider.value = adjust.neutral; adjust.reset() }
            QQC2.ToolTip.text: i18n("Back to the default")
            QQC2.ToolTip.visible: hovered
        }
        QQC2.Label {
            visible: adjust.names !== null
            text: adjust.names ? adjust.names[Math.round(slider.value)] : ""
            opacity: 0.8
        }
        QQC2.TextField {
            id: field
            visible: adjust.names === null
            readonly property string full: adjust.shown(slider.value) + (adjust.unit.length > 0 ? " " + adjust.unit : "")
            // as wide as the longest value this adjustment can show, so the row does not shift while the slider moves
            Layout.preferredWidth: Math.max(sizer.advanceWidth, Kirigami.Units.gridUnit * 2.5) + leftPadding + rightPadding
            TextMetrics { id: sizer; font: field.font; text: (adjust.shown(adjust.from).length > adjust.shown(adjust.to).length ? adjust.shown(adjust.from) : adjust.shown(adjust.to)) + (adjust.unit.length > 0 ? " " + adjust.unit : "") + "0" }
            horizontalAlignment: Text.AlignRight
            inputMethodHints: Qt.ImhFormattedNumbersOnly
            selectByMouse: true
            enabled: slider.enabled
            opacity: 0.85
            // plain text until it is being edited or pointed at
            background: Rectangle {
                radius: 3
                color: field.activeFocus ? Kirigami.Theme.backgroundColor : "transparent"
                border.width: field.activeFocus || fieldHover.hovered ? 1 : 0
                border.color: field.activeFocus ? Kirigami.Theme.highlightColor : Kirigami.Theme.disabledTextColor
            }
            HoverHandler { id: fieldHover; cursorShape: Qt.IBeamCursor }
            onActiveFocusChanged: {
                if (activeFocus) { text = adjust.shown(slider.value); selectAll() }      // the bare number while typing
                else text = full
            }
            onEditingFinished: {
                const v = parseFloat(text.replace(",", "."))
                if (!isNaN(v)) {
                    const s = adjust.snap(v)
                    if (Math.abs(s - slider.value) > adjust.step / 4) { slider.value = s; adjust.edited(s) }
                }
                focus = false
            }
            Binding { target: field; property: "text"; value: field.full; when: !field.activeFocus; restoreMode: Binding.RestoreNone }
        }
    }
    QQC2.Slider {
        id: slider
        Layout.fillWidth: true
        from: adjust.from; to: adjust.to
        // no stepSize: the desktop style would draw a tick for every step. The value is rounded to the step here instead.
        onMoved: { value = adjust.snap(value); adjust.edited(value) }
        // A finger that moves a little up or down while it drags the handle must not scroll the page instead.
        property Item scroller: null
        onPressedChanged: {
            if (pressed) {
                for (let p = parent; p; p = p.parent) if (p.contentY !== undefined && p.interactive !== undefined) { scroller = p; break }
                if (scroller) scroller.interactive = false
            } else if (scroller) scroller.interactive = true
        }
        Binding { target: slider; property: "value"; value: adjust.value; when: !slider.pressed; restoreMode: Binding.RestoreNone }
    }
}
