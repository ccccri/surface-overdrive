// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.surfaceoverdrive.kcm

// The page itself does not scroll: the preview stays in view and only the adjustments scroll, next to it (below it on a narrow window).
Kirigami.Page {
    id: root

    title: kcm.name
    padding: 0

    property string cam: "rear"
    Bars { target: root }
    property var d: ({ settings: {}, controls: [], presets: [], focus: {}, sizes: [], node: "" })
    property real peak: 1
    readonly property var s: d.settings
    readonly property bool wide: width > Kirigami.Units.gridUnit * 42
    readonly property var activePreset: d.presets.find(p => p.current)
    property int presetIndex: 0

    // ---- talking to overdrivectl ----
    function cmd(tag, args) { kcm.call(tag, ["camera", cam].concat(args)) }
    function load() { cmd("load", ["describe"]) }
    function setLocal(key, value) { const o = {}; o[key] = value; d = Object.assign({}, d, { settings: Object.assign({}, d.settings, o) }) }
    // sliders send many values while they move: keep the last one of each setting and send it a moment later
    function edit(key, value) {
        if (typeof value === "number" && !isFinite(value)) return          // never send what is not a number
        setLocal(key, value); pending[key] = value; sendTimer.restart()
    }
    property var pending: ({})
    Timer {
        id: sendTimer; interval: 90
        onTriggered: {
            const p = root.pending; root.pending = ({})
            for (const k in p) root.cmd("set", ["set", k, String(p[k])])
        }
    }
    Connections {
        target: kcm
        function onCallFinished(tag, ok, output, error) {
            if (tag === "poll") {
                if (!ok) return
                try {
                    const r = JSON.parse(output)
                    root.d = Object.assign({}, root.d, { focus: r.focus })
                    if (r.focus.sharpness !== undefined) root.peak = Math.max(root.peak * 0.995, r.focus.sharpness)
                } catch (e) {}
                return
            }
            if (tag !== "load" && tag !== "set" && tag !== "action") return
            if (!ok) { message.text = error || i18n("The change was not applied."); return }
            let r
            try { r = JSON.parse(output) } catch (e) { return }
            if (tag === "set") {
                // the sliders already show the value; only keep the live focus reading and the preset marks fresh
                root.d = Object.assign({}, root.d, { focus: r.focus, presets: r.presets })
                if (r.restart) restartPreview.restart()
                return
            }
            root.d = r
            const i = r.presets.findIndex(p => p.current)
            if (i >= 0) root.presetIndex = i
            else if (root.presetIndex >= r.presets.length) root.presetIndex = 0
            if (r.result === "invalid") message.text = i18n("Please type a name.")
            else if (r.result === "exists") message.text = i18n("A preset with that name already exists.")
            else message.text = ""
            if (r.restart) restartPreview.restart()
        }
    }

    // ---- preview ----
    function startPreview() { if (d.node) preview.start(d.node) }
    Timer { id: autoStart; interval: 500; onTriggered: root.startPreview() }
    Timer { id: restartPreview; interval: 300; onTriggered: root.startPreview() }   // overdrivectl returns once the cameras are back
    onCamChanged: { preview.stop(); peak = 1; load(); autoStart.restart() }
    Component.onCompleted: { load(); autoStart.start(); if (kcm.startTab === "bottom") toBottom.start() }
    Timer { id: toBottom; interval: 3000; onTriggered: scroll.contentItem.contentY = Math.max(0, scroll.contentItem.contentHeight - scroll.height) }   // "--args bottom": to check the end of the list from a script
    Component.onDestruction: preview.stop()
    onVisibleChanged: if (!visible) preview.stop()
    Timer { interval: 300; repeat: true; running: preview.running && root.cam === "rear"; onTriggered: root.cmd("poll", ["describe"]) }

    component NameDialog: QQC2.Dialog {
        id: nd
        property string mode: "save"
        property string targetId: ""
        modal: true
        anchors.centerIn: QQC2.Overlay.overlay
        title: mode === "save" ? i18n("Save the current settings as a preset") : mode === "rename" ? i18n("Rename preset") : i18n("Duplicate preset")
        standardButtons: QQC2.Dialog.Ok | QQC2.Dialog.Cancel
        contentItem: ColumnLayout {
            QQC2.Label { text: i18n("Name:") }
            QQC2.TextField { id: nameField; Layout.fillWidth: true; Layout.minimumWidth: Kirigami.Units.gridUnit * 18; maximumLength: 60; onAccepted: nd.accept() }
        }
        function begin(m, id, initial) { mode = m; targetId = id; nameField.text = initial; open(); nameField.forceActiveFocus(); nameField.selectAll() }
        onAccepted: {
            if (mode === "save") root.cmd("action", ["preset", "save", nameField.text])
            else if (mode === "rename") root.cmd("action", ["preset", "rename", targetId, nameField.text])
            else root.cmd("action", ["preset", "duplicate", targetId, nameField.text])
        }
    }
    // The picture size and the presets: under the preview when the window is wide (they stay in view with it), at the top of the
    // scrolling part otherwise.
    Component {
        id: sizeAndPresets
        ColumnLayout {
            spacing: Kirigami.Units.largeSpacing
            Section {
                title: i18n("Resolution")
                QQC2.ComboBox {
                    Layout.fillWidth: true
                    model: root.d.sizes.map(x => x.text)
                    currentIndex: { for (let i = 0; i < root.d.sizes.length; i++) if (root.d.sizes[i].minWidth === root.s.minWidth) return i; return 0 }
                    onActivated: { preview.stop(); root.edit("minWidth", root.d.sizes[currentIndex].minWidth) }
                    QQC2.ToolTip.text: i18n("The picture size apps get from this camera. The largest sizes read the whole sensor: sharpest photos, fewer pictures per second. For video calls pick a fast one. Changing it restarts the camera service.")
                    QQC2.ToolTip.visible: hovered && !popup.visible
                    QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                }
            }

            Section {
                title: i18n("Presets")
                QQC2.ComboBox {
                    Layout.fillWidth: true
                    enabled: root.d.presets.length > 0
                    model: root.d.presets.length > 0 ? root.d.presets.map(p => p.name + (p.current ? i18n("   (active)") : "")) : [i18n("No presets saved yet")]
                    currentIndex: root.presetIndex
                    onActivated: i => root.presetIndex = i
                }
                RowLayout {
                    Layout.fillWidth: true
                    QQC2.Button {
                        Layout.fillWidth: true
                        text: i18n("Apply"); icon.name: "dialog-ok-apply"
                        enabled: root.d.presets.length > 0
                        onClicked: root.cmd("action", ["preset", "apply", root.d.presets[root.presetIndex].id])
                    }
                    QQC2.Button {
                        Layout.fillWidth: true
                        text: i18n("Save As…"); icon.name: "document-save-as"
                        onClicked: nameDialog.begin("save", "", "")
                    }
                    QQC2.Button {
                        id: moreButton
                        text: i18n("More"); icon.name: "view-more-symbolic"
                        enabled: root.d.presets.length > 0
                        // right under the button: without a place the menu opens where the mouse pointer last was, which
                        // with a finger is anywhere
                        onClicked: moreMenu.popup(moreButton, 0, moreButton.height)
                        QQC2.Menu {
                            id: moreMenu
                            readonly property var p: root.d.presets.length > 0 ? root.d.presets[Math.min(root.presetIndex, root.d.presets.length - 1)] : ({ id: "", name: "" })
                            QQC2.MenuItem {
                                text: i18n("Update with the Current Settings…"); icon.name: "document-save"
                                onTriggered: {
                                    confirmDialog.text = i18n("Replace the settings stored in \"%1\" with the current ones?", moreMenu.p.name)
                                    confirmDialog.run = () => root.cmd("action", ["preset", "save", moreMenu.p.name, "overwrite"])
                                    confirmDialog.open()
                                }
                            }
                            QQC2.MenuItem { text: i18n("Rename…"); icon.name: "edit-rename"; onTriggered: nameDialog.begin("rename", moreMenu.p.id, moreMenu.p.name) }
                            QQC2.MenuItem { text: i18n("Duplicate…"); icon.name: "edit-copy"; onTriggered: nameDialog.begin("duplicate", moreMenu.p.id, i18n("%1 copy", moreMenu.p.name)) }
                            QQC2.MenuSeparator {}
                            QQC2.MenuItem {
                                text: i18n("Delete…"); icon.name: "edit-delete"
                                onTriggered: {
                                    confirmDialog.text = i18n("Delete the preset \"%1\"? This cannot be undone.", moreMenu.p.name)
                                    confirmDialog.run = () => root.cmd("action", ["preset", "delete", moreMenu.p.id])
                                    confirmDialog.open()
                                }
                            }
                        }
                    }
                }
                QQC2.Label {
                    Layout.fillWidth: true; elide: Text.ElideRight; opacity: 0.7
                    text: root.activePreset ? i18n("Current settings = \"%1\"", root.activePreset.name) : i18n("Current settings do not match a preset")
                }
            }
        }
    }

    NameDialog { id: nameDialog }
    QQC2.Dialog {
        id: confirmDialog
        property string text: ""
        property var run: null
        modal: true
        anchors.centerIn: QQC2.Overlay.overlay
        title: i18n("Are you sure?")
        standardButtons: QQC2.Dialog.Yes | QQC2.Dialog.No
        contentItem: QQC2.Label { text: confirmDialog.text; wrapMode: Text.WordWrap }
        onAccepted: if (run) run()
    }

    // A message lies over the top of the page and goes away by itself: it never pushes the preview and the settings around.
    Kirigami.InlineMessage {
        id: message
        z: 10
        anchors { top: parent.top; left: parent.left; right: parent.right; margins: Kirigami.Units.largeSpacing }
        visible: text.length > 0
        type: Kirigami.MessageType.Warning
        showCloseButton: true
        onTextChanged: if (text.length > 0) hideMessage.restart()
        Timer { id: hideMessage; interval: 8000; onTriggered: message.text = "" }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: Kirigami.Units.largeSpacing
        anchors.leftMargin: Kirigami.Units.largeSpacing     // none on the right: the scroll bar sits at the edge, as on the pages of Plasma
        spacing: Kirigami.Units.largeSpacing

        Tabs {
            Layout.rightMargin: Kirigami.Units.largeSpacing
            model: [{ text: i18n("Front Camera"), icon: "camera-web-symbolic" }, { text: i18n("Rear Camera"), icon: "camera-photo-symbolic" }]
            current: root.cam === "front" ? 0 : 1
            onChosen: index => root.cam = index === 0 ? "front" : "rear"
        }

        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: root.wide ? 2 : 1
            columnSpacing: Kirigami.Units.gridUnit
            rowSpacing: Kirigami.Units.largeSpacing

            // ---------------- the preview: always in view ----------------
            ColumnLayout {
                id: stage
                Layout.fillWidth: true
                Layout.fillHeight: root.wide
                Layout.alignment: Qt.AlignTop
                Layout.preferredWidth: Kirigami.Units.gridUnit * 24
                spacing: Kirigami.Units.largeSpacing

                Item {
                    id: frame
                    // 4:3, as wide as the column; on a narrow window at most about 40% of the height, the rest is for the adjustments
                    readonly property real room: root.wide ? stage.height - below.implicitHeight - stage.spacing : root.height * 0.4
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: Math.max(Kirigami.Units.gridUnit * 8, Math.min(stage.width, room * 4 / 3))
                    Layout.preferredHeight: Layout.preferredWidth * 3 / 4
                    PreviewItem {
                        id: preview
                        anchors.fill: parent
                    }
                    QQC2.Label {
                        anchors.centerIn: parent
                        width: parent.width - 2 * Kirigami.Units.largeSpacing
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        color: "white"
                        visible: !preview.hasFrame
                        text: preview.error.length > 0 ? preview.error : (preview.running ? i18n("Starting the camera…") : i18n("Live preview is off"))
                    }
                    QQC2.RoundButton {
                        anchors { right: parent.right; bottom: parent.bottom; margins: Kirigami.Units.smallSpacing }
                        icon.name: preview.running ? "media-playback-pause" : "media-playback-start"
                        onClicked: preview.running ? preview.stop() : root.startPreview()
                        QQC2.ToolTip.text: preview.running ? i18n("Pause the preview. While it runs other apps cannot use this camera.") : i18n("Start the preview")
                        QQC2.ToolTip.visible: hovered
                    }
                }
                Loader { id: below; Layout.fillWidth: true; active: root.wide; visible: active; sourceComponent: sizeAndPresets }
                Item { Layout.fillHeight: true; visible: root.wide }
            }

            // ---------------- everything that can be changed: scrolls on its own ----------------
            QQC2.ScrollView {
                id: scroll
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: Kirigami.Units.gridUnit * 22
                Layout.maximumWidth: root.wide ? Kirigami.Units.gridUnit * 28 : -1
                contentWidth: availableWidth
                QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff

                ColumnLayout {
                    width: scroll.availableWidth - Kirigami.Units.largeSpacing     // a gap between the cards and the scroll bar
                    spacing: Kirigami.Units.largeSpacing

                    // on a narrow window there is no room under the preview: the picture size and the presets come first here
                    Loader { Layout.fillWidth: true; active: !root.wide; visible: active; sourceComponent: sizeAndPresets }

                    Section {
                        title: i18n("Focus")
                        visible: root.cam === "rear"
                        Check {
                            text: i18n("Manual focus")
                            help: i18n("Off: the camera focuses by itself. On: the lens stays where you put it, in every app, starting from where the autofocus is now.")
                            checked: root.s.focusManual === true
                            onToggled: { const value = checked; root.setLocal("focusManual", value); root.cmd("action", ["set", "focusManual", value ? "1" : "0"]) }
                        }
                        Adjust {
                            stacked: true
                            id: lens          // not "focus": inside a button that name is the button's own keyboard focus
                            label: i18n("Lens position")
                            help: i18n("0 is far away, 1023 is as close as the lens goes. Watch the sharpness meter: it is highest when the picture is in focus.")
                            enabled: root.s.focusManual === true
                            from: 0; to: 1023; step: 1
                            showReset: false
                            value: root.s.focusManual ? (root.s.focus || 0) : (root.d.focus.focus !== undefined ? root.d.focus.focus : 0)
                            onEdited: v => root.edit("focus", v)
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            enabled: root.s.focusManual === true
                            Repeater {
                                model: [-50, -5, 5, 50]
                                delegate: QQC2.Button {
                                    Layout.fillWidth: true
                                    text: modelData > 0 ? "+" + modelData : String(modelData)
                                    onClicked: root.edit("focus", Math.max(0, Math.min(1023, Math.round(lens.value) + modelData)))
                                }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            QQC2.Label { text: i18n("Sharpness meter"); Layout.fillWidth: true }
                            QQC2.ProgressBar {
                                Layout.preferredWidth: Kirigami.Units.gridUnit * 9
                                from: 0; to: 1
                                value: root.d.focus.sharpness !== undefined ? Math.min(1, root.d.focus.sharpness / root.peak) : 0
                            }
                        }
                    }

                    Repeater {
                        model: root.d.controls
                        delegate: Section {
                            title: modelData.group
                            Repeater {
                                model: modelData.items
                                delegate: Adjust {
                                    stacked: true
                                    readonly property var it: modelData
                                    label: it.label
                                    help: it.desc
                                    from: it.min; to: it.max; step: it.step
                                    neutral: it.default
                                    unit: it.unit || ""
                                    names: it.names || null
                                    value: root.s[it.key] !== undefined ? root.s[it.key] : it.default
                                    onEdited: v => root.edit(it.key, v)
                                    onReset: { root.setLocal(it.key, it.default); root.cmd("set", ["reset", it.key]) }
                                }
                            }
                        }
                    }

                    Section {
                        title: i18n("Geometry")
                        Check {
                            text: i18n("Mirror (left-right)")
                            help: i18n("Done in the sensor, so it costs nothing. It is read when a camera starts: open apps must reopen the camera.")
                            checked: root.s.mirror === true
                            onToggled: { const value = checked; preview.stop(); root.setLocal("mirror", value); root.cmd("set", ["set", "mirror", value ? "1" : "0"]); restartPreview.restart() }
                        }
                        Check {
                            text: i18n("Flip (upside-down)")
                            help: i18n("Done in the sensor, so it costs nothing. It is read when a camera starts: open apps must reopen the camera.")
                            checked: root.s.flip === true
                            onToggled: { const value = checked; preview.stop(); root.setLocal("flip", value); root.cmd("set", ["set", "flip", value ? "1" : "0"]); restartPreview.restart() }
                        }
                    }

                    QQC2.Button {
                        Layout.fillWidth: true
                        Layout.leftMargin: Kirigami.Units.largeSpacing
                        Layout.rightMargin: Kirigami.Units.largeSpacing
                        text: i18n("Reset All Adjustments")
                        icon.name: "edit-undo"
                        enabled: root.s.dirty === true
                        onClicked: root.cmd("action", ["reset"])
                    }
                    QQC2.Label {
                        Layout.fillWidth: true; wrapMode: Text.WordWrap; opacity: 0.6
                        Layout.leftMargin: Kirigami.Units.largeSpacing; Layout.rightMargin: Kirigami.Units.largeSpacing
                        font.pointSize: Kirigami.Theme.defaultFont.pointSize - 1
                        text: i18n("Changes apply to every app that uses the camera.")
                        bottomPadding: Kirigami.Units.largeSpacing
                    }
                }
            }
        }
    }
}
