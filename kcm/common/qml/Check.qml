// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// A check box with its explanation: a tooltip under the mouse or the hovering pen, and the small (i) button Plasma puts next
// to a setting that has one, which is what a finger can reach.
RowLayout {
    id: check

    property string text
    property string help
    property alias checked: box.checked
    property bool helpButton: true
    signal toggled()

    Layout.fillWidth: false
    Layout.fillHeight: false
    spacing: Kirigami.Units.smallSpacing

    QQC2.CheckBox {
        id: box
        text: check.text
        onToggled: check.toggled()
        QQC2.ToolTip.text: check.help
        QQC2.ToolTip.visible: check.help.length > 0 && hovered
        QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
    }
    Kirigami.ContextualHelpButton {
        visible: check.helpButton && check.help.length > 0
        toolTipText: check.help
    }
}
