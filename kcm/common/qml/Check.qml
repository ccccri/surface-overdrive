// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// A check box with its explanation as a tooltip: under the mouse or the hovering pen, or while a finger holds it down.
QQC2.CheckBox {
    id: check

    property string help

    QQC2.ToolTip.text: help
    QQC2.ToolTip.visible: help.length > 0 && (hovered || pressed)
    QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
}
