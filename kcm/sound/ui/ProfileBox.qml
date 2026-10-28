// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// The sound profiles (presets) of an output or of the microphone as a list: it shows the one in effect, "Custom" when the
// settings match none, and choosing one applies it at once.
QQC2.ComboBox {
    id: box

    property var presets: []          // [{ name, builtin }]
    property int current: -1          // index of the profile in effect, -1 for none
    signal chosen(string name)

    implicitWidth: Kirigami.Units.gridUnit * 12
    popup.modal: true; popup.dim: false; popup.closePolicy: QQC2.Popup.CloseOnEscape | QQC2.Popup.CloseOnPressOutside          // a touch outside the list only closes it (see Bars.qml)
    model: presets.map(p => p.name)
    displayText: current >= 0 && current < presets.length ? presets[current].name : i18n("Custom")
    onActivated: index => { if (index >= 0 && index < presets.length) box.chosen(presets[index].name) }
    // the list opens on the profile in effect
    Binding { target: box; property: "currentIndex"; value: box.current; delayed: true; restoreMode: Binding.RestoreNone }
    QQC2.ToolTip.text: i18n("Sound profiles: saved sets of the equalizer settings below. Choosing one applies it at once; change a setting and it reads \"Custom\" until you save it as a profile.")
    QQC2.ToolTip.visible: hovered && !popup.visible
    QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
}
