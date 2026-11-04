// The window of overdrive-camera (cameraapp.py). The order of the iPhone camera, the look of Plasma: the picture alone
// on the left, nothing drawn over it; every control in one column at the right edge (at the bottom when the tablet
// stands upright), so that what a button opens comes out on its own side. In the column, from the top: the light,
// the flash and night mode, the settings; then the modes and the shutter; then the last picture and the camera switch.
// Breeze icons and Plasma's shapes and highlight colour.
//
// The light: the window draws a warm white frame round everything and moves picture and controls inside it, with
// the backlight at its brightest; nothing is covered, the button stays where the finger expects it. A flash photo
// lights the same frame for a moment.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Shapes
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

    // Plasma's highlight (the accent the user picked), Breeze's dark surfaces
    readonly property color accent: palette.highlight
    readonly property color surface: "#232629"
    readonly property color raised: "#31363b"
    readonly property bool landscape: width >= height
    readonly property real column: landscape ? 168 : 230
    property string mode: "photo"            // "photo" or "video"
    property bool grid: false
    property bool flashing: false            // the frame lit for a flash photo
    property string note: ""

    // the light frame: warm white, as wide as a phone's ring light looks from arm's length
    readonly property bool lit: camera.light || win.flashing
    property real ring: lit ? Math.round(Math.min(width, height) * 0.085) : 0
    Behavior on ring { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
    Rectangle {
        anchors.fill: parent
        color: "#fff1df"
        visible: win.ring > 0
    }

    Item {
        id: content
        anchors.fill: parent
        anchors.margins: win.ring

        // ---- the picture
        Rectangle {
            id: stage
            color: "black"
            radius: win.ring > 0 ? 14 : 0
            clip: true
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.right: win.landscape ? controls.left : parent.right
            anchors.bottom: win.landscape ? parent.bottom : controls.top

            GstGLQt6VideoItem {
                id: view
                anchors.fill: parent
                // the front camera is shown as a mirror, like every selfie camera; photos and videos are not mirrored
                transform: Scale { origin.x: view.width / 2; xScale: camera.mirrored ? -1 : 1 }
                Component.onCompleted: camera.setSink(view)
            }
            Item {
                anchors.fill: parent
                visible: win.grid
                Repeater {
                    model: 2
                    Rectangle { x: parent.width * (index + 1) / 3; width: 1; height: parent.height; color: "#60ffffff" }
                }
                Repeater {
                    model: 2
                    Rectangle { y: parent.height * (index + 1) / 3; height: 1; width: parent.width; color: "#60ffffff" }
                }
            }
            // the shutter's blink
            Rectangle {
                anchors.fill: parent
                color: "black"
                opacity: 0
                SequentialAnimation on opacity {
                    id: blinkAnim
                    running: false
                    NumberAnimation { to: 0.85; duration: 40 }
                    NumberAnimation { to: 0; duration: 180 }
                }
            }
            // only when there is no picture at all: why
            Label {
                anchors.centerIn: parent
                width: parent.width * 0.7
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                color: "white"
                font.pixelSize: 20
                text: camera.error
                visible: camera.error !== ""
            }
        }

        // ---- the column
        Rectangle {
            id: controls
            color: win.surface
            radius: win.ring > 0 ? 14 : 0
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            width: win.landscape ? win.column : parent.width
            height: win.landscape ? parent.height : win.column

            GridLayout {
                anchors.fill: parent
                anchors.margins: 18
                flow: win.landscape ? GridLayout.TopToBottom : GridLayout.LeftToRight
                rows: win.landscape ? 5 : 1
                columns: win.landscape ? 1 : 5
                rowSpacing: 14
                columnSpacing: 22

                // the quick settings: light, flash, night mode, settings
                Grid {
                    Layout.alignment: Qt.AlignCenter
                    columns: win.landscape ? 2 : 4
                    spacing: 10
                    Tool {
                        iconName: "flashlight-on"
                        on: camera.light
                        label: "Light"
                        onClicked: camera.toggleLight()
                    }
                    Tool {
                        glyph: "bolt"
                        enabled: camera.key === "front" && win.mode === "photo"
                        on: camera.flashMode === "on" || (camera.flashMode === "auto" && camera.dark && !camera.light)
                        label: camera.flashMode === "auto" ? "Auto" : camera.flashMode === "on" ? "On" : "Off"
                        onClicked: camera.cycleFlash()
                    }
                    Tool {
                        glyph: "moon"
                        enabled: camera.dark && win.mode === "photo"
                        on: camera.night
                        slashed: camera.dark && !camera.night
                        label: !camera.dark ? "Night" : camera.night ? "2 s" : "Off"
                        onClicked: camera.toggleNight()
                    }
                    Tool {
                        iconName: "configure"
                        label: "Settings"
                        enabled: !camera.recording
                        onClicked: settingsDrawer.open()
                    }
                }

                Item { Layout.fillWidth: !win.landscape; Layout.fillHeight: win.landscape }

                // modes, what is going on, the shutter
                ColumnLayout {
                    Layout.alignment: Qt.AlignCenter
                    spacing: 14
                    Row {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: 4
                        Repeater {
                            model: [["photo", "Photo"], ["video", "Video"]]
                            AbstractButton {
                                implicitWidth: 62
                                implicitHeight: 30
                                enabled: !camera.recording && camera.busy === ""
                                onClicked: win.mode = modelData[0]
                                background: Rectangle {
                                    radius: 6
                                    color: win.mode === modelData[0] ? win.raised : "transparent"
                                    border.color: win.mode === modelData[0] ? win.accent : "transparent"
                                }
                                contentItem: Label {
                                    text: modelData[1]
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    color: win.mode === modelData[0] ? "white" : "#a0a4a8"
                                    font.pixelSize: 14
                                }
                            }
                        }
                    }
                    // the status line: hold still, processing, recording time, messages
                    Label {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: 140
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        font.pixelSize: 13
                        color: camera.recording ? "#ff5f57" : camera.busy !== "" ? win.accent : "#d0d4d8"
                        font.family: camera.recording ? "monospace" : ""
                        text: camera.recording ? "● " + clock.text : camera.busy !== "" ? camera.busy : win.note
                        Text { id: clock; visible: false; text: "0:00" }
                        Timer {
                            interval: 250; repeat: true; running: camera.recording; triggeredOnStart: true
                            onTriggered: clock.text = camera.elapsed()
                        }
                    }
                    AbstractButton {
                        id: shutterButton
                        Layout.alignment: Qt.AlignHCenter
                        implicitWidth: 80
                        implicitHeight: 80
                        enabled: camera.key !== "" && camera.error === "" && !camera.applyingSize
                        opacity: enabled ? 1 : 0.4
                        onClicked: win.shutter()
                        background: Item {
                            Rectangle { anchors.fill: parent; radius: width / 2; color: "transparent"; border.color: "white"; border.width: 4 }
                            Shape {
                                anchors.fill: parent
                                visible: camera.busy !== "" && camera.progress > 0
                                ShapePath {
                                    strokeColor: win.accent
                                    strokeWidth: 4
                                    fillColor: "transparent"
                                    capStyle: ShapePath.RoundCap
                                    PathAngleArc {
                                        centerX: 40; centerY: 40; radiusX: 38; radiusY: 38
                                        startAngle: -90
                                        sweepAngle: 360 * camera.progress
                                    }
                                }
                            }
                        }
                        contentItem: Item {
                            Rectangle {
                                anchors.centerIn: parent
                                readonly property bool rec: camera.recording
                                width: rec ? 28 : (shutterButton.pressed ? 56 : 64)
                                height: width
                                radius: rec ? 6 : width / 2
                                color: win.mode === "video" ? "#da4453" : "white"
                                Behavior on width { NumberAnimation { duration: 120 } }
                                Behavior on radius { NumberAnimation { duration: 120 } }
                                Behavior on color { ColorAnimation { duration: 150 } }
                            }
                        }
                    }
                }

                Item { Layout.fillWidth: !win.landscape; Layout.fillHeight: win.landscape }

                // the last picture and the camera switch
                Row {
                    Layout.alignment: Qt.AlignCenter
                    spacing: 14
                    AbstractButton {
                        implicitWidth: 52
                        implicitHeight: 52
                        enabled: camera.lastCapture !== ""
                        onClicked: gallery.openAt(0)
                        background: Rectangle { radius: 8; color: win.raised; border.color: "#4d5257" }
                        contentItem: Item {
                            clip: true
                            Image {
                                anchors.fill: parent
                                anchors.margins: 2
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
                                font.pixelSize: 20
                            }
                        }
                    }
                    Tool {
                        iconName: "exchange-positions-clockwise"
                        enabled: camera.keys.length > 1 && !camera.recording && !camera.applyingSize && camera.busy === ""
                        onClicked: camera.next()
                    }
                }
            }
        }
    }

    Timer { id: noteTimer; interval: 2600; onTriggered: win.note = "" }
    Connections {
        target: camera
        function onMessage(text) { win.note = text; noteTimer.restart() }
    }

    // ---- a button of the column: Breeze icon (or a drawn glyph), its state underneath, the highlight when on
    component Tool: AbstractButton {
        id: tool
        property string iconName
        property string glyph: ""
        property bool on: false
        property bool slashed: false
        property string label: ""
        implicitWidth: 56
        implicitHeight: label !== "" ? 66 : 52
        opacity: enabled ? 1 : 0.35
        background: Rectangle {
            radius: 8
            color: tool.pressed ? "#4d5257" : tool.on ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.25) : win.raised
            border.color: tool.on ? win.accent : "transparent"
        }
        contentItem: Column {
            spacing: 3
            topPadding: tool.label !== "" ? 8 : 14
            Item {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 24; height: 24
                Shape {
                    anchors.fill: parent
                    visible: tool.glyph === "bolt"
                    ShapePath {
                        fillColor: tool.on ? win.accent : "#eff0f1"
                        strokeColor: "transparent"
                        startX: 14; startY: 1
                        PathLine { x: 4; y: 14 }
                        PathLine { x: 11; y: 14 }
                        PathLine { x: 9; y: 23 }
                        PathLine { x: 20; y: 9 }
                        PathLine { x: 12.5; y: 9 }
                        PathLine { x: 14; y: 1 }
                    }
                }
                Shape {
                    anchors.fill: parent
                    visible: tool.glyph === "moon"
                    ShapePath {
                        fillColor: tool.on ? win.accent : "#eff0f1"
                        strokeColor: "transparent"
                        // round the left of a circle from top to bottom, back up along a flatter curve
                        startX: 15; startY: 2.5
                        PathArc { x: 15; y: 21.5; radiusX: 10; radiusY: 10; useLargeArc: true; direction: PathArc.Counterclockwise }
                        PathArc { x: 15; y: 2.5; radiusX: 12; radiusY: 12; direction: PathArc.Clockwise }
                    }
                }
                Button {
                    // the theme icon, tinted: through a button, which colours its icon
                    visible: tool.glyph === ""
                    anchors.centerIn: parent
                    padding: 0; flat: true; enabled: false; background: null
                    icon.name: tool.iconName
                    icon.color: tool.on ? win.accent : "#eff0f1"
                    icon.width: 24; icon.height: 24
                }
                Rectangle {
                    visible: tool.slashed
                    anchors.centerIn: parent
                    width: 30; height: 2
                    rotation: -45
                    color: "#eff0f1"
                }
            }
            Label {
                anchors.horizontalCenter: parent.horizontalCenter
                visible: tool.label !== ""
                text: tool.label
                color: tool.on ? win.accent : "#a0a4a8"
                font.pixelSize: 11
            }
        }
    }

    // ---- taking pictures
    Timer {
        // the flash: the light frame and the backlight up, a moment for the exposure, then the photo
        id: flashTimer
        interval: 600
        onTriggered: { camera.takePhoto(); flashEnd.restart() }
    }
    Timer {
        id: flashEnd
        // a single frame is in at once; a night photo takes its frames in the light too
        interval: camera.night ? 1400 : 250
        onTriggered: { win.flashing = false; camera.flashOff() }
    }
    function shutter() {
        if (win.mode === "video") {
            camera.toggleRecording()
            return
        }
        if (camera.busy !== "")
            return
        if (camera.flashWanted()) {
            win.flashing = true
            camera.flashOn()
            flashTimer.restart()
            return
        }
        blinkAnim.restart()
        camera.takePhoto()
    }

    // ---- settings: from the right, where the button is
    Drawer {
        id: settingsDrawer
        edge: Qt.RightEdge
        width: Math.min(440, win.width * 0.9)
        height: win.height
        dim: true
        background: Rectangle { color: win.surface }

        property var data: {
            try { return JSON.parse(camera.settings) } catch (e) { return ({}) }
        }

        component Heading: Label {
            Layout.leftMargin: 20
            Layout.topMargin: 16
            color: "#a0a4a8"
            font.pixelSize: 13
            font.weight: Font.DemiBold
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
                        font.weight: Font.DemiBold
                    }
                    Button {
                        text: "Reset"
                        icon.name: "edit-undo"
                        onClicked: camera.resetSettings()
                    }
                }

                Heading { text: "Picture size" }
                ColumnLayout {
                    Layout.leftMargin: 18
                    Layout.rightMargin: 18
                    Layout.fillWidth: true
                    spacing: 6
                    Repeater {
                        model: settingsDrawer.data.sizes || []
                        AbstractButton {
                            Layout.fillWidth: true
                            implicitHeight: 50
                            readonly property bool current: (settingsDrawer.data.values || {}).minWidth === modelData.minWidth
                            enabled: !camera.applyingSize && !current && !camera.recording
                            onClicked: camera.setSetting("minWidth", modelData.minWidth)
                            background: Rectangle {
                                radius: 8
                                color: parent.current ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.25) : win.raised
                                border.color: parent.current ? win.accent : "transparent"
                            }
                            contentItem: RowLayout {
                                Label { Layout.leftMargin: 14; text: modelData.text; color: "white"; font.pixelSize: 16 }
                                Label { Layout.fillWidth: true; Layout.rightMargin: 12; text: modelData.desc; color: "#a0a4a8"; font.pixelSize: 13; elide: Text.ElideRight; horizontalAlignment: Text.AlignRight }
                            }
                        }
                    }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        color: "#a0a4a8"
                        font.pixelSize: 13
                        text: camera.applyingSize ? "Changing the picture size..." :
                              "The smallest size other apps get from this camera too. Video calls are lightest at the smaller size."
                    }
                }

                Heading { text: "View" }
                RowLayout {
                    Layout.leftMargin: 20
                    Layout.rightMargin: 18
                    Label { Layout.fillWidth: true; text: "Grid"; color: "white"; font.pixelSize: 16 }
                    Switch { checked: win.grid; onToggled: win.grid = checked }
                }

                // the sliders, in the groups of the Cameras page
                Repeater {
                    model: settingsDrawer.data.controls || []
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        readonly property var group: modelData
                        Heading { text: group.group }
                        Repeater {
                            model: group.items.filter(it => !it.adv && it.key !== "hue_spin")
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.leftMargin: 20
                                Layout.rightMargin: 18
                                spacing: 0
                                readonly property var item: modelData
                                readonly property real value: {
                                    const v = (settingsDrawer.data.values || {})[item.key]
                                    return v === undefined ? item.default : v
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Label { Layout.fillWidth: true; text: item.label; color: "white"; font.pixelSize: 15 }
                                    Label {
                                        color: Math.abs(slider.value - item.default) > item.step / 2 ? win.accent : "#a0a4a8"
                                        font.pixelSize: 14
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
        z: 20
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
                Rectangle {
                    anchors.centerIn: parent
                    visible: parent.isVideo && !(player.playing && ListView.isCurrentItem)
                    width: 96; height: 96; radius: 48
                    color: "#b0232629"
                    Label { anchors.centerIn: parent; anchors.horizontalCenterOffset: 4; text: "▶"; color: "white"; font.pixelSize: 40 }
                    TapHandler { onTapped: { list.currentIndex = index; player.source = "file://" + modelData; player.play() } }
                }
            }
        }
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

        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 68
            color: "#d0232629"
            RowLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 10
                Tool { iconName: "go-previous"; onClicked: gallery.close() }
                Label {
                    Layout.fillWidth: true
                    color: "white"
                    font.pixelSize: 15
                    text: gallery.items.length ? (list.currentIndex + 1) + " of " + gallery.items.length : ""
                }
                Tool { iconName: "document-open"; onClicked: camera.openExternally(gallery.current) }
                Tool { iconName: "edit-delete"; onClicked: confirmTrash.open() }
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

    // the back button of the system closes the gallery first
    onClosing: close => {
        if (gallery.visible) { gallery.close(); close.accepted = false }
    }
}
