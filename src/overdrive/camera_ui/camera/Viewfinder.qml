// SPDX-FileCopyrightText: 2013 Digia Plc and/or its subsidiary(-ies)
// SPDX-FileCopyrightText: 2018 Jonah Brüchert <jbb@kaidan.im>
// SPDX-FileCopyrightText: 2025 Andrew Wang
// SPDX-FileCopyrightText: 2025 Devin Lin <devin@kde.org>
// SPDX-License-Identifier: BSD-3-Clause

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.freedesktop.gstreamer.Qt6GLVideoItem
import org.kde.kirigami as Kirigami

Rectangle {
    id: root

    required property PlasmaCamera camera
    property real bottomMargin: 0

    // Surface Overdrive: frames come from GStreamer (cameraapp.py), not from a QVideoSink
    property var videoSink: null
    color: "black"

    Kirigami.Heading {
        anchors.centerIn: parent
        wrapMode: Text.WordWrap
        text: root.camera.available ? "" : qsTr("Camera not available")
    }

    GstGLQt6VideoItem {
        id: viewfinder
        visible: root.camera.available
        width: parent.width
        height: parent.height
        forceAspectRatio: true
        // the front camera is shown as a mirror, like every selfie camera; photos and videos are not mirrored
        transform: Scale { origin.x: viewfinder.width / 2; xScale: backend.mirrored ? -1 : 1 }
        Component.onCompleted: backend.setSink(viewfinder)
    }
}