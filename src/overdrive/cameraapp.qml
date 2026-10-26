// The window of overdrive-camera (cameraapp.py): the preview fills it, large touch buttons on the right.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtMultimedia

ApplicationWindow {
    id: win
    width: 1100
    height: 720
    visible: true
    title: "Camera"
    color: "black"

    property string note: ""

    VideoOutput {
        id: view
        anchors.fill: parent
        anchors.rightMargin: bar.width
        fillMode: VideoOutput.PreserveAspectFit
        // the front camera is shown as a mirror, like every selfie camera; photos and videos are not mirrored
        transform: Scale { origin.x: view.width / 2; xScale: camera.mirrored ? -1 : 1 }
        Component.onCompleted: camera.setSink(view.videoSink)
    }

    Rectangle {
        id: flash
        anchors.fill: view
        color: "white"
        opacity: 0
        NumberAnimation on opacity { id: flashAnim; from: 0.8; to: 0; duration: 250; running: false }
    }

    Label {
        anchors.centerIn: view
        width: view.width * 0.8
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
        color: "white"
        font.pixelSize: 20
        text: camera.error
        visible: camera.error !== ""
    }

    Rectangle {
        anchors.top: parent.top
        anchors.horizontalCenter: view.horizontalCenter
        anchors.topMargin: 16
        radius: height / 2
        color: "#c0d32f2f"
        width: recLabel.implicitWidth + 32
        height: recLabel.implicitHeight + 12
        visible: camera.recording
        Label {
            id: recLabel
            anchors.centerIn: parent
            color: "white"
            font.pixelSize: 20
            font.bold: true
            text: "● " + clock.text
        }
        Text { id: clock; visible: false; text: "" }
        Timer {
            interval: 250; repeat: true; running: camera.recording; triggeredOnStart: true
            onTriggered: clock.text = camera.elapsed()
        }
    }

    Label {
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: view.horizontalCenter
        anchors.bottomMargin: 16
        color: "white"
        font.pixelSize: 16
        text: win.note
        visible: win.note !== ""
        background: Rectangle { color: "#a0000000"; radius: 6 }
        padding: 8
    }
    Timer { id: noteTimer; interval: 3000; onTriggered: win.note = "" }
    Connections {
        target: camera
        function onMessage(text) { win.note = text; noteTimer.restart() }
    }

    Rectangle {
        id: bar
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 128
        color: "#202020"

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 24

            RoundButton {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 72; Layout.preferredHeight: 72
                icon.name: "exchange-positions-clockwise"
                icon.width: 36; icon.height: 36
                enabled: camera.keys.length > 1 && !camera.recording
                onClicked: camera.next()
                ToolTip.visible: hovered; ToolTip.text: "Switch camera"
            }
            Label {
                Layout.alignment: Qt.AlignHCenter
                color: "#c0c0c0"
                font.pixelSize: 13
                horizontalAlignment: Text.AlignHCenter
                text: (camera.key === "front" ? "Front" : camera.key === "rear" ? "Rear" : "") + "\n" + camera.size
            }
            Item { Layout.fillHeight: true }

            RoundButton {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 88; Layout.preferredHeight: 88
                icon.name: "camera-photo"
                icon.width: 40; icon.height: 40
                enabled: camera.key !== "" && camera.error === ""
                onClicked: { flashAnim.restart(); camera.takePhoto() }
                ToolTip.visible: hovered; ToolTip.text: "Take a photo"
            }
            RoundButton {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 88; Layout.preferredHeight: 88
                icon.name: camera.recording ? "media-playback-stop" : "media-record"
                icon.color: "#e53935"
                icon.width: 40; icon.height: 40
                enabled: camera.key !== "" && camera.error === ""
                onClicked: camera.toggleRecording()
                ToolTip.visible: hovered; ToolTip.text: camera.recording ? "Stop recording" : "Record a video"
            }
            Item { Layout.fillHeight: true }

            RoundButton {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 64; Layout.preferredHeight: 64
                icon.name: "folder-pictures"
                icon.width: 32; icon.height: 32
                onClicked: camera.openFolder()
                ToolTip.visible: hovered; ToolTip.text: "Open the photos folder"
            }
            RoundButton {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 64; Layout.preferredHeight: 64
                icon.name: "folder-videos"
                icon.width: 32; icon.height: 32
                onClicked: camera.openVideos()
                ToolTip.visible: hovered; ToolTip.text: "Open the videos folder"
            }
        }
    }
}
