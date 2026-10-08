// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// "Sound and EQ": the Sound page of Plasma and our tuning (boost, equaliser, microphone, volume buttons) as two tabs.
Kirigami.Page {
    id: wrapper

    title: kcm.name
    padding: 0
    Component.onCompleted: { kcm.showStockButtons(bar.currentIndex === 0); kcm.loadStock("kcm_pulseaudio") }

    header: QQC2.TabBar {
        id: bar
        onCurrentIndexChanged: kcm.showStockButtons(currentIndex === 0)
        currentIndex: kcm.startTab === "tuning" ? 1 : 0
        QQC2.TabButton { text: i18n("Sound"); icon.name: "preferences-desktop-sound" }
        QQC2.TabButton { text: i18n("Tuning"); icon.name: "view-media-equalizer" }
    }

    // Two plain items instead of a StackLayout: a layout would feed the size hints of the pages back into them, which never settles
    // with some Plasma pages.
    Item {
        anchors.fill: parent

        // the page that ships with Plasma, shown as it is
        Item {
            id: holder
            anchors.fill: parent
            visible: bar.currentIndex === 0
            readonly property Item page: kcm.stockPage
            onPageChanged: if (page) { page.parent = holder; page.anchors.fill = holder; page.visible = true }
            Kirigami.PlaceholderMessage {
                anchors.centerIn: parent
                width: parent.width - Kirigami.Units.gridUnit * 4
                visible: kcm.stockError.length > 0
                icon.name: "dialog-warning"
                text: i18n("This page could not be loaded")
                explanation: kcm.stockError
            }
        }
        Tuning { anchors.fill: parent; visible: bar.currentIndex === 1 }
    }
}
