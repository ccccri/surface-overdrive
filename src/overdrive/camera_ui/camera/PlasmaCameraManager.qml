// SPDX-FileCopyrightText: 2026 Surface Overdrive
// SPDX-License-Identifier: GPL-2.0-or-later
//
// Stands in for Plasma Camera's PlasmaCameraManager (C++): photos, videos and their files, on the Surface Overdrive
// backend (cameraapp.py). Photos keep the screen flash of the front camera: the light frame of CameraPage is lit for a
// moment ("flashing") before the shot.
import QtQuick

QtObject {
    id: root

    property var plasmaCamera
    property var videoSink
    property var recorder: RecorderShim {}

    readonly property bool readyForCapture: backend.key !== "" && !root.flashing
    readonly property bool isRecordingVideo: backend.recording
    property bool isSavingVideo: false
    property bool audioRecordingEnabled: backend.audio
    onAudioRecordingEnabledChanged: backend.setAudio(audioRecordingEnabled)
    readonly property string errorString: ""

    // the light frame lit for a flash photo
    property bool flashing: false

    signal errorOccurred()
    signal framesDropped()
    signal imageSaved(int id, string fileName)

    function captureImageToFile(fileName) {
        if (backend.flashWanted()) {
            root.flashing = true;
            backend.flashOn();
            flashTimer.restart();
            return;
        }
        backend.takePhoto();
    }
    function startRecordingVideo() {
        if (!backend.recording)
            backend.toggleRecording();
    }
    function stopRecordingVideo() {
        if (backend.recording) {
            root.isSavingVideo = true;
            backend.toggleRecording();
        }
    }

    // a moment for the exposure to take in the light, then the photo
    property Timer flashTimer: Timer {
        interval: 600
        onTriggered: { backend.takePhoto(); flashEnd.restart(); }
    }
    property Timer flashEnd: Timer {
        interval: 250
        onTriggered: { root.flashing = false; backend.flashOff(); }
    }

    property Connections backendLink: Connections {
        target: backend
        function onCapturesChanged() {
            const url = backend.lastCapture;
            if (url === "")
                return;
            const path = url.replace(/^file:\/\//, "");
            if (backend.lastIsVideo) {
                root.recorder.actualLocation = url;
                root.isSavingVideo = false;
                root.recorder.recorderStateChanged();
            } else {
                root.imageSaved(0, path);
            }
        }
        function onChanged() {
            if (!backend.recording && root.isSavingVideo)
                Qt.callLater(() => { if (!backend.recording) root.isSavingVideo = false; });
        }
    }
}
