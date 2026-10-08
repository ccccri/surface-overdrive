// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// A page of Plasma with a panel of ours next to it: side by side on a wide window, so that nothing needs scrolling to be seen, the
// panel below the page on a narrow one. What is declared inside goes into the panel.
Kirigami.Page {
    id: wrapper

    property string stock                                   // plugin name of the Plasma page, for example "kcm_updates"
    property real sideWidth: Kirigami.Units.gridUnit * 26
    readonly property bool wide: width > Kirigami.Units.gridUnit * 50
    default property alias side: sideColumn.data

    title: kcm.name
    padding: 0
    actions: kcm.stockPage ? kcm.stockPage.actions : []
    signal loaded(Item page)
    Component.onCompleted: kcm.loadStock(stock)

    GridLayout {
        anchors.fill: parent
        columns: wrapper.wide ? 2 : 1
        columnSpacing: 0
        rowSpacing: 0

        Item {
            id: holder
            Layout.fillWidth: true
            Layout.fillHeight: true
            readonly property Item page: kcm.stockPage
            onPageChanged: if (page) { page.parent = holder; page.anchors.fill = holder; page.visible = true; wrapper.loaded(page) }
            Kirigami.PlaceholderMessage {
                anchors.centerIn: parent
                width: parent.width - Kirigami.Units.gridUnit * 4
                visible: kcm.stockError.length > 0
                icon.name: "dialog-warning"
                text: i18n("This page could not be loaded")
                explanation: kcm.stockError
            }
        }
        QQC2.ScrollView {
            id: scroll
            Layout.fillHeight: wrapper.wide
            Layout.fillWidth: !wrapper.wide
            Layout.preferredWidth: wrapper.wide ? wrapper.sideWidth : -1
            Layout.preferredHeight: wrapper.wide ? -1 : wrapper.height * 0.5
            contentWidth: availableWidth
            QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
            QQC2.ScrollBar.vertical.policy: QQC2.ScrollBar.AlwaysOff
            Item {
                width: scroll.availableWidth
                implicitHeight: sideColumn.implicitHeight + 2 * Kirigami.Units.largeSpacing
                ColumnLayout {
                    id: sideColumn
                    x: Kirigami.Units.largeSpacing
                    y: Kirigami.Units.largeSpacing
                    width: parent.width - 2 * Kirigami.Units.largeSpacing
                    spacing: Kirigami.Units.largeSpacing
                }
            }
        }
    }
}
