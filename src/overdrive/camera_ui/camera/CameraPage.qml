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


Kirigami.Page {
    id: root

    title: qsTr("Camera")
    leftPadding: 0
    rightPadding: 0
    bottomPadding: 0
    topPadding: 0

    globalToolBarStyle: Kirigami.ApplicationHeaderStyle.None

    required property PlasmaCamera camera

    enum CaptureMode {
        Photo,
        Video
    }

    // The current mode of capturing the camera is going to do
    property int captureMode: CameraPage.CaptureMode.Photo

    property PlasmaCameraManager captureSession: PlasmaCameraManager {
        id: captureSession
        plasmaCamera: root.camera
        videoSink: viewfinder.videoSink

        onErrorOccurred: {
            showPassiveNotification(qsTr("An error occurred: \"%1\". Please consider restarting the application if it stopped working.").arg(captureSession.errorString))
        }
        onFramesDropped: {
            showPassiveNotification(qsTr("The video encoder is struggling to keep up. Try lowering your recording settings to improve performance."));
        }
    }

    property CaptureController captureController: CaptureController {
        id: captureController

        camera: root.camera
        captureSession: root.captureSession
        captureMode: root.captureMode
    }

    // These actions are used for functional purposes, but are not actually visible
    actions: [
        Kirigami.Action {
            id: switchModeAction

            visible: false
            text: qsTr("Switch mode")
            icon.color: "transparent"
            icon.name: {
                if (root.captureMode === CameraPage.CaptureMode.Photo)
                    return "emblem-videos-symbolic";
                else if (root.captureMode === CameraPage.CaptureMode.Video)
                    return "camera-photo-symbolic";
            }
            enabled: true
            onTriggered: {
                if (root.captureMode === CameraPage.CaptureMode.Photo)
                    root.captureMode = CameraPage.CaptureMode.Video;
                else
                    root.captureMode = CameraPage.CaptureMode.Photo;
            }
        },
        Kirigami.Action {
            id: captureAction

            visible: false
            text: root.captureController.intendedText
            icon.color: "transparent"
            icon.name: root.captureController.intendedIcon
            onTriggered: root.captureController.requestCapture()

            enabled: !camera.busy
                && !root.captureController.captureTimerRunning
                && !root.captureSession.isSavingVideo
        },
        Kirigami.Action {
            id: switchCameraAction

            visible: false
            text: qsTr("Switch Camera")
            icon.color: "transparent"
            icon.name: "camera-photo-symbolic"
            enabled: !root.camera.busy && root.camera.cameraDeviceIds.length > 1

            onTriggered: root.camera.switchToNextCamera();
        }
    ]

    // Surface Overdrive: the screen light. A warm white frame round everything and the picture inside it, with the
    // backlight at its brightest (cameraapp.py); a flash photo lights it for a moment.
    readonly property bool lit: backend.light || captureSession.flashing
    property real ring: lit ? Math.round(Math.min(width, height) * 0.085) : 0
    Behavior on ring { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
    Rectangle {
        anchors.fill: parent
        color: "#fff1df"
        visible: root.ring > 0
    }

    Viewfinder {
        id: viewfinder
        anchors.fill: parent
        anchors.margins: root.ring

        camera: root.camera
        bottomMargin: controlContainer.height

        // Header controls
        CameraExtraControls {
            id: cameraExtraControls
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right

            audioRecordingEnabled: root.captureSession.audioRecordingEnabled
            audioRecordingEnabledShown: root.captureMode === CameraPage.CaptureMode.Video && !root.captureSession.isRecordingVideo && !root.captureSession.isSavingVideo
            exposureValueEnabled: root.camera.exposureValueAvailable
            photoMode: root.captureMode === CameraPage.CaptureMode.Photo

            onExposureValueRequested: (value) => root.camera.exposureValue = value;
            onAudioEnabledChangeRequested: (enabled) => root.captureSession.audioRecordingEnabled = enabled;
        }

        // Footer controls
        CameraControls {
            id: controlContainer
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right

            captureSession: root.captureSession
            captureController: root.captureController

            captureMode: root.captureMode
            captureEnabled: captureAction.enabled
            switchCameraEnabled: switchCameraAction.enabled
            timerButtonEnabled: !root.camera.busy

            onCaptureButtonClicked: captureAction.triggered()
            onSwitchCameraRequested: switchCameraAction.triggered()
            onTimerDurationRequested: (duration) => {
                root.captureController.captureTimerDuration = duration;
            }
            onSwitchCaptureModeRequested: (captureMode) => {
                root.captureMode = captureMode;
            }
        }

        // Indicator for timer
        ViewfinderTimerOverlay {
            id: timerOverlay
            anchors.fill: parent

            captureMode: root.captureMode
            captureController: root.captureController
        }

        // Video recording duration overlay
        ViewfinderVideoDurationOverlay {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: controlContainer.height + Kirigami.Units.largeSpacing

            visible: root.captureSession.isRecordingVideo
            duration: root.captureSession.recorder.duration
        }
    }

    // Surface Overdrive: night mode collecting its frames, then merging them
    Rectangle {
        anchors.centerIn: parent
        visible: backend.busy !== ""
        radius: height / 2
        color: Qt.rgba(0, 0, 0, 0.6)
        width: busyLabel.implicitWidth + Kirigami.Units.gridUnit * 2
        height: busyLabel.implicitHeight + Kirigami.Units.gridUnit
        QQC2.Label {
            id: busyLabel
            anchors.centerIn: parent
            color: "white"
            text: backend.busy === "Hold still" ? qsTr("Hold still") : qsTr("Processing...")
        }
    }
}
