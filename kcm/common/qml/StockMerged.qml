// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// A page of Plasma with our part added at its end, so that it reads as one page. What is declared inside is our part.
//
// The pages of Plasma scroll one column of content: our part becomes the last item of that column. A page that is built differently
// (a single form, or whatever a future Plasma does) is shown at its own height with our part right below it instead.
Kirigami.Page {
    id: wrapper

    property string stock                                   // plugin name of the Plasma page, for example "kcm_pulseaudio"
    property bool merged: false
    signal mergedInto(Item column)                          // our part is now the last item of this column of the Plasma page
    default property alias extra: ours.data

    title: kcm.name
    padding: 0
    // A page that the Plasma page opens on top of itself (its "Configure..." entries) takes the whole view with a way back, as it
    // does in Plasma, instead of squeezing in as a second column: System Settings decides that from this property of the first page.
    Kirigami.ColumnView.fillWidth: true
    // the menu of the Plasma page (top right in the title bar) stays where it was
    actions: kcm.stockPage ? kcm.stockPage.actions : []
    Component.onCompleted: kcm.loadStock(stock)
    Bars { target: wrapper }

    // The content of a Plasma page is a column a few wrappers below the page: the first column layout with several items in it.
    function column(item, depth) {
        if (!item || depth > 8) return null
        if (String(item).indexOf("FormLayout") >= 0) return null          // a form lays its children out as label and field: not for us
        if (String(item).indexOf("ColumnLayout") >= 0 && item.children.length >= 2) return item
        for (let i = 0; item.children && i < item.children.length; i++) {
            const found = column(item.children[i], depth + 1)
            if (found) return found
        }
        return null
    }
    function merge(page) {
        try {
            const target = column(page.flickable ? page.flickable.contentItem : page.contentItem, 0)
            if (target) { ours.parent = target; merged = true; wrapper.mergedInto(target) }
        } catch (e) {
            console.warn("Surface Control: could not add to the page of Plasma, showing our part below it:", e)
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Item {
            id: holder
            Layout.fillWidth: true
            Layout.fillHeight: wrapper.merged
            // not merged: the page of Plasma gets the height of its content (at most half), ours the rest
            Layout.preferredHeight: wrapper.merged || !page ? -1
                                    : Math.min(wrapper.height * 0.5, (page.flickable ? page.flickable.contentHeight : wrapper.height * 0.5) + Kirigami.Units.gridUnit * 2)
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
        QQC2.ScrollView {
            id: below
            visible: !wrapper.merged
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: availableWidth
            QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
            Item {
                id: belowContent
                width: below.availableWidth
                implicitHeight: ours.implicitHeight + 2 * Kirigami.Units.largeSpacing
                ColumnLayout {
                    id: ours
                    // inside the column of the Plasma page the layout places it; below the page it is placed here
                    Layout.fillWidth: true
                    x: wrapper.merged ? 0 : Kirigami.Units.largeSpacing
                    y: wrapper.merged ? 0 : Kirigami.Units.largeSpacing
                    width: wrapper.merged ? implicitWidth : belowContent.width - 2 * Kirigami.Units.largeSpacing
                    spacing: Kirigami.Units.largeSpacing
                }
            }
        }
    }
}
