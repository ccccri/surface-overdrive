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

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

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
    }
}
