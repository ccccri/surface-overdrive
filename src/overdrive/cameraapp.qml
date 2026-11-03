// The window of overdrive-camera (cameraapp.py), laid out like the camera of a phone or of Plasma Mobile: the preview
// fills the window and the controls float over it, at the bottom when the tablet stands upright and at the right edge
// when it lies landscape. Photo and video share one shutter (white for a photo, red for a video); the last picture
// opens a gallery inside the app; the settings slide in from the side with the same adjustments as the Cameras page of
// System Settings (they act on the camera while it runs).
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import QtMultimedia
import org.freedesktop.gstreamer.Qt6GLVideoItem

ApplicationWindow {
    id: win
    width: 1200
    height: 800
    visibility: Window.Maximized
    visible: true
    title: "Camera"
    color: "black"

    property string mode: "photo"            // "photo" or "video"
    property int timerSeconds: 0              // 0, 3 or 10 before a photo
    property int countdown: 0
    property bool grid: false
    property string note: ""
    readonly property bool landscape: width >= height
    readonly property real ctl: 64           // size of the round buttons
    readonly property real barSize: landscape ? 150 : 200

    // ---- preview
    GstGLQt6VideoItem {
        id: view
        anchors.fill: parent
        // the front camera is shown as a mirror, like every selfie camera; photos and videos are not mirrored
        transform: Scale { origin.x: view.width / 2; xScale: camera.mirrored ? -1 : 1 }
        Component.onCompleted: camera.setSink(view)
    }

    // rule-of-thirds grid over the preview
    Item {
        anchors.fill: parent
        visible: win.grid
        Repeater {
            model: 2
            Rectangle { x: parent.width * (index + 1) / 3; width: 1; height: parent.height; color: "#80ffffff" }
        }
        Repeater {
            model: 2
            Rectangle { y: parent.height * (index + 1) / 3; height: 1; width: parent.width; color: "#80ffffff" }
        }
    }

    // white flash when a photo is taken
    Rectangle {
        id: flash
        anchors.fill: parent
        color: "white"
        opacity: 0
        NumberAnimation on opacity { id: flashAnim; from: 0.8; to: 0; duration: 250; running: false }
    }

    // countdown of the timer
    Label {
        anchors.centerIn: parent
        visible: win.countdown > 0
        text: win.countdown
        color: "white"
        font.pixelSize: 160
        font.weight: Font.Light
        style: Text.Outline
        styleColor: "#60000000"
    }
    Timer {
        id: countdownTimer
        interval: 1000
        repeat: true
        onTriggered: {
            win.countdown -= 1
            if (win.countdown <= 0) {
                stop()
                win.capturePhoto()
            }
        }
    }

    function capturePhoto() {
        flashAnim.restart()
        camera.takePhoto()
    }
    function shutter() {
        if (win.mode === "video") {
            camera.toggleRecording()
            return
        }
        if (countdownTimer.running) {           // a second tap cancels the countdown
            countdownTimer.stop()
            win.countdown = 0
            return
        }
        if (win.timerSeconds > 0) {
            win.countdown = win.timerSeconds
            countdownTimer.start()
        } else {
            win.capturePhoto()
        }
    }

    // errors and the camera starting
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

    // ---- top: picture size, recording time
    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: 16
        radius: height / 2
        color: "#66000000"
        width: sizeLabel.implicitWidth + 24
        height: sizeLabel.implicitHeight + 12
        Label {
            id: sizeLabel
            anchors.centerIn: parent
            color: "white"
            font.pixelSize: 15
            text: camera.size
        }
    }
    Rectangle {
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.topMargin: 16
        radius: height / 2
        color: "#e0d32f2f"
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

    // messages
    Label {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.horizontalCenterOffset: win.landscape ? -win.barSize / 2 : 0
        anchors.bottom: parent.bottom
        anchors.bottomMargin: (win.landscape ? 0 : win.barSize) + 24
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

    // ---- the control bar: bottom (portrait) or right edge (landscape), translucent over the picture
    component RoundButton2: Button {
        id: rb
        property string iconName
        property bool on: false
        implicitWidth: win.ctl
        implicitHeight: win.ctl
        opacity: enabled ? 1 : 0.35
        icon.name: iconName
        icon.color: "white"
        icon.width: 28
        icon.height: 28
        display: text !== "" ? AbstractButton.TextUnderIcon : AbstractButton.IconOnly
        font.pixelSize: 11
        font.bold: true
        palette.buttonText: "white"
        background: Rectangle {
            radius: width / 2
            color: rb.pressed ? "#70ffffff" : rb.on ? "#50ffffff" : "#30ffffff"
        }
    }

    Rectangle {
        id: bar
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        width: win.landscape ? win.barSize : parent.width
        height: win.landscape ? parent.height : win.barSize
        gradient: Gradient {
            orientation: win.landscape ? Gradient.Horizontal : Gradient.Vertical
            GradientStop { position: 0; color: "#00000000" }
            GradientStop { position: 0.35; color: "#99000000" }
            GradientStop { position: 1; color: "#cc000000" }
        }

        GridLayout {
            anchors.centerIn: parent
            anchors.horizontalCenterOffset: win.landscape ? 12 : 0
            anchors.verticalCenterOffset: win.landscape ? 0 : 12
            flow: win.landscape ? GridLayout.TopToBottom : GridLayout.LeftToRight
            rows: win.landscape ? 7 : 1
            columns: win.landscape ? 1 : 7
            rowSpacing: 22
            columnSpacing: 30

            // the last photo or video: opens the gallery
            AbstractButton {
                id: thumb
                Layout.alignment: Qt.AlignCenter
                implicitWidth: win.ctl
                implicitHeight: win.ctl
                enabled: camera.lastCapture !== ""
                onClicked: gallery.openAt(0)
                background: Rectangle { radius: 12; color: "#30ffffff"; border.color: "white"; border.width: 2 }
                contentItem: Item {
                    clip: true
                    Image {
                        anchors.fill: parent
                        anchors.margins: 3
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        sourceSize.width: 160
                        source: camera.lastCapture !== "" && !camera.lastIsVideo ? camera.lastCapture : ""
                    }
                    Label {
                        anchors.centerIn: parent
                        visible: camera.lastIsVideo
                        text: "▶"
                        color: "white"
                        font.pixelSize: 26
                    }
                }
            }

            RoundButton2 {
                Layout.alignment: Qt.AlignCenter
                iconName: "chronometer"
                visible: win.mode === "photo"
                on: win.timerSeconds > 0
                text: win.timerSeconds > 0 ? win.timerSeconds + "s" : ""
                onClicked: win.timerSeconds = win.timerSeconds === 0 ? 3 : win.timerSeconds === 3 ? 10 : 0
            }
            Item { visible: win.mode !== "photo"; implicitWidth: win.ctl; implicitHeight: win.ctl }

            // the shutter: white disc for a photo, red disc for a video, red square while recording
            AbstractButton {
                id: shutterButton
                Layout.alignment: Qt.AlignCenter
                implicitWidth: 92
                implicitHeight: 92
                enabled: camera.key !== "" && camera.error === "" && !camera.applyingSize
                opacity: enabled ? 1 : 0.4
                onClicked: win.shutter()
                background: Rectangle { radius: width / 2; color: "transparent"; border.color: "white"; border.width: 5 }
                contentItem: Item {
                    Rectangle {
                        anchors.centerIn: parent
                        readonly property bool rec: camera.recording
                        width: rec ? 34 : (shutterButton.pressed ? 66 : 74)
                        height: width
                        radius: rec ? 7 : width / 2
                        color: win.mode === "video" ? "#e53935" : "white"
                        Behavior on width { NumberAnimation { duration: 120 } }
                        Behavior on radius { NumberAnimation { duration: 120 } }
                        Behavior on color { ColorAnimation { duration: 150 } }
                    }
                }
            }

            RoundButton2 {
                Layout.alignment: Qt.AlignCenter
                iconName: "exchange-positions-clockwise"
                enabled: camera.keys.length > 1 && !camera.recording && !camera.applyingSize
                onClicked: camera.next()
            }

            RoundButton2 {
                Layout.alignment: Qt.AlignCenter
                iconName: "configure"
                enabled: !camera.recording
                onClicked: settingsDrawer.open()
            }

            // Photo | Video
            Rectangle {
                Layout.alignment: Qt.AlignCenter
                Layout.columnSpan: 1
                radius: height / 2
                color: "#40ffffff"
                implicitWidth: modes.implicitWidth + 8
                implicitHeight: modes.implicitHeight + 8
                Grid {
                    id: modes
                    anchors.centerIn: parent
                    columns: win.landscape ? 1 : 2
                    spacing: 4
                    Repeater {
                        model: [["photo", "Photo"], ["video", "Video"]]
                        AbstractButton {
                            implicitWidth: 92
                            implicitHeight: 40
                            enabled: !camera.recording
                            onClicked: { win.mode = modelData[0]; countdownTimer.stop(); win.countdown = 0 }
                            background: Rectangle { radius: height / 2; color: win.mode === modelData[0] ? "white" : "transparent" }
                            contentItem: Label {
                                text: modelData[1]
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                font.pixelSize: 16
                                font.bold: true
                                color: win.mode === modelData[0] ? "black" : "white"
                            }
                        }
                    }
                }
            }
        }
    }

    // ---- settings: the adjustments of the Cameras page, for the camera in use
    Drawer {
        id: settingsDrawer
        edge: Qt.RightEdge
        width: Math.min(460, win.width * 0.9)
        height: win.height
        dim: true
        background: Rectangle { color: "#ee1c1c1e" }

        property var data: {
            try { return JSON.parse(camera.settings) } catch (e) { return ({}) }
        }

        ScrollView {
            id: scroller
            anchors.fill: parent
            contentWidth: availableWidth
            clip: true

            ColumnLayout {
                width: scroller.availableWidth
                spacing: 6

                RowLayout {
                    Layout.fillWidth: true
                    Layout.margins: 18
                    Label {
                        Layout.fillWidth: true
                        text: (camera.key === "front" ? "Front" : "Rear") + " camera"
                        color: "white"
                        font.pixelSize: 22
                        font.bold: true
                    }
                    Button {
                        text: "Reset"
                        icon.name: "edit-undo"
                        onClicked: camera.resetSettings()
                    }
                }

                // picture size
                Label { Layout.leftMargin: 18; text: "PICTURE SIZE"; color: "#a0a0a0"; font.pixelSize: 13; font.bold: true }
                ColumnLayout {
                    Layout.leftMargin: 18
                    Layout.rightMargin: 18
                    Layout.fillWidth: true
                    spacing: 4
                    Repeater {
                        model: settingsDrawer.data.sizes || []
                        AbstractButton {
                            Layout.fillWidth: true
                            implicitHeight: 52
                            readonly property bool current: (settingsDrawer.data.values || {}).minWidth === modelData.minWidth
                            enabled: !camera.applyingSize && !current
                            onClicked: camera.setSetting("minWidth", modelData.minWidth)
                            background: Rectangle { radius: 10; color: parent.current ? "#3d7eff" : "#2c2c2e" }
                            contentItem: RowLayout {
                                Label { Layout.leftMargin: 14; text: modelData.text; color: "white"; font.pixelSize: 17; font.bold: true }
                                Label { Layout.fillWidth: true; text: modelData.desc; color: "#d0d0d0"; font.pixelSize: 14; elide: Text.ElideRight }
                            }
                        }
                    }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        color: "#a0a0a0"
                        font.pixelSize: 13
                        text: camera.applyingSize ? "Changing the picture size..." :
                              "The smallest size other apps get from this camera too. Video calls are lightest at the smaller size."
                    }
                }

                // view options of this app
                Label { Layout.leftMargin: 18; Layout.topMargin: 10; text: "VIEW"; color: "#a0a0a0"; font.pixelSize: 13; font.bold: true }
                RowLayout {
                    Layout.leftMargin: 18
                    Layout.rightMargin: 18
                    Label { Layout.fillWidth: true; text: "Grid"; color: "white"; font.pixelSize: 16 }
                    Switch { checked: win.grid; onToggled: win.grid = checked }
                }

                // quality of what is saved
                Label { Layout.leftMargin: 18; Layout.topMargin: 10; text: "QUALITY"; color: "#a0a0a0"; font.pixelSize: 13; font.bold: true }
                Repeater {
                    model: [["photo", "Photos", camera.photoQuality], ["video", "Videos", camera.videoQuality]]
                    RowLayout {
                        Layout.leftMargin: 18
                        Layout.rightMargin: 18
                        readonly property string kind: modelData[0]
                        readonly property string current: modelData[2]
                        Label { Layout.fillWidth: true; text: modelData[1]; color: "white"; font.pixelSize: 16 }
                        Repeater {
                            model: [["standard", "Standard"], ["high", "High"], ["maximum", "Max"]]
                            AbstractButton {
                                implicitWidth: 84
                                implicitHeight: 38
                                onClicked: camera.setQuality(kind, modelData[0])
                                background: Rectangle { radius: height / 2; color: current === modelData[0] ? "#3d7eff" : "#2c2c2e" }
                                contentItem: Label {
                                    text: modelData[1]
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    color: "white"
                                    font.pixelSize: 14
                                }
                            }
                        }
                    }
                }
                Label {
                    Layout.leftMargin: 18
                    Layout.rightMargin: 18
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    color: "#a0a0a0"
                    font.pixelSize: 13
                    text: "Higher quality keeps more detail in bigger files. Videos are encoded by the graphics chip at any quality."
                }

                // the sliders, in the groups of the Cameras page
                Repeater {
                    model: settingsDrawer.data.controls || []
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        readonly property var group: modelData
                        Label {
                            Layout.leftMargin: 18
                            Layout.topMargin: 12
                            text: group.group.toUpperCase()
                            color: "#a0a0a0"
                            font.pixelSize: 13
                            font.bold: true
                        }
                        Repeater {
                            model: group.items.filter(it => !it.adv && it.key !== "hue_spin")
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.leftMargin: 18
                                Layout.rightMargin: 18
                                spacing: 0
                                readonly property var item: modelData
                                readonly property real value: {
                                    const v = (settingsDrawer.data.values || {})[item.key]
                                    return v === undefined ? item.default : v
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Label { Layout.fillWidth: true; text: item.label; color: "white"; font.pixelSize: 16 }
                                    Label {
                                        color: "#d0d0d0"
                                        font.pixelSize: 15
                                        text: item.names ? item.names[Math.round(slider.value)]
                                              : slider.value.toFixed(item.step >= 1 ? 0 : (item.step >= 0.1 ? 1 : 2)) + (item.unit ? " " + item.unit : "")
                                    }
                                    ToolButton {
                                        icon.name: "edit-undo"
                                        visible: Math.abs(slider.value - item.default) > item.step / 2
                                        onClicked: { slider.value = item.default; camera.setSetting(item.key, item.default) }
                                    }
                                }
                                Slider {
                                    id: slider
                                    Layout.fillWidth: true
                                    from: item.min
                                    to: item.max
                                    stepSize: item.step
                                    snapMode: Slider.SnapAlways
                                    value: parent.value
                                    // live while the finger moves, at most ten times a second
                                    onMoved: sendTimer.restart()
                                    Timer {
                                        id: sendTimer
                                        interval: 100
                                        onTriggered: camera.setSetting(item.key, slider.value)
                                    }
                                }
                            }
                        }
                    }
                }
                Item { Layout.preferredHeight: 30 }
            }
        }
    }

    // ---- gallery: the photos and videos taken, newest first, swiped left and right
    Rectangle {
        id: gallery
        anchors.fill: parent
        color: "black"
        visible: false
        property var items: []

        function openAt(i) {
            items = camera.captures
            if (items.length === 0)
                return
            visible = true
            list.positionViewAtIndex(i, ListView.Beginning)
            list.currentIndex = i
        }
        function close() {
            visible = false
            player.stop()
        }
        Connections {
            target: camera
            function onCapturesChanged() {
                if (gallery.visible) {
                    const keep = gallery.items[list.currentIndex]
                    gallery.items = camera.captures
                    const i = gallery.items.indexOf(keep)
                    list.currentIndex = Math.max(0, Math.min(i >= 0 ? i : list.currentIndex, gallery.items.length - 1))
                    if (gallery.items.length === 0) gallery.close()
                }
            }
        }

        readonly property string current: items.length > 0 && list.currentIndex >= 0 ? items[list.currentIndex] : ""
        readonly property bool currentIsVideo: /\.(mp4|mkv|webm|mov)$/i.test(current)

        ListView {
            id: list
            anchors.fill: parent
            orientation: ListView.Horizontal
            snapMode: ListView.SnapOneItem
            highlightRangeMode: ListView.StrictlyEnforceRange
            boundsBehavior: Flickable.StopAtBounds
            model: gallery.items
            onCurrentIndexChanged: player.stop()
            delegate: Item {
                width: list.width
                height: list.height
                readonly property bool isVideo: /\.(mp4|mkv|webm|mov)$/i.test(modelData)
                Image {
                    anchors.fill: parent
                    visible: !parent.isVideo
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                    sourceSize.width: 1920
                    source: parent.isVideo ? "" : "file://" + modelData
                }
                Label {
                    anchors.centerIn: parent
                    visible: parent.isVideo && !(player.playing && ListView.isCurrentItem)
                    text: "▶"
                    color: "white"
                    font.pixelSize: 90
                    TapHandler { onTapped: { list.currentIndex = index; player.source = "file://" + modelData; player.play() } }
                }
            }
        }
        // one player, over the video in front
        VideoOutput {
            id: videoOut
            anchors.fill: parent
            visible: player.playing || player.playbackState === MediaPlayer.PausedState
        }
        MediaPlayer {
            id: player
            videoOutput: videoOut
            audioOutput: AudioOutput {}
            readonly property bool playing: playbackState === MediaPlayer.PlayingState
        }
        TapHandler {
            enabled: videoOut.visible
            onTapped: player.playing ? player.pause() : player.play()
        }

        // top bar: back, position, open elsewhere, trash
        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 72
            color: "#99000000"
            RowLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 12
                RoundButton2 { iconName: "go-previous"; onClicked: gallery.close() }
                Label {
                    Layout.fillWidth: true
                    color: "white"
                    font.pixelSize: 17
                    text: gallery.items.length ? (list.currentIndex + 1) + " / " + gallery.items.length : ""
                }
                RoundButton2 { iconName: "document-open"; onClicked: camera.openExternally(gallery.current) }
                RoundButton2 { iconName: "edit-delete"; onClicked: confirmTrash.open() }
            }
        }
        Dialog {
            id: confirmTrash
            anchors.centerIn: parent
            modal: true
            title: gallery.currentIsVideo ? "Move this video to the trash?" : "Move this photo to the trash?"
            standardButtons: Dialog.Yes | Dialog.No
            onAccepted: { player.stop(); camera.trash(gallery.current) }
        }
    }

    // the back button of the system closes the gallery or the settings first
    onClosing: close => {
        if (gallery.visible) { gallery.close(); close.accepted = false }
    }
}
