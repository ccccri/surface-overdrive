// The window of overdrive-camera (cameraapp.py). Laid out like the camera of an iPad: the picture in the middle, a black
// column of controls at the right edge (at the bottom when the tablet stands upright) with the camera switch, the modes,
// the shutter and the last picture; small round buttons over the picture for the screen light, the flash, night mode,
// the timer, the grid and the settings. Yellow marks what is on. Night mode turns itself on in the dark (a moon with the
// time to hold still) and a tap turns it off, as on an iPhone.
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

    readonly property color accent: "#ffd60a"
    readonly property color glass: "#8c1c1c1e"
    readonly property bool landscape: width >= height
    readonly property real column: landscape ? 140 : 190
    property string mode: "photo"            // "photo" or "video"
    property int timerSeconds: 0              // 0, 3 or 10 before a photo
    property int countdown: 0
    property bool grid: false
    property bool flashing: false            // the screen is white: a front flash photo is being taken
    property string note: ""

    // ---- the picture, in the space the controls leave
    Item {
        id: stage
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

        // rule-of-thirds grid
        Item {
            anchors.fill: parent
            visible: win.grid
            Repeater {
                model: 2
                Rectangle { x: parent.width * (index + 1) / 3; width: 1; height: parent.height; color: "#70ffffff" }
            }
            Repeater {
                model: 2
                Rectangle { y: parent.height * (index + 1) / 3; height: 1; width: parent.width; color: "#70ffffff" }
            }
        }

        // the shutter's blink
        Rectangle {
            id: blink
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

        // errors, the camera starting
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

        // countdown of the timer
        Label {
            anchors.centerIn: parent
            visible: win.countdown > 0
            text: win.countdown
            color: "white"
            font.pixelSize: 180
            font.weight: Font.Thin
            font.family: "monospace"
        }

        // night photo: hold still, then the merge
        Column {
            anchors.centerIn: parent
            spacing: 14
            visible: camera.busy !== ""
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                radius: height / 2
                color: win.glass
                width: busyText.implicitWidth + 40
                height: busyText.implicitHeight + 20
                Label {
                    id: busyText
                    anchors.centerIn: parent
                    text: camera.busy.toUpperCase()
                    color: win.accent
                    font.pixelSize: 17
                    font.letterSpacing: 2
                    font.weight: Font.DemiBold
                }
            }
        }

        // recording time
        Rectangle {
            anchors.top: parent.top
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.topMargin: 18
            radius: 8
            color: "#e8ff3b30"
            width: recLabel.implicitWidth + 28
            height: recLabel.implicitHeight + 10
            visible: camera.recording
            Label {
                id: recLabel
                anchors.centerIn: parent
                color: "white"
                font.pixelSize: 20
                font.family: "monospace"
                text: clock.text
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
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 24
            color: "white"
            font.pixelSize: 16
            text: win.note
            visible: win.note !== ""
            background: Rectangle { color: win.glass; radius: height / 2 }
            leftPadding: 18; rightPadding: 18; topPadding: 9; bottomPadding: 9
        }
        Timer { id: noteTimer; interval: 2600; onTriggered: win.note = "" }
        Connections {
            target: camera
            function onMessage(text) { win.note = text; noteTimer.restart() }
        }

        // ---- the small buttons over the picture: a column at the left (landscape) or a row at the top (portrait)
        Grid {
            id: tools
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.margins: 18
            columns: win.landscape ? 1 : 6
            spacing: 14

            Chip {
                iconName: "flashlight-on"
                on: camera.light
                hint: camera.light ? "Screen light on" : "Screen light"
                onClicked: camera.toggleLight()
            }
            Chip {
                glyph: "bolt"
                visible: camera.key === "front" && win.mode === "photo"
                on: camera.flashMode === "on" || (camera.flashMode === "auto" && camera.dark && !camera.light)
                badge: camera.flashMode === "auto" ? "A" : camera.flashMode === "off" ? "OFF" : ""
                onClicked: camera.cycleFlash()
            }
            Chip {
                glyph: "moon"
                visible: camera.dark && win.mode === "photo"
                on: camera.night
                slashed: !camera.night
                badge: camera.night ? "1s" : ""
                onClicked: camera.toggleNight()
            }
            Chip {
                iconName: "chronometer"
                visible: win.mode === "photo"
                on: win.timerSeconds > 0
                badge: win.timerSeconds > 0 ? win.timerSeconds + "s" : ""
                onClicked: win.timerSeconds = win.timerSeconds === 0 ? 3 : win.timerSeconds === 3 ? 10 : 0
            }
            Chip {
                iconName: "view-grid"
                on: win.grid
                onClicked: win.grid = !win.grid
            }
            Chip {
                iconName: "configure"
                enabled: !camera.recording
                onClicked: settingsDrawer.open()
            }
        }
    }

    // the screen as the flash of a front photo
    Rectangle {
        anchors.fill: parent
        color: "#fff6ec"
        visible: win.flashing
        z: 10
    }

    // ---- a round button over the picture; yellow when on, a badge with its setting
    component Chip: AbstractButton {
        id: chip
        property string iconName
        property bool on: false
        property bool slashed: false
        property string badge: ""
        property string hint: ""
        property string glyph: ""
        implicitWidth: badge !== "" ? 44 + badgeLabel.implicitWidth + 6 : 44
        implicitHeight: 44
        opacity: enabled ? 1 : 0.35
        background: Rectangle {
            radius: height / 2
            color: chip.on ? "#33ffd60a" : win.glass
            border.color: chip.on ? win.accent : "transparent"
            border.width: 1
            scale: chip.pressed ? 0.92 : 1
            Behavior on scale { NumberAnimation { duration: 90 } }
        }
        contentItem: Row {
            spacing: 2
            leftPadding: 11
            Item {
                width: 22; height: 22
                anchors.verticalCenter: parent.verticalCenter
                // drawn glyphs where Breeze has none fitting: a lightning bolt, a crescent moon
                Shape {
                    anchors.fill: parent
                    visible: chip.glyph === "bolt"
                    ShapePath {
                        fillColor: chip.on ? win.accent : "white"
                        strokeColor: "transparent"
                        startX: 13; startY: 1
                        PathLine { x: 4; y: 13 }
                        PathLine { x: 10.5; y: 13 }
                        PathLine { x: 8.5; y: 21 }
                        PathLine { x: 18; y: 8.5 }
                        PathLine { x: 11.5; y: 8.5 }
                        PathLine { x: 13; y: 1 }
                    }
                }
                Shape {
                    anchors.fill: parent
                    visible: chip.glyph === "moon"
                    ShapePath {
                        fillColor: chip.on ? win.accent : "white"
                        strokeColor: "transparent"
                        // round the left of a circle from top to bottom, back up along a flatter curve
                        startX: 14; startY: 2.5
                        PathArc { x: 14; y: 19.5; radiusX: 9; radiusY: 9; useLargeArc: true; direction: PathArc.Counterclockwise }
                        PathArc { x: 14; y: 2.5; radiusX: 11; radiusY: 11; direction: PathArc.Clockwise }
                    }
                }
                Button {
                    // the theme icon, coloured: through a button, which tints its icon
                    visible: chip.glyph === ""
                    anchors.centerIn: parent
                    padding: 0
                    flat: true
                    enabled: false
                    background: null
                    icon.name: chip.iconName
                    icon.color: chip.on ? win.accent : "white"
                    icon.width: 22
                    icon.height: 22
                }
                Rectangle {
                    visible: chip.slashed
                    anchors.centerIn: parent
                    width: 28; height: 2
                    rotation: -45
                    color: "white"
                }
            }
            Label {
                id: badgeLabel
                anchors.verticalCenter: parent.verticalCenter
                visible: chip.badge !== ""
                text: chip.badge
                color: chip.on ? win.accent : "white"
                font.pixelSize: 13
                font.weight: Font.DemiBold
                font.family: "monospace"
            }
        }
    }

    // ---- taking pictures
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
    Timer {
        // the front flash: the screen white and at its brightest, a moment for the exposure, then the photo
        id: flashTimer
        interval: 700
        onTriggered: { camera.takePhoto(); flashEnd.restart() }
    }
    Timer {
        id: flashEnd
        // a single frame is in at once; a night photo takes its frames under the light too
        interval: camera.night ? 1000 : 250
        onTriggered: { win.flashing = false; camera.flashOff() }
    }

    function capturePhoto() {
        if (camera.flashWanted()) {
            win.flashing = true
            camera.flashOn()
            flashTimer.restart()
            return
        }
        blinkAnim.restart()
        camera.takePhoto()
    }
    function shutter() {
        if (win.mode === "video") {
            camera.toggleRecording()
            return
        }
        if (camera.busy !== "")
            return
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

    // ---- the control column: right edge (landscape) or bottom (portrait)
    Rectangle {
        id: controls
        color: "black"
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        width: win.landscape ? win.column : parent.width
        height: win.landscape ? parent.height : win.column

        GridLayout {
            anchors.fill: parent
            anchors.topMargin: win.landscape ? 28 : 0
            anchors.bottomMargin: win.landscape ? 28 : 0
            anchors.leftMargin: win.landscape ? 0 : 36
            anchors.rightMargin: win.landscape ? 0 : 36
            flow: win.landscape ? GridLayout.TopToBottom : GridLayout.LeftToRight
            rows: win.landscape ? 5 : 1
            columns: win.landscape ? 1 : 5

            // switch camera
            AbstractButton {
                Layout.alignment: Qt.AlignCenter
                implicitWidth: 56
                implicitHeight: 56
                enabled: camera.keys.length > 1 && !camera.recording && !camera.applyingSize && camera.busy === ""
                opacity: enabled ? 1 : 0.35
                onClicked: { flip.restart(); camera.next() }
                background: Rectangle { radius: width / 2; color: "#2c2c2e" }
                contentItem: Item {
                    Button {
                        id: flipIcon
                        anchors.centerIn: parent
                        padding: 0; flat: true; enabled: false; background: null
                        icon.name: "exchange-positions-clockwise"
                        icon.color: "white"
                        icon.width: 26; icon.height: 26
                        RotationAnimation on rotation { id: flip; running: false; from: 0; to: 180; duration: 300 }
                    }
                }
            }

            Item { Layout.fillWidth: !win.landscape; Layout.fillHeight: win.landscape }

            // the shutter with the modes beside it
            ColumnLayout {
                Layout.alignment: Qt.AlignCenter
                spacing: 18
                // modes: the chosen one in yellow, as on an iPhone
                Column {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 10
                    visible: win.landscape
                    Repeater {
                        model: [["video", "VIDEO"], ["photo", "PHOTO"]]
                        Label {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: modelData[1]
                            color: win.mode === modelData[0] ? win.accent : "#dddddd"
                            font.pixelSize: 14
                            font.letterSpacing: 2
                            font.weight: Font.DemiBold
                            TapHandler {
                                enabled: !camera.recording && camera.busy === ""
                                onTapped: { win.mode = modelData[0]; countdownTimer.stop(); win.countdown = 0 }
                            }
                        }
                    }
                }
                AbstractButton {
                    id: shutterButton
                    Layout.alignment: Qt.AlignHCenter
                    implicitWidth: 84
                    implicitHeight: 84
                    enabled: camera.key !== "" && camera.error === "" && !camera.applyingSize
                    opacity: enabled ? 1 : 0.4
                    onClicked: win.shutter()
                    background: Item {
                        Rectangle { anchors.fill: parent; radius: width / 2; color: "transparent"; border.color: "white"; border.width: 4 }
                        // the night frames being collected
                        Shape {
                            anchors.fill: parent
                            visible: camera.busy !== "" && camera.progress > 0
                            ShapePath {
                                strokeColor: win.accent
                                strokeWidth: 4
                                fillColor: "transparent"
                                capStyle: ShapePath.RoundCap
                                PathAngleArc {
                                    centerX: 42; centerY: 42; radiusX: 40; radiusY: 40
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
                            width: rec ? 30 : (shutterButton.pressed ? 60 : 68)
                            height: width
                            radius: rec ? 6 : width / 2
                            color: win.mode === "video" ? "#ff3b30" : "white"
                            Behavior on width { NumberAnimation { duration: 120 } }
                            Behavior on radius { NumberAnimation { duration: 120 } }
                            Behavior on color { ColorAnimation { duration: 150 } }
                        }
                    }
                }
                Row {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 22
                    visible: !win.landscape
                    Repeater {
                        model: [["video", "VIDEO"], ["photo", "PHOTO"]]
                        Label {
                            text: modelData[1]
                            color: win.mode === modelData[0] ? win.accent : "#dddddd"
                            font.pixelSize: 14
                            font.letterSpacing: 2
                            font.weight: Font.DemiBold
                            TapHandler {
                                enabled: !camera.recording && camera.busy === ""
                                onTapped: { win.mode = modelData[0]; countdownTimer.stop(); win.countdown = 0 }
                            }
                        }
                    }
                }
            }

            Item { Layout.fillWidth: !win.landscape; Layout.fillHeight: win.landscape }

            // the last photo or video: opens the gallery
            AbstractButton {
                Layout.alignment: Qt.AlignCenter
                implicitWidth: 56
                implicitHeight: 56
                enabled: camera.lastCapture !== ""
                onClicked: gallery.openAt(0)
                background: Rectangle { radius: 10; color: "#2c2c2e" }
                contentItem: Item {
                    clip: true
                    Image {
                        anchors.fill: parent
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        sourceSize.width: 160
                        source: camera.lastCapture !== "" && !camera.lastIsVideo ? camera.lastCapture : ""
                        layer.enabled: true
                    }
                    Label {
                        anchors.centerIn: parent
                        visible: camera.lastIsVideo
                        text: "▶"
                        color: "white"
                        font.pixelSize: 22
                    }
                }
            }
        }
    }

    // ---- settings: the adjustments of the Cameras page, for the camera in use
    Drawer {
        id: settingsDrawer
        edge: Qt.RightEdge
        width: Math.min(440, win.width * 0.9)
        height: win.height
        dim: true
        background: Rectangle { color: "#f21c1c1e" }

        property var data: {
            try { return JSON.parse(camera.settings) } catch (e) { return ({}) }
        }

        component Heading: Label {
            Layout.leftMargin: 22
            Layout.topMargin: 14
            color: "#8e8e93"
            font.pixelSize: 12
            font.letterSpacing: 1.5
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
                    Layout.margins: 20
                    Label {
                        Layout.fillWidth: true
                        text: (camera.key === "front" ? "Front" : "Rear") + " camera"
                        color: "white"
                        font.pixelSize: 24
                        font.weight: Font.DemiBold
                    }
                    Button {
                        text: "Reset"
                        flat: true
                        palette.buttonText: win.accent
                        onClicked: camera.resetSettings()
                    }
                }

                Heading { text: "PICTURE SIZE" }
                ColumnLayout {
                    Layout.leftMargin: 18
                    Layout.rightMargin: 18
                    Layout.fillWidth: true
                    spacing: 6
                    Repeater {
                        model: settingsDrawer.data.sizes || []
                        AbstractButton {
                            Layout.fillWidth: true
                            implicitHeight: 54
                            readonly property bool current: (settingsDrawer.data.values || {}).minWidth === modelData.minWidth
                            enabled: !camera.applyingSize && !current && !camera.recording
                            onClicked: camera.setSetting("minWidth", modelData.minWidth)
                            background: Rectangle {
                                radius: 12
                                color: "#2c2c2e"
                                border.color: parent.current ? win.accent : "transparent"
                                border.width: 1.5
                            }
                            contentItem: RowLayout {
                                Label { Layout.leftMargin: 16; text: modelData.text; color: "white"; font.pixelSize: 17; font.family: "monospace" }
                                Label { Layout.fillWidth: true; Layout.rightMargin: 12; text: modelData.desc; color: "#aeaeb2"; font.pixelSize: 14; elide: Text.ElideRight; horizontalAlignment: Text.AlignRight }
                            }
                        }
                    }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        color: "#8e8e93"
                        font.pixelSize: 13
                        text: camera.applyingSize ? "Changing the picture size..." :
                              "The smallest size other apps get from this camera too. Video calls are lightest at the smaller size."
                    }
                }

                // the sliders, in the groups of the Cameras page
                Repeater {
                    model: settingsDrawer.data.controls || []
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        readonly property var group: modelData
                        Heading { text: group.group.toUpperCase() }
                        Repeater {
                            model: group.items.filter(it => !it.adv && it.key !== "hue_spin")
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.leftMargin: 22
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
                                        color: Math.abs(slider.value - item.default) > item.step / 2 ? win.accent : "#aeaeb2"
                                        font.pixelSize: 14
                                        font.family: "monospace"
                                        text: item.names ? item.names[Math.round(slider.value)]
                                              : slider.value.toFixed(item.step >= 1 ? 0 : (item.step >= 0.1 ? 1 : 2)) + (item.unit ? " " + item.unit : "")
                                    }
                                    ToolButton {
                                        icon.name: "edit-undo"
                                        icon.color: "white"
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
                    color: win.glass
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

        RowLayout {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: 18
            spacing: 12
            Chip { iconName: "go-previous"; onClicked: gallery.close() }
            Item { Layout.fillWidth: true }
            Label {
                color: "white"
                font.pixelSize: 15
                font.family: "monospace"
                text: gallery.items.length ? (list.currentIndex + 1) + " / " + gallery.items.length : ""
                background: Rectangle { color: win.glass; radius: height / 2 }
                leftPadding: 14; rightPadding: 14; topPadding: 8; bottomPadding: 8
            }
            Item { Layout.fillWidth: true }
            Chip { iconName: "document-open"; onClicked: camera.openExternally(gallery.current) }
            Chip { iconName: "edit-delete"; onClicked: confirmTrash.open() }
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
