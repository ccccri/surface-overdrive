// Surface Overdrive: the settings of the image, one button away (Plasma's Welcome Center, second page).
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

import org.kde.plasma.welcome

Page {
    id: root
    heading: "Make it yours"
    description: "Everything Surface Overdrive adds lives in System Settings, next to Plasma's own pages. A few to start with:"

    QQC2.ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth

        ColumnLayout {
            width: parent.width
            spacing: Kirigami.Units.largeSpacing

            Repeater {
                model: [
                    ["preferences-desktop-user-password", "Unlock with a PIN or a pattern", "Screen Locking: choose a PIN or draw a pattern, for the lock screen and the login screen.", "systemsettings kcm_overdrive_screenlock", "Set up"],
                    ["overdrive-camera", "Cameras", "Live preview, presets and fine tuning of both cameras.", "systemsettings kcm_overdrive_cameras", "Open"],
                    ["camera-photo", "Camera app", "Photos and videos with the graphics chip's encoder, a gallery, a timer and a grid.", "overdrive-camera", "Start"],
                    ["preferences-desktop-sound", "Sound and EQ", "Speaker boost, equalizer presets per output, microphone noise filter.", "systemsettings kcm_overdrive_sound", "Open"],
                    ["preferences-desktop-tablet", "Pen", "Pen buttons and pressure, with a test area to try them.", "systemsettings kcm_overdrive_tablet", "Open"],
                    ["overdrive-nfc", "NFC", "Hold a tag to the back of the tablet and see what it says.", "systemsettings kcm_overdrive_nfc", "Open"]
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
        }
    }
}
