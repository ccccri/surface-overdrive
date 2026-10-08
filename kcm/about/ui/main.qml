// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// "About this System": the page of Plasma, with the firmware version added to its hardware list and the light and motion sensors
// next to it.
StockWithSide {
    id: page
    stock: "kcm_about-distro"

    // The lists of the Plasma page are forms (label on the left, value on the right): the last one is the hardware list, and a label
    // given to it becomes one more line. If that does not work on a future Plasma, the firmware stays in a box with the sensors.
    function forms(item, depth, found) {
        if (!item || depth > 10) return found
        if (String(item).indexOf("FormLayout") >= 0) found.push(item)
        for (let i = 0; item.children && i < item.children.length; i++) forms(item.children[i], depth + 1, found)
        return found
    }
    onLoaded: stockPage => {
        try {
            const found = forms(stockPage.flickable.contentItem, 0, [])
            if (found.length === 0) return
            firmwareLine.createObject(found[found.length - 1])
            sensors.showFirmware = false
        } catch (e) {
            console.warn("Surface Control: could not add the firmware to the hardware list:", e)
        }
    }

    Sensors { id: sensors; live: page.visible }
    Component {
        id: firmwareLine
        QQC2.Label {
            Kirigami.FormData.label: i18n("Firmware Version:")
            visible: text.length > 0
            text: sensors.s.device.firmware ? sensors.s.device.firmware + " (" + (sensors.s.device.firmware_date || "") + ")" : ""
        }
    }
}
