// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// Scroll bars that stay in sight. On a touch screen Plasma's bars show only while one scrolls and then fade: here every
// vertical bar under `target` stays for as long as there is something to scroll, like the one of the sidebar of System
// Settings. Pages of Plasma build their parts a moment after they load, so the bars are looked for a few times.
Item {
    id: bars

    property Item target: null
    visible: false

    function style(item, depth) {
        if (!item || depth > 12) return
        if (item.policy !== undefined && item.size !== undefined && item.orientation !== undefined) {
            if (item.orientation === Qt.Vertical && item.objectName !== "overdriveBar") {
                item.objectName = "overdriveBar"
                item.policy = Qt.binding(() => item.size < 0.999 ? QQC2.ScrollBar.AlwaysOn : QQC2.ScrollBar.AlwaysOff)
            }
            return
        }
        for (let i = 0; item.children && i < item.children.length; i++) style(item.children[i], depth + 1)
    }
    Timer {
        property int rounds: 0
        interval: 1200; repeat: true; running: bars.target !== null && rounds < 6
        onTriggered: { rounds++; try { bars.style(bars.target, 0) } catch (e) { console.warn("Surface Control: scroll bars:", e) } }
    }
}
