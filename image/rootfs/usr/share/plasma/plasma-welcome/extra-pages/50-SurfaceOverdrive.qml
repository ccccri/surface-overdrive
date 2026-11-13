// Surface Overdrive: the first page of its introduction in Plasma's Welcome Center. Shown once after the switch to the
// image (overdrive-welcome) and from "Surface Overdrive Tour" in the application menu, and after Plasma's own pages on a
// user's first login.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

import org.kde.plasma.welcome

Page {
    id: root
    heading: "Welcome to Surface Overdrive"
    description: "This Fedora Kinoite runs the Surface Overdrive image: the fixes and extras that make the Surface Go a complete tablet, kept working through every update without you rebuilding anything. Updates come by themselves, like the rest of Fedora."

    topContent: [
        Kirigami.UrlButton {
            Layout.topMargin: Kirigami.Units.largeSpacing
            text: "The project on GitHub"
            url: "https://github.com/ccccri/surface-overdrive"
        },
        Kirigami.UrlButton {
            text: "Everything it does, and what is still open"
            url: "https://github.com/ccccri/surface-overdrive/blob/main/docs/FEATURES.md"
        },
        Kirigami.UrlButton {
            text: "What changed lately"
            url: "https://github.com/ccccri/surface-overdrive/blob/main/docs/CHANGELOG.md"
        }
    ]

    ColumnLayout {
        anchors.fill: parent
        spacing: Kirigami.Units.largeSpacing

        Repeater {
            model: [
                ["overdrive-camera", "Both cameras", "Our own tuning and calibration, a camera app with photos and videos, and every app and browser can use them"],
                ["preferences-desktop-sound", "Sound", "Louder speakers, an equalizer for every output and a microphone that filters out the noise"],
                ["preferences-desktop-tablet", "Pen and touch", "Pressure and tilt, no fake battery, on-screen keyboard for passwords, swipe up for the launcher"],
                ["preferences-desktop-user-password", "PIN or pattern", "Unlock the screen and log in with a PIN or a 9-dot pattern, next to the password"],
                ["overdrive-nfc", "NFC and sensors", "Tags read and shown, light and motion sensors, volume buttons that repeat"]
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
            }
        }
        Item { Layout.fillHeight: true }
    }
}
