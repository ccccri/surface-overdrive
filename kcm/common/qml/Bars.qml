// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Window
import org.kde.kirigami as Kirigami

// Two touch-screen fixes for every page, ours and the pages of Plasma inside them, under `target`:
//  - Scroll bars that stay in sight. On a touch screen Plasma's bars show only while one scrolls and then fade: here every
//    vertical bar stays for as long as there is something to scroll, like the one of the sidebar of System Settings.
//  - Drop-down lists that keep a stray touch. The list of a ComboBox is not modal: a touch outside it closes it and also
//    goes on to whatever lies under it, so a finger that misses the list (or taps beside it to close it) moved the slider
//    underneath, and it took several taps to get anything done. Made modal (without dimming), a touch outside only closes it;
//    a touch on the list's own button closes it too, as before.
// Pages of Plasma build their parts a moment after they load and make rows again when a device comes or goes, so the page is
// looked through a few times at first and then every couple of seconds while its window is in front.
Item {
    id: bars

    property Item target: null
    visible: false

    function style(item, depth) {
        if (!item || depth > 40) return
        if (item.policy !== undefined && item.size !== undefined && item.orientation !== undefined) {
            if (item.orientation === Qt.Vertical && item.objectName !== "overdriveBar") {
                item.objectName = "overdriveBar"
                item.policy = Qt.binding(() => item.size < 0.999 ? QQC2.ScrollBar.AlwaysOn : QQC2.ScrollBar.AlwaysOff)
            }
            return
        }
        if (item.currentIndex !== undefined && item.popup && item.popup.modal === false && item.popup.dim !== undefined) {
            item.popup.dim = false
            item.popup.modal = true
            // modal, a touch on the list's own button no longer reached it to close the list: close on any touch outside the
            // list, the button included
            item.popup.closePolicy = QQC2.Popup.CloseOnEscape | QQC2.Popup.CloseOnPressOutside
        }
        for (let i = 0; item.children && i < item.children.length; i++) style(item.children[i], depth + 1)
    }
    function run() { try { bars.style(bars.target, 0) } catch (e) { console.warn("Surface Control: scroll bars and lists:", e) } }
    Timer {
        property int rounds: 0
        interval: 1200; repeat: true; running: bars.target !== null && rounds < 6
        onTriggered: { rounds++; bars.run() }
    }
    Timer {
        interval: 2000; repeat: true
        running: bars.target !== null && bars.target.visible && bars.Window.active
        onTriggered: bars.run()
    }
}
