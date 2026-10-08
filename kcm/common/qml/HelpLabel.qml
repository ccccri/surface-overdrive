// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// A name with an explanation behind it. The explanation is a tooltip: it shows under the mouse or the hovering pen, and for
// fingers after a tap or a long press on the name (a second tap, or a few seconds, close it).
QQC2.Label {
    id: label

    property string help

    elide: Text.ElideRight
    HoverHandler { id: hover; acceptedDevices: PointerDevice.Mouse | PointerDevice.Stylus | PointerDevice.TouchPad }
    TapHandler {
        onTapped: { tip.pinned = !tip.pinned; if (tip.pinned) unpin.restart() }
        onLongPressed: { tip.pinned = true; unpin.restart() }
    }
    Timer { id: unpin; interval: 7000; onTriggered: tip.pinned = false }
    QQC2.ToolTip {
        id: tip
        property bool pinned: false
        text: label.help
        visible: label.help.length > 0 && (pinned || hover.hovered)
        delay: pinned ? 0 : Kirigami.Units.toolTipDelay
        timeout: -1
    }
}
