// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kcmutils as KCM
import org.kde.kirigami as Kirigami

KCM.SimpleKCM {
    id: root

    property var status: ({ overall: "na", checks: [], settings: {} })

    function parse() {
        try {
            root.status = JSON.parse(kcm.statusJson)
        } catch (e) {
            root.status = { overall: "na", checks: [], settings: {} }
        }
    }
    Component.onCompleted: parse()
    Connections {
        target: kcm
        function onStatusChanged() { root.parse() }
    }

    readonly property var statusText: ({
        ok: i18n("Everything works"),
        warn: i18n("Something needs attention"),
        fail: i18n("Something does not work"),
        na: i18n("Checking...")
    })
    readonly property var statusType: ({
        ok: Kirigami.MessageType.Positive,
        warn: Kirigami.MessageType.Warning,
        fail: Kirigami.MessageType.Error,
        na: Kirigami.MessageType.Information
    })

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: true
            type: root.statusType[root.status.overall] ?? Kirigami.MessageType.Information
            text: root.statusText[root.status.overall] ?? ""
            actions: [
                Kirigami.Action {
                    text: i18n("Check again")
                    icon.name: "view-refresh"
                    enabled: !kcm.busy
                    onTriggered: kcm.refresh()
                }
            ]
        }

        Kirigami.FormLayout {
            Layout.fillWidth: true

            QQC2.Switch {
                Kirigami.FormData.label: i18n("Volume buttons:")
                text: i18n("Hold to repeat")
                checked: root.status.settings.volume_hold === "on"
                enabled: root.status.settings.volume_hold !== "unavailable" && !kcm.busy
                onToggled: kcm.changeSetting("volume-hold", checked ? "on" : "off")
            }
            QQC2.Switch {
                Kirigami.FormData.label: i18n("Pen:")
                text: i18n("Hide the fake battery")
                checked: root.status.settings.stylus_filter === "on"
                enabled: !kcm.busy
                onToggled: kcm.changeSetting("stylus-filter", checked ? "on" : "off")
            }
            QQC2.Label {
                visible: root.status.settings.stylus_filter === "off"
                text: i18n("Turning the pen filter off applies after a restart.")
                wrapMode: Text.WordWrap
                opacity: 0.7
            }
        }

        Repeater {
            model: root.status.checks

            delegate: Kirigami.AbstractCard {
                id: card
                Layout.fillWidth: true
                property bool expanded: false
                readonly property var item: modelData

                contentItem: ColumnLayout {
                    spacing: Kirigami.Units.smallSpacing

                    RowLayout {
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
                            Layout.preferredHeight: Kirigami.Units.iconSizes.smallMedium
                            source: card.item.status === "ok" ? "emblem-ok-symbolic"
                                  : card.item.status === "warn" ? "dialog-warning-symbolic"
                                  : card.item.status === "fail" ? "dialog-error-symbolic"
                                  : "emblem-question-symbolic"
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            Kirigami.Heading {
                                level: 4
                                text: card.item.title
                            }
                            QQC2.Label {
                                Layout.fillWidth: true
                                text: card.item.detail
                                wrapMode: Text.WordWrap
                                opacity: 0.7
                            }
                        }
                        QQC2.ToolButton {
                            icon.name: card.expanded ? "arrow-up" : "arrow-down"
                            onClicked: card.expanded = !card.expanded
                            QQC2.ToolTip.text: i18n("Details")
                            QQC2.ToolTip.visible: hovered
                        }
                    }

                    ColumnLayout {
                        visible: card.expanded
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        Repeater {
                            model: [
                                { label: i18n("What it does"), text: card.item.what },
                                { label: i18n("How it works"), text: card.item.how },
                                { label: i18n("What to do when it is not green"), text: card.item.fix }
                            ]
                            delegate: ColumnLayout {
                                Layout.fillWidth: true
                                visible: modelData.text !== ""
                                spacing: 0
                                QQC2.Label {
                                    text: modelData.label
                                    font.bold: true
                                }
                                QQC2.Label {
                                    Layout.fillWidth: true
                                    text: modelData.text
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
