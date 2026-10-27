// The window of overdrive-camera (cameraapp.py), laid out like the camera of a phone: the preview fills the window, the
// controls float over its right edge (switch camera at the top, the shutter and the record button in the middle, the
// last photo or video at the bottom), so that nothing takes room from the picture.
import QtQuick
import QtQuick.Controls
import QtQuick.Window
import org.freedesktop.gstreamer.Qt6GLVideoItem

ApplicationWindow {
    id: win
    width: 1200
    height: 800
    visibility: Window.Maximized
    visible: true
    title: "Camera"
    color: "black"

    property string note: ""
    readonly property int bar: 132

    GstGLQt6VideoItem {
        id: view
        anchors.fill: parent
        anchors.rightMargin: win.bar        // the whole picture stays visible, left of the controls
        // the front camera is shown as a mirror, like every selfie camera; photos and videos are not mirrored
        transform: Scale { origin.x: view.width / 2; xScale: camera.mirrored ? -1 : 1 }
        Component.onCompleted: camera.setSink(view)
    }

    // white flash on a photo
    Rectangle {
        id: flash
        anchors.fill: parent
        color: "white"
        opacity: 0
        NumberAnimation on opacity { id: flashAnim; from: 0.7; to: 0; duration: 220; running: false }
    }

    Label {
        anchors.centerIn: parent
        width: parent.width * 0.6
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
        color: "white"
        font.pixelSize: 22
        text: camera.error
        visible: camera.error !== ""
    }

    // resolution, top left
    Label {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: 18
        color: "white"
        opacity: 0.8
        font.pixelSize: 15
        text: camera.size
        style: Text.Outline
        styleColor: "#80000000"
    }

    // recording time, top centre
    Rectangle {
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.topMargin: 18
        radius: height / 2
        color: "#d0d32f2f"
        width: recLabel.implicitWidth + 36
        height: recLabel.implicitHeight + 14
        visible: camera.recording
        Label {
            id: recLabel
            anchors.centerIn: parent
            color: "white"
            font.pixelSize: 20
            font.bold: true
            text: "●  " + clock.text
        }
        Text { id: clock; visible: false; text: "0:00" }
        Timer {
            interval: 250; repeat: true; running: camera.recording; triggeredOnStart: true
            onTriggered: clock.text = camera.elapsed()
        }
    }

    // messages, bottom centre
    Label {
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 24
        anchors.horizontalCenterOffset: -win.bar / 2
        color: "white"
        font.pixelSize: 16
        text: win.note
        visible: win.note !== ""
        background: Rectangle { color: "#b0000000"; radius: 8 }
        padding: 10
    }
    Timer { id: noteTimer; interval: 2500; onTriggered: win.note = "" }
    Connections {
        target: camera
        function onMessage(text) { win.note = text; noteTimer.restart() }
    }

    // the control bar over the right edge
    Rectangle {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: win.bar
        color: "#141414"

        // switch camera
        RoundButton {
            id: switcher
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: 28
            width: 64; height: 64
            enabled: camera.keys.length > 1 && !camera.recording
            opacity: enabled ? 1 : 0.4
            background: Rectangle { radius: width / 2; color: switcher.pressed ? "#60ffffff" : "#30ffffff" }
            icon.name: "exchange-positions-clockwise"
            icon.color: "white"
            icon.width: 30; icon.height: 30
            onClicked: camera.next()
        }

        // shutter: a white disc in a ring
        Item {
            id: shutter
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: -56
            width: 86; height: 86
            enabled: camera.key !== "" && camera.error === ""
            opacity: enabled ? 1 : 0.4
            Rectangle { anchors.fill: parent; radius: width / 2; color: "transparent"; border.color: "white"; border.width: 4 }
            Rectangle {
                anchors.centerIn: parent
                width: shutterTap.pressed ? 62 : 70; height: width; radius: width / 2
                color: "white"
                Behavior on width { NumberAnimation { duration: 80 } }
            }
            TapHandler { id: shutterTap; onTapped: { flashAnim.restart(); camera.takePhoto() } }
        }

        // record: a red dot in a ring, a red square while recording
        Item {
            id: record
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: shutter.bottom
            anchors.topMargin: 28
            width: 70; height: 70
            enabled: camera.key !== "" && camera.error === ""
            opacity: enabled ? 1 : 0.4
            Rectangle { anchors.fill: parent; radius: width / 2; color: "transparent"; border.color: "white"; border.width: 3 }
            Rectangle {
                anchors.centerIn: parent
                width: camera.recording ? 26 : 50; height: width
                radius: camera.recording ? 5 : width / 2
                color: "#e53935"
                Behavior on width { NumberAnimation { duration: 120 } }
                Behavior on radius { NumberAnimation { duration: 120 } }
            }
            TapHandler { onTapped: camera.toggleRecording() }
        }

        // the last photo or video: tap to open it
        Rectangle {
            id: thumb
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 28
            width: 64; height: 64
            radius: 10
            color: "#30ffffff"
            border.color: "white"
            border.width: 2
            clip: true
            visible: camera.lastCapture !== ""
            Image {
                anchors.fill: parent
                anchors.margins: 2
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                sourceSize.width: 128
                source: camera.lastIsVideo ? "" : camera.lastCapture
                visible: !camera.lastIsVideo
            }
            Label {
                anchors.centerIn: parent
                text: "\u25B6"
                color: "white"
                font.pixelSize: 26
                visible: camera.lastIsVideo
            }
            TapHandler { onTapped: camera.openLast() }
        }
    }
}
