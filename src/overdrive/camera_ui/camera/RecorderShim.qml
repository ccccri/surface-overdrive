// SPDX-FileCopyrightText: 2026 Surface Overdrive
// SPDX-License-Identifier: GPL-2.0-or-later
//
// The few parts of QtMultimedia's MediaRecorder that Plasma Camera's QML reads: the recording time and the file of the
// last video. The recording itself is the backend's (GStreamer, VA-API H.264).
import QtQuick

QtObject {
    id: root

    property real duration: 0                 // milliseconds
    property string actualLocation: ""        // file URL of the last video
    signal recorderStateChanged()

    property real started: 0
    property Timer clock: Timer {
        interval: 200
        repeat: true
        running: backend.recording
        onRunningChanged: {
            if (running) {
                root.started = Date.now();
                root.duration = 0;
            }
        }
        onTriggered: root.duration = Date.now() - root.started
    }
}
