// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// "About this System": the page of Plasma with our sensor readings added at its end, in the same scrolling column.
Kirigami.Page {
    id: wrapper

    title: kcm.name
    padding: 0
    property bool merged: false
    Component.onCompleted: kcm.loadStock("kcm_about-distro")

    // The page of Plasma is a scrolling page with one column of content: put our part at the end of that column. Should a future
    // Plasma build the page differently, our part goes below the page instead, with a scroll bar of its own.
    function merge(page) {
        try {
            // the content sits a few plain wrappers below the scrolling area: go down to the first item that lays out several children
            let item = page.flickable.contentItem
            for (let depth = 0; depth < 8 && item; depth++) {
                if (item.spacing !== undefined && item.children.length >= 2) {
                    sensors.parent = item
                    merged = true
                    return
                }
                item = item.children.length > 0 ? item.children[0] : null
            }
            console.warn("Surface Control: the About page has no column to add the sensors to; showing them below it")
        } catch (e) {
            console.warn("Surface Control: could not add the sensors to the About page:", e)
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Item {
            id: holder
            Layout.fillWidth: true; Layout.fillHeight: true
            readonly property Item page: kcm.stockPage
            onPageChanged: if (page) { page.parent = holder; page.anchors.fill = holder; page.visible = true; wrapper.merge(page) }
            Kirigami.PlaceholderMessage {
                anchors.centerIn: parent
                width: parent.width - Kirigami.Units.gridUnit * 4
                visible: kcm.stockError.length > 0
                icon.name: "dialog-warning"
                text: i18n("This page could not be loaded")
                explanation: kcm.stockError
            }
        }

        Kirigami.Separator { Layout.fillWidth: true; visible: !wrapper.merged }
        QQC2.ScrollView {
            id: below
            visible: !wrapper.merged
            Layout.fillWidth: true
            Layout.preferredHeight: wrapper.height * 0.45
            contentWidth: availableWidth
            Item {
                id: belowContent
                width: below.availableWidth
                implicitHeight: sensors.implicitHeight + 2 * Kirigami.Units.largeSpacing
                Sensors {
                    id: sensors
                    live: wrapper.visible
                    Layout.fillWidth: true          // used once it sits in the column of the Plasma page
                    Layout.maximumWidth: Kirigami.Units.gridUnit * 34
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: Kirigami.Units.largeSpacing
                    x: wrapper.merged ? 0 : Kirigami.Units.largeSpacing
                    y: wrapper.merged ? 0 : Kirigami.Units.largeSpacing
                    width: wrapper.merged ? undefined : belowContent.width - 2 * Kirigami.Units.largeSpacing
                }
            }
        }
    }
}
