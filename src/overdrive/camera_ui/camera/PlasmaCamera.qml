// SPDX-FileCopyrightText: 2026 Surface Overdrive
// SPDX-License-Identifier: GPL-2.0-or-later
//
// Stands in for Plasma Camera's PlasmaCamera (C++, libcamera) so that its QML runs unchanged on the Surface Overdrive
// camera backend (cameraapp.py, the context property "backend": PipeWire, the patched libcamera of the image).
import QtQuick

QtObject {
    id: root

    readonly property bool available: backend.key !== "" && backend.error === ""
    readonly property bool busy: backend.busy !== "" || backend.applyingSize
    readonly property var cameraDeviceIds: backend.keys
    readonly property var cameraDeviceNames: backend.labels
    readonly property string cameraDevice: backend.key
    readonly property bool error: backend.error !== "" && backend.error.indexOf("Looking") !== 0
    readonly property string errorString: backend.error

    // the exposure compensation of the live profile (EV), the same as the Cameras page of System Settings
    readonly property bool exposureValueAvailable: backend.key === "front" || backend.key === "rear"
    property real exposureValue: 0
    onExposureValueChanged: backend.setSetting("exposure", exposureValue)

    signal errorOccurred()

    function switchToNextCamera() {
        backend.next();
        return true;
    }
    function startCamera() {}
    function stopCamera() {}
}
