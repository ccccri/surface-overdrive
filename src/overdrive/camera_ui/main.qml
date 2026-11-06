// SPDX-FileCopyrightText: 2025 Andrew Wang
// SPDX-FileCopyrightText: 2018 Jonah Brüchert <jbb@kaidan.im>
// SPDX-FileCopyrightText: 2013 Digia Plc and/or its subsidiary(-ies)
// SPDX-License-Identifier: BSD-3-Clause

// Surface Overdrive: Plasma Camera's window, without its settings (CameraSettings, SettingsDialog are tied to its own
// backend); the camera is the stand-in of camera/PlasmaCamera.qml on cameraapp.py.

import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls as Controls

import org.kde.kirigami as Kirigami

import "camera"

Kirigami.ApplicationWindow {
    id: root

    minimumWidth: 350
    title: qsTr("Camera")
    visibility: Window.Maximized

    pageStack.columnView.columnResizeMode: Kirigami.ColumnView.SingleColumn
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None
    pageStack.initialPage: CameraPage {
        id: cameraPage
        camera: mainCamera
    }

    function openSettings() {}

    PlasmaCamera {
        id: mainCamera

        onErrorOccurred: {
            showPassiveNotification(qsTr("An error occurred: \"%1\". Please consider restarting the application if it stopped working.").arg(mainCamera.errorString));
        }
    }

    // Surface Overdrive: the backend's messages (video saved, a photo that failed...)
    Connections {
        target: backend
        function onMessage(text) {
            if (text !== "")
                showPassiveNotification(text);
        }
    }
}
