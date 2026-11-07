// SPDX-FileCopyrightText: 2013 Digia Plc and/or its subsidiary(-ies)
// SPDX-FileCopyrightText: 2018 Jonah Brüchert <jbb@kaidan.im>
// SPDX-FileCopyrightText: 2025 Andrew Wang
// SPDX-FileCopyrightText: 2025 Devin Lin <devin@kde.org>
// SPDX-License-Identifier: BSD-3-Clause

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtMultimedia

import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.components as Components

Rectangle {
    id: root
    required property PlasmaCameraManager captureSession
    required property CaptureController captureController

    required property int captureMode
    required property bool captureEnabled
    required property bool switchCameraEnabled
    required property bool timerButtonEnabled

    signal captureButtonClicked()
    signal switchCameraRequested()
    signal timerDurationRequested(duration: int)
    signal switchCaptureModeRequested(captureMode: int)

    height: controlsLayout.implicitHeight
    color: Qt.rgba(0, 0, 0, 0.3)

    ColumnLayout {
        id: controlsLayout
        width: parent.width

        // Select timer strip
        TimerSelectStrip {
            id: timerSelectStrip
            Layout.fillWidth: true

            shown: false // Set by timerButton

            onTimerDurationRequested: (duration) => {
                root.timerDurationRequested(duration);
            }
        }

        // Main footer controls row
        RowLayout {
            spacing: Kirigami.Units.gridUnit
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignHCenter

            Item {
                Layout.fillWidth: true
            }

            // Surface Overdrive: the folder of the photos and videos taken with the app (the file manager opens it), in
            // place of Plasma Camera's thumbnail of the last one, which opened that single picture
            QQC2.ToolButton {
                id: galleryButton
                implicitWidth: Kirigami.Units.gridUnit * 2.5
                implicitHeight: implicitWidth
                icon.name: "folder-pictures-symbolic"
                icon.color: "white"
                icon.width: Kirigami.Units.gridUnit * 1.6
                icon.height: Kirigami.Units.gridUnit * 1.6
                display: QQC2.ToolButton.IconOnly
                text: qsTr("Open the folder of photos and videos")
                enabled: !root.captureSession.isSavingVideo
                onClicked: backend.openFolder()
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.text: text

                // a video still being written
                QQC2.BusyIndicator {
                    anchors.centerIn: parent
                    running: root.captureSession.isSavingVideo
                    visible: running
                }
            }

            QQC2.ToolButton {
                id: timerButton
                enabled: root.timerButtonEnabled
                icon.name: "clock"
                icon.color: "white"

                Layout.fillWidth: true
                Layout.maximumWidth: height
                onClicked: {
                    timerSelectStrip.shown = !timerSelectStrip.shown;
                }
            }

            // Capture photo/video button
            CaptureButton {
                id: captureButton
                captureMode: root.captureMode
                isRecording: captureController.isRecording
                enabled: root.captureEnabled
                onClicked: root.captureButtonClicked()
            }

            QQC2.ToolButton {
                id: switchCameraButton
                icon.name: "circular-arrow-shape"
                icon.color: "white"

                Layout.fillWidth: true
                Layout.maximumWidth: height

                enabled: root.switchCameraEnabled
                opacity: enabled ? 1 : 0 // use opacity instead of visible, so space is still used
                onClicked: root.switchCameraRequested()
            }

            Item {
                // Surface Overdrive: no settings dialog; kept as a spacer so the shutter stays in the middle
                implicitWidth: 40
                implicitHeight: 40
            }

            Item {
                Layout.fillWidth: true
            }
        }

        Components.RadioSelector {
            id: modeSelector

            Layout.alignment: Qt.AlignHCenter
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.largeSpacing * 3
            Layout.maximumWidth: Kirigami.Units.gridUnit * 10
            consistentWidth: true

            Kirigami.Theme.inherit: false
            Kirigami.Theme.colorSet: Kirigami.Theme.Complementary

            actions: [
                Kirigami.Action {
                    text: qsTr("Photo")
                    icon.name: "camera-photo-symbolic"
                    onTriggered: root.switchCaptureModeRequested(CameraPage.CaptureMode.Photo)
                },
                Kirigami.Action {
                    text: qsTr("Video")
                    icon.name: "emblem-videos-symbolic"
                    onTriggered: root.switchCaptureModeRequested(CameraPage.CaptureMode.Video)
                }
            ]
        }
    }
}