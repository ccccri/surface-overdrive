// SPDX-License-Identifier: MIT
import QtQuick
import org.kde.kirigami as Kirigami

// "About this System": the page of Plasma, and next to it what the Surface adds (firmware, light and motion sensors).
StockWithSide {
    id: page
    stock: "kcm_about-distro"
    Sensors { live: page.visible }
}
