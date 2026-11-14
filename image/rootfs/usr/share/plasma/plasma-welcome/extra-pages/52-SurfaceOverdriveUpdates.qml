// Surface Overdrive: how it keeps working, and where to look when it does not (Plasma's Welcome Center, third page).
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

import org.kde.plasma.welcome

Page {
    id: root
    heading: "It keeps working by itself"
    description: "A new image is built every day from Fedora's own and reaches the tablet as a normal update. After each one, a health check makes sure every fix still works, and tells you if one does not."

    topContent: [
        Kirigami.UrlButton {
            Layout.topMargin: Kirigami.Units.largeSpacing
            text: "Report a problem"
            url: "https://github.com/ccccri/surface-overdrive/issues"
        }
    ]

    ColumnLayout {
        anchors.fill: parent
        spacing: Kirigami.Units.largeSpacing

        Repeater {
            model: [
                ["system-software-update", "Software Update", "The fixes and their state, the images with a way back to the previous one, what changed between two images, and the export of all your Surface settings.", "systemsettings kcm_overdrive_updates", "Open"],
                ["help-about", "About this System", "The tablet's firmware, and its light and motion sensors live.", "systemsettings kcm_overdrive_about", "Open"],
                ["utilities-terminal", "In a terminal", "overdrivectl status shows the health check with an explanation for each fix.", "konsole --noclose -e overdrivectl status", "Run it"]
            ]
            delegate: RowLayout {
                required property var modelData
                Layout.fillWidth: true
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: modelData[0]
                    fallback: "preferences-system"
                    Layout.preferredWidth: Kirigami.Units.iconSizes.large
                    Layout.preferredHeight: Kirigami.Units.iconSizes.large
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Kirigami.Heading { level: 4; text: modelData[1]; Layout.fillWidth: true }
                    QQC2.Label { text: modelData[2]; wrapMode: Text.WordWrap; opacity: 0.8; Layout.fillWidth: true }
                }
                QQC2.Button {
                    text: modelData[4]
                    onClicked: Controller.runCommand(modelData[3])
                }
            }
        }
        Item { Layout.fillHeight: true }
    }
}
