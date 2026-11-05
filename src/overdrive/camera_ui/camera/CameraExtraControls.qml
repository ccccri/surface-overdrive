// SPDX-FileCopyrightText: 2025 Devin Lin <devin@kde.org>
// SPDX-License-Identifier: GPL-2.0-or-later

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtMultimedia

import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.components as Components

Rectangle {
    id: root

    required property bool audioRecordingEnabled
    required property bool audioRecordingEnabledShown
    required property bool exposureValueEnabled
    // Surface Overdrive: photo mode (the flash and night mode are for photos)
    property bool photoMode: true
    signal audioEnabledChangeRequested(enabled: bool)
    signal exposureValueRequested(value: real)

    height: controlsLayout.implicitHeight
    color: Qt.rgba(0, 0, 0, 0.3)

    ColumnLayout {
        id: controlsLayout
        spacing: Kirigami.Units.smallSpacing
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top

        Kirigami.Theme.inherit: false
        Kirigami.Theme.colorSet: Kirigami.Theme.Complementary

        RowLayout {
            id: controlsRow

            spacing: Kirigami.Units.largeSpacing
            Layout.fillWidth: true
            Layout.topMargin: Kirigami.Units.largeSpacing
            Layout.bottomMargin: Kirigami.Units.largeSpacing

            Item { Layout.fillWidth: true }
            // Surface Overdrive: the screen as a light round the picture
            QQC2.ToolButton {
                icon.name: backend.light ? "flashlight-on" : "flashlight-off"
                icon.color: backend.light ? Kirigami.Theme.highlightColor : "white"
                text: backend.light ? qsTr("Screen light is on") : qsTr("Screen light is off")
                display: QQC2.ToolButton.IconOnly
                onClicked: backend.toggleLight()
                QQC2.ToolTip.visible: down
                QQC2.ToolTip.text: text
            }
            // Surface Overdrive: the screen as the flash of front photos (auto: in the dark)
            QQC2.ToolButton {
                visible: backend.key === "front" && root.photoMode
                icon.source: Qt.resolvedUrl("../icons/flash.svg")
                icon.color: backend.flashMode === "off" ? "white" : Kirigami.Theme.highlightColor
                text: backend.flashMode === "auto" ? qsTr("Flash: auto") : backend.flashMode === "on" ? qsTr("Flash: on") : qsTr("Flash: off")
                display: QQC2.ToolButton.TextBesideIcon
                onClicked: backend.cycleFlash()
            }
            // Surface Overdrive: night mode, on by itself in the dark; a tap turns it off for now
            QQC2.ToolButton {
                visible: backend.dark && root.photoMode
                icon.name: "weather-clear-night"
                icon.color: backend.night ? Kirigami.Theme.highlightColor : "white"
                text: backend.night ? qsTr("Night mode") : qsTr("Night mode off")
                display: QQC2.ToolButton.TextBesideIcon
                onClicked: backend.toggleNight()
            }
            QQC2.ToolButton {
                id: audioRecordingButton
                icon.name: root.audioRecordingEnabled ? 'microphone-sensitivity-high-symbolic' : 'microphone-sensitivity-muted-symbolic'
                icon.color: 'white'
                text: root.audioRecordingEnabled ? qsTr("Microphone is enabled") : qsTr("Microphone is disabled")
                display: QQC2.ToolButton.IconOnly
                visible: root.audioRecordingEnabledShown
                onClicked: root.audioEnabledChangeRequested(!root.audioRecordingEnabled)

                QQC2.ToolTip.visible: down
                QQC2.ToolTip.text: text
            }

            // Surface Overdrive: the photo presets (in place of the exposure strip) and the page where they are made
            QQC2.ToolButton {
                id: presetButton
                icon.name: "color-management"
                icon.color: presetSelectStrip.shown ? Kirigami.Theme.highlightColor : "white"
                text: qsTr("Photo preset")
                display: QQC2.ToolButton.IconOnly
                visible: root.exposureValueEnabled
                onClicked: presetSelectStrip.shown = !presetSelectStrip.shown
                QQC2.ToolTip.visible: down
                QQC2.ToolTip.text: text
            }
            QQC2.ToolButton {
                icon.name: "configure"
                icon.color: "white"
                text: qsTr("Embedded Cameras settings")
                display: QQC2.ToolButton.IconOnly
                onClicked: backend.openCameraSettings()
                QQC2.ToolTip.visible: down
                QQC2.ToolTip.text: text
            }

            Item { Layout.fillWidth: true }
        }

        PresetSelectStrip {
            id: presetSelectStrip
            visible: root.exposureValueEnabled
            shown: false // Set by presetButton
            Layout.fillWidth: true
        }
    }
}
