// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// The kernel patches, modules and other fixes that come with the system image: one line each with its state; a tap on a line opens
// what it does and what to do when it is not working.
ColumnLayout {
    id: root

    Layout.fillWidth: true
    spacing: 0

    property var status: ({ overall: "na", checks: [], settings: {} })
    readonly property bool troubled: status.overall === "warn" || status.overall === "fail"

    function parse() {
        try {
            const parsed = JSON.parse(kcm.statusJson)
            root.status = parsed && parsed.checks ? parsed : { overall: "na", checks: [], settings: {} }
        } catch (e) {
            root.status = { overall: "na", checks: [], settings: {} }
        }
    }
    Component.onCompleted: parse()
    Connections {
        target: kcm
        function onStatusChanged() { root.parse() }
    }

    Kirigami.ListSectionHeader {
        Layout.fillWidth: true
        text: i18n("Kernel Patches and Modules")
    }
    Kirigami.InlineMessage {
        Layout.fillWidth: true
        Layout.margins: Kirigami.Units.largeSpacing
        Layout.topMargin: 0
        visible: root.troubled
        type: root.status.overall === "fail" ? Kirigami.MessageType.Error : Kirigami.MessageType.Warning
        text: root.status.overall === "fail" ? i18n("Something does not work. The lines marked below say what, and what to do.")
                                             : i18n("Something needs attention. The lines marked below say what, and what to do.")
    }
    QQC2.Label {
        Layout.fillWidth: true
        Layout.margins: Kirigami.Units.largeSpacing
        visible: root.status.checks.length === 0
        opacity: 0.7
        text: kcm.busy ? i18n("Checking…") : i18n("The state of the fixes could not be read.")
    }

    Repeater {
        model: root.status.checks

        delegate: QQC2.ItemDelegate {
            id: line
            Layout.fillWidth: true
            readonly property var item: modelData
            property bool expanded: false
            onClicked: expanded = !expanded
            // a line that is not working opens by itself: its remedy is what the user came for
            Component.onCompleted: expanded = item.status === "fail"

            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Icon {
                        Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
                        Layout.preferredHeight: Kirigami.Units.iconSizes.smallMedium
                        source: line.item.status === "ok" ? "emblem-ok-symbolic"
                              : line.item.status === "warn" ? "data-warning"
                              : line.item.status === "fail" ? "data-error"
                              : "emblem-question-symbolic"
                    }
                    QQC2.Label { text: line.item.title; elide: Text.ElideRight; Layout.maximumWidth: line.width * 0.5 }
                    QQC2.Label { Layout.fillWidth: true; text: line.item.detail; elide: Text.ElideRight; opacity: 0.7; horizontalAlignment: Text.AlignRight }
                    Kirigami.Icon {
                        Layout.preferredWidth: Kirigami.Units.iconSizes.small
                        Layout.preferredHeight: Kirigami.Units.iconSizes.small
                        source: line.expanded ? "arrow-up" : "arrow-down"
                        opacity: 0.6
                    }
                }
                Repeater {
                    model: line.expanded ? [line.item.detail, line.item.what, line.item.how, line.item.fix] : []
                    delegate: QQC2.Label {
                        Layout.fillWidth: true
                        Layout.leftMargin: Kirigami.Units.iconSizes.smallMedium + Kirigami.Units.largeSpacing
                        visible: text.length > 0
                        text: modelData || ""
                        wrapMode: Text.WordWrap
                        opacity: index === 0 ? 1 : 0.8
                    }
                }
            }
        }
    }
}
