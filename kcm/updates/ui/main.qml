// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// "Software Update": first the state of what the system image adds for the Surface (kernel patches, modules and the other fixes),
// which is what one comes to look at; under it the page of Plasma, which only holds how and how often updates are fetched.
Kirigami.Page {
    id: wrapper

    title: kcm.name
    padding: 0
    // A page that the Plasma page opens on top of itself takes the whole view with a way back, as it does in Plasma.
    Kirigami.ColumnView.fillWidth: true
    Component.onCompleted: kcm.loadStock("kcm_updates")
    actions: [
        Kirigami.Action {
            text: i18n("Check Again")
            icon.name: "view-refresh"
            enabled: !kcm.busy
            onTriggered: kcm.refresh()
        }
    ]

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        QQC2.ScrollView {
            id: scroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: availableWidth
            QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
            Health { width: scroll.availableWidth }
        }
        Kirigami.ListSectionHeader {
            Layout.fillWidth: true
            visible: kcm.stockPage !== null
            text: i18n("Updates")
        }
        Item {
            id: holder
            Layout.fillWidth: true
            // the page of Plasma is a short form: it gets the height of its content, at most half of the page
            Layout.preferredHeight: !page ? (kcm.stockError.length > 0 ? Kirigami.Units.gridUnit * 6 : 0)
                                    : Math.min(wrapper.height * 0.5, (page.flickable ? page.flickable.contentHeight : Kirigami.Units.gridUnit * 8) + Kirigami.Units.largeSpacing * 2)
            readonly property Item page: kcm.stockPage
            onPageChanged: if (page) { page.parent = holder; page.anchors.fill = holder; page.visible = true }
            QQC2.Label {
                anchors.centerIn: parent
                width: parent.width - Kirigami.Units.gridUnit * 4
                visible: kcm.stockError.length > 0
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                opacity: 0.7
                text: i18n("The update settings of Plasma could not be loaded: %1", kcm.stockError)
            }
        }
    }
}
