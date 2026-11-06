# The Camera app's window: Plasma Camera's QML

The QML of this folder is Plasma Camera's (https://invent.kde.org/plasma-mobile/plasma-camera, commit
7faa4d51fb38), the KDE camera app, run on the Surface Overdrive backend (cameraapp.py) instead of its own
C++ one. Its files keep their authors and licences (SPDX headers; texts in LICENSES/: BSD-3-Clause, GPL-2.0-or-later,
GPL-3.0-or-later). Because of them the Camera app as a whole is GPL-3.0-or-later; the rest of Surface Overdrive stays
under its MIT licence.

What changed, each marked "Surface Overdrive" in the files:
- camera/PlasmaCamera.qml, camera/PlasmaCameraManager.qml, camera/RecorderShim.qml: stand-ins for Plasma Camera's C++
  types (PlasmaCamera, PlasmaCameraManager, QtMultimedia's MediaRecorder), on the context property "backend".
- camera/Viewfinder.qml: GStreamer's qml6glsink item instead of VideoOutput.
- camera/CameraExtraControls.qml: buttons for the screen light and the front flash.
- camera/CameraPage.qml: the screen light frame.
- camera/CameraControls.qml: the last picture at start; no settings dialog.
- main.qml: without Plasma Camera's settings (CameraSettings, SettingsDialog).
- i18n() calls became qsTr().
