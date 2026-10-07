// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kcmutils as KCM
import org.kde.kirigami as Kirigami
import org.surfaceoverdrive.kcm

KCM.SimpleKCM {
    id: root

    property string cam: "rear"
    property var d: ({ settings: {}, controls: [], presets: [], focus: {}, sizes: [], advanced: false, node: "" })
    property real peak: 1
    readonly property var s: d.settings
    readonly property bool wide: width > Kirigami.Units.gridUnit * 45
    readonly property var activePreset: d.presets.find(p => p.current)
    property int presetIndex: 0

    // ---- talking to overdrivectl ----
    function cmd(tag, args) { kcm.call(tag, ["camera", cam].concat(args)) }
    function load() { cmd("load", ["describe"]) }
    function setLocal(key, value) { const o = {}; o[key] = value; d = Object.assign({}, d, { settings: Object.assign({}, d.settings, o) }) }
    function edit(key, value) { setLocal(key, value); pending[key] = value; sendTimer.restart() }
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
    Timer { id: restartPreview; interval: 2500; onTriggered: root.startPreview() }
    onCamChanged: { preview.stop(); peak = 1; load(); autoStart.restart() }
    Component.onCompleted: { load(); autoStart.start() }
    Component.onDestruction: preview.stop()
    onVisibleChanged: if (!visible) preview.stop()
    Timer {
        interval: 300; repeat: true; running: preview.running
        onTriggered: { root.cmd("poll", ["describe"]) }
    }
    Connections {
        target: kcm
        function onCallFinished(tag, ok, output, error) {
            if (tag !== "poll" || !ok) return
            try {
                const r = JSON.parse(output)
                root.d = Object.assign({}, root.d, { focus: r.focus })
                if (r.focus.sharpness !== undefined) root.peak = Math.max(root.peak * 0.995, r.focus.sharpness)
            } catch (e) {}
        }
    }

    component Section: Kirigami.AbstractCard {
        id: sec
        property string title
        default property alias content: body.data
        Layout.fillWidth: true
        header: Kirigami.Heading { level: 4; text: sec.title; padding: Kirigami.Units.smallSpacing }
        contentItem: ColumnLayout { id: body; spacing: Kirigami.Units.smallSpacing }
    }

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
            QQC2.TextField { id: nameField; Layout.fillWidth: true; Layout.minimumWidth: Kirigami.Units.gridUnit * 18; onAccepted: nd.accept() }
        }
        function begin(m, id, initial) { mode = m; targetId = id; nameField.text = initial; open(); nameField.forceActiveFocus(); nameField.selectAll() }
        onAccepted: {
            if (mode === "save") root.cmd("action", ["preset", "save", nameField.text])
            else if (mode === "rename") root.cmd("action", ["preset", "rename", targetId, nameField.text])
            else root.cmd("action", ["preset", "duplicate", targetId, nameField.text])
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

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        Kirigami.InlineMessage {
            id: message
            Layout.fillWidth: true
            visible: text.length > 0
            type: Kirigami.MessageType.Warning
            showCloseButton: true
        }

        RowLayout {
            Layout.fillWidth: true
            Repeater {
                model: [{ t: i18n("Front camera"), c: "front", i: "camera-web-symbolic" }, { t: i18n("Rear camera"), c: "rear", i: "camera-photo-symbolic" }]
                delegate: QQC2.Button {
                    Layout.fillWidth: true
                    text: modelData.t
                    icon.name: modelData.i
                    checkable: true
                    checked: root.cam === modelData.c
                    autoExclusive: true
                    highlighted: checked
                    onClicked: root.cam = modelData.c
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: root.wide ? 2 : 1
            columnSpacing: Kirigami.Units.gridUnit * 1.5
            rowSpacing: Kirigami.Units.largeSpacing

            // ---------------- left: preview and presets ----------------
            ColumnLayout {
                Layout.alignment: Qt.AlignTop
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                Item {
                    Layout.fillWidth: true
                    Layout.maximumWidth: Kirigami.Units.gridUnit * 30
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredHeight: width * 3 / 4
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
                        text: preview.error.length > 0 ? preview.error : (preview.running ? i18n("Starting the camera...") : i18n("Live preview is off"))
                    }
                }
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    QQC2.Button {
                        text: preview.running ? i18n("Pause preview") : i18n("Start preview")
                        icon.name: preview.running ? "media-playback-pause" : "media-playback-start"
                        onClicked: preview.running ? preview.stop() : root.startPreview()
                    }
                }
                QQC2.Label {
                    Layout.fillWidth: true; wrapMode: Text.WordWrap; opacity: 0.6
                    text: i18n("Changes apply to every app using the %1 camera. While the preview runs other apps cannot use this camera: pause it before a video call.", root.cam === "front" ? i18n("front") : i18n("rear"))
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
                            text: i18n("Save as..."); icon.name: "document-save-as"
                            onClicked: nameDialog.begin("save", "", "")
                        }
                        QQC2.Button {
                            text: i18n("More"); icon.name: "view-more-symbolic"
                            enabled: root.d.presets.length > 0
                            onClicked: moreMenu.popup()
                            QQC2.Menu {
                                id: moreMenu
                                readonly property var p: root.d.presets.length > 0 ? root.d.presets[Math.min(root.presetIndex, root.d.presets.length - 1)] : ({ id: "", name: "" })
                                QQC2.MenuItem {
                                    text: i18n("Update with the current settings..."); icon.name: "document-save"
                                    onTriggered: { confirmDialog.text = i18n("Replace the settings stored in \"%1\" with the current ones?", moreMenu.p.name); confirmDialog.run = () => root.cmd("action", ["preset", "save", moreMenu.p.name, "overwrite"]); confirmDialog.open() }
                                }
                                QQC2.MenuItem { text: i18n("Rename..."); icon.name: "edit-rename"; onTriggered: nameDialog.begin("rename", moreMenu.p.id, moreMenu.p.name) }
                                QQC2.MenuItem { text: i18n("Duplicate..."); icon.name: "edit-copy"; onTriggered: nameDialog.begin("duplicate", moreMenu.p.id, i18n("%1 copy", moreMenu.p.name)) }
                                QQC2.MenuSeparator {}
                                QQC2.MenuItem {
                                    text: i18n("Delete..."); icon.name: "edit-delete"
                                    onTriggered: { confirmDialog.text = i18n("Delete the preset \"%1\"? This cannot be undone.", moreMenu.p.name); confirmDialog.run = () => root.cmd("action", ["preset", "delete", moreMenu.p.id]); confirmDialog.open() }
                                }
                            }
                        }
                    }
                    QQC2.Label {
                        Layout.fillWidth: true; elide: Text.ElideRight; opacity: 0.7
                        text: root.activePreset ? i18n("Current settings = \"%1\"", root.activePreset.name) : i18n("Current settings do not match a preset")
                    }
                }

                QQC2.Switch {
                    text: i18n("Show expert controls")
                    checked: root.d.advanced
                    onToggled: { root.d = Object.assign({}, root.d, { advanced: checked }); root.cmd("set-ui", ["ui", "camAdvanced", checked ? "1" : "0"]) }
                }
            }

            // ---------------- right: the adjustments ----------------
            ColumnLayout {
                Layout.alignment: Qt.AlignTop
                Layout.fillWidth: true
                Layout.preferredWidth: root.wide ? Kirigami.Units.gridUnit * 22 : -1
                Layout.maximumWidth: root.wide ? Kirigami.Units.gridUnit * 26 : -1
                spacing: Kirigami.Units.largeSpacing

                Section {
                    title: i18n("Focus")
                    visible: root.cam === "rear"
                    RowLayout {
                        Layout.fillWidth: true
                        QQC2.Label { text: i18n("Manual focus"); font.bold: true; Layout.fillWidth: true }
                        QQC2.Switch {
                            checked: root.s.focusManual === true
                            onToggled: { root.setLocal("focusManual", checked); root.cmd("action", ["set", "focusManual", checked ? "1" : "0"]) }
                        }
                    }
                    QQC2.Label {
                        Layout.fillWidth: true; wrapMode: Text.WordWrap; opacity: 0.6
                        text: root.s.focusManual ? i18n("The lens stays where you put it in every app until you switch back to automatic focus.")
                                                 : i18n("Automatic focus is on. Switch to manual to place the lens yourself; it starts from where the autofocus is now.")
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        QQC2.Label { text: i18n("Lens position"); Layout.fillWidth: true }
                        QQC2.Label { text: Math.round(focusSlider.value) + " / 1023"; opacity: 0.7 }
                    }
                    QQC2.Slider {
                        id: focusSlider
                        Layout.fillWidth: true
                        Layout.preferredHeight: Kirigami.Units.gridUnit * 2.6
                        enabled: root.s.focusManual === true
                        from: 0; to: 1023; stepSize: 1
                        onMoved: root.edit("focus", value)
                    }
                    Binding {
                        target: focusSlider; property: "value"
                        value: root.s.focusManual ? (root.s.focus || 0) : (root.d.focus.focus !== undefined ? root.d.focus.focus : 0)
                        when: !focusSlider.pressed
                        restoreMode: Binding.RestoreNone
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        enabled: root.s.focusManual === true
                        Repeater {
                            model: [-50, -5, 5, 50]
                            delegate: QQC2.Button {
                                Layout.fillWidth: true
                                Layout.preferredHeight: Kirigami.Units.gridUnit * 2.4
                                text: modelData > 0 ? "+" + modelData : String(modelData)
                                onClicked: { const v = Math.max(0, Math.min(1023, Math.round(focusSlider.value) + modelData)); focusSlider.value = v; root.edit("focus", v) }
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

                Section {
                    title: i18n("Output")
                    QQC2.Label { text: i18n("Picture size offered to apps"); font.bold: true }
                    QQC2.ComboBox {
                        Layout.fillWidth: true
                        model: root.d.sizes.map(x => x.text)
                        currentIndex: { for (let i = 0; i < root.d.sizes.length; i++) if (root.d.sizes[i].minWidth === root.s.minWidth) return i; return 0 }
                        onActivated: { preview.stop(); root.edit("minWidth", root.d.sizes[currentIndex].minWidth) }
                    }
                    QQC2.Label {
                        Layout.fillWidth: true; wrapMode: Text.WordWrap; opacity: 0.6
                        text: i18n("Apps take the first size offered. Smaller sizes run faster (video calls); the largest give the sharpest photos. Changing it restarts the camera service.")
                    }
                }

                Repeater {
                    model: root.d.controls
                    delegate: Section {
                        title: modelData.group
                        Repeater {
                            model: modelData.items
                            delegate: ColumnLayout {
                                id: row
                                readonly property var it: modelData
                                visible: !it.adv || root.d.advanced
                                Layout.fillWidth: true
                                spacing: 0
                                readonly property real val: root.s[it.key] !== undefined ? root.s[it.key] : it.default
                                RowLayout {
                                    Layout.fillWidth: true
                                    QQC2.Label { text: row.it.label; font.bold: true }
                                    Item { Layout.fillWidth: true }
                                    QQC2.Label {
                                        text: row.it.names ? row.it.names[Math.round(slider.value)] : (Math.round(slider.value / row.it.step) * row.it.step).toFixed(row.it.step < 1 ? 2 : 0).replace(/\.?0+$/, "") + (row.it.unit && !row.it.names ? " " + row.it.unit : "")
                                        opacity: 0.8
                                    }
                                    QQC2.ToolButton {
                                        icon.name: "edit-undo"
                                        display: QQC2.AbstractButton.IconOnly
                                        opacity: Math.abs(slider.value - row.it.default) > row.it.step / 2 ? 1 : 0
                                        enabled: opacity > 0
                                        onClicked: { slider.value = row.it.default; root.setLocal(row.it.key, row.it.default); root.cmd("set", ["reset", row.it.key]) }
                                        QQC2.ToolTip.text: i18n("Back to the default")
                                        QQC2.ToolTip.visible: hovered
                                    }
                                }
                                QQC2.Slider {
                                    id: slider
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: Kirigami.Units.gridUnit * 2
                                    from: row.it.min; to: row.it.max; stepSize: row.it.step
                                    snapMode: QQC2.Slider.SnapAlways
                                    value: row.val
                                    onMoved: root.edit(row.it.key, value)
                                }
                                QQC2.Label {
                                    Layout.fillWidth: true; wrapMode: Text.WordWrap; opacity: 0.6
                                    font.pointSize: Kirigami.Theme.defaultFont.pointSize - 1
                                    text: row.it.desc
                                    bottomPadding: Kirigami.Units.smallSpacing
                                }
                            }
                        }
                    }
                }

                Section {
                    title: i18n("Geometry")
                    RowLayout {
                        Layout.fillWidth: true
                        QQC2.Label { text: i18n("Mirror (left-right)"); font.bold: true; Layout.fillWidth: true }
                        QQC2.Switch { checked: root.s.mirror === true; onToggled: { preview.stop(); root.setLocal("mirror", checked); root.cmd("set", ["set", "mirror", checked ? "1" : "0"]); restartPreview.restart() } }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        QQC2.Label { text: i18n("Flip (upside-down)"); font.bold: true; Layout.fillWidth: true }
                        QQC2.Switch { checked: root.s.flip === true; onToggled: { preview.stop(); root.setLocal("flip", checked); root.cmd("set", ["set", "flip", checked ? "1" : "0"]); restartPreview.restart() } }
                    }
                    QQC2.Label {
                        Layout.fillWidth: true; wrapMode: Text.WordWrap; opacity: 0.6
                        text: i18n("Done in the sensor, so it costs nothing. It is read when a camera starts: open apps must reopen the camera.")
                    }
                }

                QQC2.Button {
                    text: i18n("Reset all adjustments to the tuned defaults")
                    icon.name: "edit-undo"
                    enabled: root.s.dirty === true
                    onClicked: root.cmd("action", ["reset"])
                }
            }
        }
    }
}
