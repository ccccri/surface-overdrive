// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// "Sound and EQ": the Sound page of Plasma (devices and volumes) and our tuning (boost, equaliser, microphone, volume buttons).
Kirigami.Page {
    id: wrapper

    title: kcm.name
    padding: 0
    property int tab: kcm.startTab === "tuning" ? 1 : 0
    onTabChanged: kcm.showStockButtons(tab === 0)
    Component.onCompleted: { kcm.showStockButtons(tab === 0); kcm.loadStock("kcm_pulseaudio") }

    header: QQC2.Control {
        padding: Kirigami.Units.largeSpacing
        bottomPadding: Kirigami.Units.smallSpacing
        contentItem: RowLayout {
            spacing: Kirigami.Units.smallSpacing
            Repeater {
                model: [{ t: i18n("Devices and volume"), i: "audio-volume-high" }, { t: i18n("Tuning"), i: "view-media-equalizer" }]
                delegate: QQC2.Button {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1          // equal halves whatever the text
                    text: modelData.t
                    icon.name: modelData.i
                    checkable: true
                    autoExclusive: true
                    checked: wrapper.tab === index
                    highlighted: checked
                    onClicked: wrapper.tab = index
                }
            }
        }
    }

    // Two plain items instead of a StackLayout: a layout would feed the size hints of the pages back into them, which never settles
    // with some Plasma pages.
    Item {
        anchors.fill: parent

        // the page that ships with Plasma, shown as it is
        Item {
            id: holder
            anchors.fill: parent
            visible: wrapper.tab === 0
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
        Tuning { anchors.fill: parent; visible: wrapper.tab === 1 }
    }
}
