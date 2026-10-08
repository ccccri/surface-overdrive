// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Dialogs
import org.kde.kcmutils as KCM
import org.kde.kirigami as Kirigami

KCM.SimpleKCM {
    id: root

    property var d: ({ eq: { sync: true, sets: { speaker: { boost: 120, preamp: 0, bands: [] }, headphones: { boost: 100, preamp: 0, bands: [] } } },
                       active: "speaker", presets: [], mic: { available: false, running: false, values: {}, ranges: {}, presets: [] },
                       output: {}, input: {}, volume_hold: "on" })
    property string editing: "speaker"
    property int sel: 4
    property bool testing: false
    readonly property var cur: d.eq.sets[editing]
    readonly property var kindNames: ({ peak: i18n("Peak"), lowshelf: i18n("Low shelf"), highshelf: i18n("High shelf"),
                                        highpass: i18n("High-pass (low cut)"), lowpass: i18n("Low-pass (high cut)") })
    function kindsFor(i) { return i === 0 ? ["peak", "lowshelf", "highpass"] : i === 9 ? ["peak", "highshelf", "lowpass"] : ["peak"] }

    // ---- talking to overdrivectl ----
    function audio(tag, args) { kcm.call(tag, ["audio"].concat(args)) }
    function load() { audio("load", ["describe"]) }
    Component.onCompleted: { load(); editing = "speaker" }
    Timer { interval: 4000; repeat: true; running: root.visible; onTriggered: if (!sendTimer.running) root.audio("quiet", ["describe"]) }
    Connections {
        target: kcm
        function onCallFinished(tag, ok, output, error) {
            if (["load", "action", "quiet"].indexOf(tag) < 0) return
            if (!ok) { if (tag !== "quiet") message.text = error || i18n("The change was not applied."); return }
            let r
            try { r = JSON.parse(output) } catch (e) { return }
            if (tag === "quiet") {
                // keep what the sliders show while the user is working: only the mic state and the output volume are refreshed
                root.d = Object.assign({}, root.d, { active: r.active, output: r.output, input: r.input, volume_hold: r.volume_hold,
                                                     mic: Object.assign({}, root.d.mic, { available: r.mic.available, running: r.mic.running }) })
                return
            }
            root.d = r
            if (r.notes && r.notes.length > 0) message.text = r.notes.join("\n")
            else if (r.result === "invalid") message.text = i18n("Please type a name.")
            else if (r.result === false && tag === "action") message.text = i18n("That did not work.")
            else message.text = ""
            busyMic.running = false
        }
        function onChangeFinished(ok, msg) {
            if (!ok) message.text = msg || i18n("The change was not applied.")
            root.load()
        }
    }

    // ---- equaliser edits: stored and applied live, a moment after the last change ----
    property var pendingEq: null
    function pushEq(set) {
        const sets = Object.assign({}, d.eq.sets); sets[editing] = set
        d = Object.assign({}, d, { eq: Object.assign({}, d.eq, { sets: sets }) })
        pendingEq = { output: editing, set: set }
        sendTimer.restart()
    }
    function setBand(i, key, value) {
        const c = JSON.parse(JSON.stringify(cur)); c.bands[i][key] = value; pushEq(c)
    }
    function setBandPos(i, f, g) {
        const c = JSON.parse(JSON.stringify(cur)); c.bands[i].freq = Math.round(f); c.bands[i].gain = Math.round(g * 10) / 10; pushEq(c)
    }
    function setTop(key, value) { const c = JSON.parse(JSON.stringify(cur)); c[key] = value; pushEq(c) }
    Timer {
        id: sendTimer; interval: 120
        onTriggered: { const p = root.pendingEq; root.pendingEq = null; if (p) root.audio("set", ["eq", "set", p.output, JSON.stringify(p.set)]) }
    }
    // microphone
    property var pendingMic: null
    function setMic(key, value) {
        const v = Object.assign({}, d.mic.values); v[key] = value
        d = Object.assign({}, d, { mic: Object.assign({}, d.mic, { values: v }) })
        pendingMic = v; micTimer.restart()
    }
    Timer { id: micTimer; interval: 120; onTriggered: { const v = root.pendingMic; root.pendingMic = null; if (v) root.audio("set", ["mic", "set-all", JSON.stringify(v)]) } }

    component Section: Kirigami.AbstractCard {
        id: sec
        property string title
        default property alias content: body.data
        Layout.fillWidth: true
        header: Kirigami.Heading { level: 4; text: sec.title; padding: Kirigami.Units.smallSpacing }
        contentItem: ColumnLayout { id: body; spacing: Kirigami.Units.smallSpacing }
    }
    component Hint: QQC2.Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; opacity: 0.6; font.pointSize: Kirigami.Theme.defaultFont.pointSize - 1 }
    component ValueSlider: ColumnLayout {
        id: vs
        property string label
        property real from: 0
        property real to: 1
        property real step: 0.1
        property real value: 0
        property string unit: ""
        property real neutral: 0
        signal edited(real v)
        Layout.fillWidth: true
        spacing: 0
        RowLayout {
            Layout.fillWidth: true
            QQC2.Label { text: vs.label; font.bold: true }
            Item { Layout.fillWidth: true }
            QQC2.Label { text: (Math.round(sl.value / vs.step) * vs.step).toFixed(vs.step < 1 ? 1 : 0) + " " + vs.unit; opacity: 0.8 }
            QQC2.ToolButton {
                icon.name: "edit-undo"; display: QQC2.AbstractButton.IconOnly
                opacity: Math.abs(sl.value - vs.neutral) > vs.step / 2 ? 1 : 0
                enabled: opacity > 0
                onClicked: { sl.value = vs.neutral; vs.edited(vs.neutral) }
            }
        }
        QQC2.Slider {
            id: sl
            Layout.fillWidth: true
            Layout.preferredHeight: Kirigami.Units.gridUnit * 2
            from: vs.from; to: vs.to; stepSize: vs.step; snapMode: QQC2.Slider.SnapAlways
            value: vs.value
            onMoved: vs.edited(value)
        }
    }
    component NameDialog: QQC2.Dialog {
        id: nd
        property var accepted_: null
        modal: true
        anchors.centerIn: QQC2.Overlay.overlay
        standardButtons: QQC2.Dialog.Ok | QQC2.Dialog.Cancel
        contentItem: ColumnLayout {
            QQC2.Label { text: i18n("Name:") }
            QQC2.TextField { id: nameField; Layout.fillWidth: true; Layout.minimumWidth: Kirigami.Units.gridUnit * 18; onAccepted: nd.accept() }
        }
        function begin(t, fn) { title = t; accepted_ = fn; nameField.text = ""; open(); nameField.forceActiveFocus() }
        onAccepted: if (accepted_) accepted_(nameField.text)
    }
    NameDialog { id: eqName }
    NameDialog { id: micName }
    FileDialog {
        id: importDialog
        title: i18n("Import an Equalizer APO / AutoEQ text file")
        nameFilters: [i18n("Text files (*.txt)"), i18n("All files (*)")]
        onAccepted: root.audio("action", ["eq", "import", root.editing, selectedFile.toString().replace("file://", "")])
    }
    FileDialog {
        id: exportDialog
        title: i18n("Export as an Equalizer APO text file")
        fileMode: FileDialog.SaveFile
        nameFilters: [i18n("Text files (*.txt)")]
        onAccepted: root.audio("action", ["eq", "export", root.editing, selectedFile.toString().replace("file://", "")])
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        Kirigami.InlineMessage { id: message; Layout.fillWidth: true; visible: text.length > 0; type: Kirigami.MessageType.Warning; showCloseButton: true }

        // ---------------- volume buttons ----------------
        Section {
            title: i18n("Volume buttons")
            QQC2.Switch {
                text: i18n("Hold a volume button to repeat")
                checked: root.d.volume_hold === "on"
                enabled: root.d.volume_hold !== "unavailable" && !kcm.busy
                onToggled: kcm.changeSetting("volume-hold", checked ? "on" : "off")
            }
            Hint { text: i18n("The Surface Go volume buttons send one step per press by default. With this on, holding a button keeps changing the volume. Asks for your password.") }
        }

        // ---------------- test sounds ----------------
        Section {
            title: i18n("Test the speakers")
            RowLayout {
                Layout.fillWidth: true
                Repeater {
                    model: [{ t: i18n("Left"), k: "left", i: "audio-speakers" }, { t: i18n("Right"), k: "right", i: "audio-speakers" },
                            { t: i18n("Stereo"), k: "both", i: "media-playback-start" }, { t: i18n("Sweep"), k: "sweep", i: "view-media-equalizer" }]
                    delegate: QQC2.Button { Layout.fillWidth: true; text: modelData.t; icon.name: modelData.i; onClicked: kcm.call("play", ["audio", "play", modelData.k]) }
                }
                QQC2.Button { text: i18n("Stop"); icon.name: "media-playback-stop"; onClicked: kcm.call("stop", ["audio", "stop"]) }
            }
            Hint { text: i18n("Left and Right announce the channel; Stereo is a short piece that moves between the speakers; Sweep goes from 40 Hz to 16 kHz so you can hear where the speakers rattle or fade.") }
        }

        // ---------------- output ----------------
        Section {
            title: i18n("Output")
            RowLayout {
                Layout.fillWidth: true
                Repeater {
                    model: [{ t: i18n("Speakers"), o: "speaker" }, { t: i18n("Headphones"), o: "headphones" }]
                    delegate: QQC2.Button {
                        Layout.fillWidth: true
                        text: modelData.t + (root.d.active === modelData.o ? i18n("  (in use)") : "")
                        checkable: true; autoExclusive: true; highlighted: checked
                        checked: root.editing === modelData.o
                        enabled: !root.d.eq.sync || modelData.o === "speaker"
                        onClicked: root.editing = modelData.o
                    }
                }
            }
            QQC2.Switch {
                text: i18n("Use the speaker settings for the headphones too")
                checked: root.d.eq.sync
                onToggled: { if (checked) root.editing = "speaker"; root.audio("action", ["eq", "sync", checked ? "on" : "off"]) }
            }
            ValueSlider {
                label: i18n("Volume boost")
                from: 100; to: 180; step: 1; unit: "%"; neutral: 100
                value: root.cur.boost
                onEdited: v => root.setTop("boost", v)
            }
            Hint { text: i18n("The Surface Go speakers are quiet: this is extra digital volume on top of the system volume (100% = none; the default of 120% suits the speakers). For headphones keep it near 100%, or they will be too loud.") }
            ValueSlider {
                label: i18n("Pre-amplifier")
                from: -24; to: 12; step: 0.5; unit: "dB"; neutral: 0
                value: root.cur.preamp
                onEdited: v => root.setTop("preamp", v)
            }
            Hint { text: i18n("Lowers the level before the equaliser. Use a negative value when boosting bands, so loud passages do not distort.") }
        }

        Section {
            title: i18n("Equaliser")
            RowLayout {
                Layout.fillWidth: true
                QQC2.ComboBox {
                    id: presetBox
                    Layout.fillWidth: true
                    model: root.d.presets.map(p => p.name + (p.builtin ? "" : i18n("  (yours)")))
                }
                QQC2.Button {
                    text: i18n("Apply"); icon.name: "dialog-ok-apply"
                    enabled: root.d.presets.length > 0
                    onClicked: root.audio("action", ["eq", "preset", "apply", root.editing, root.d.presets[presetBox.currentIndex].name])
                }
                QQC2.Button { text: i18n("Save as..."); icon.name: "document-save-as"; onClicked: eqName.begin(i18n("Save the current equaliser as a preset"), n => root.audio("action", ["eq", "preset", "save", n, root.editing])) }
                QQC2.Button {
                    icon.name: "edit-delete"; display: QQC2.AbstractButton.IconOnly
                    enabled: root.d.presets.length > 0 && !root.d.presets[presetBox.currentIndex].builtin
                    onClicked: root.audio("action", ["eq", "preset", "delete", root.d.presets[presetBox.currentIndex].name])
                    QQC2.ToolTip.text: i18n("Delete your preset"); QQC2.ToolTip.visible: hovered
                }
            }
            RowLayout {
                Layout.fillWidth: true
                QQC2.Button { text: i18n("Import..."); icon.name: "document-import"; onClicked: importDialog.open() }
                QQC2.Button { text: i18n("Export..."); icon.name: "document-export"; onClicked: exportDialog.open() }
                Item { Layout.fillWidth: true }
            }
            EqGraph {
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 14
                bands: root.cur.bands
                selected: root.sel
                onBandSelected: i => root.sel = i
                onBandMoved: (i, f, g) => root.setBandPos(i, f, g)
            }
            Hint { text: i18n("Drag a point to change the frequency and the gain of a band; the numbers of the selected band are below.") }
            RowLayout {
                Layout.fillWidth: true
                QQC2.Label { text: i18n("Band %1", root.sel + 1); font.bold: true }
                QQC2.ComboBox {
                    Layout.fillWidth: true
                    model: root.kindsFor(root.sel).map(k => root.kindNames[k])
                    currentIndex: Math.max(0, root.kindsFor(root.sel).indexOf(root.cur.bands[root.sel] ? root.cur.bands[root.sel].type : "peak"))
                    onActivated: i => root.setBand(root.sel, "type", root.kindsFor(root.sel)[i])
                }
                QQC2.Switch { checked: root.cur.bands[root.sel] ? root.cur.bands[root.sel].on : true; onToggled: root.setBand(root.sel, "on", checked) }
            }
            ValueSlider {
                label: i18n("Frequency"); from: 20; to: 20000; step: 1; unit: "Hz"; neutral: -1
                value: root.cur.bands[root.sel] ? root.cur.bands[root.sel].freq : 1000
                onEdited: v => root.setBand(root.sel, "freq", v)
            }
            ValueSlider {
                label: i18n("Gain"); from: -15; to: 15; step: 0.5; unit: "dB"; neutral: 0
                value: root.cur.bands[root.sel] ? root.cur.bands[root.sel].gain : 0
                onEdited: v => root.setBand(root.sel, "gain", v)
            }
            ValueSlider {
                label: i18n("Width (Q)"); from: 0.2; to: 10; step: 0.1; unit: ""; neutral: 1
                value: root.cur.bands[root.sel] ? root.cur.bands[root.sel].q : 1
                onEdited: v => root.setBand(root.sel, "q", v)
            }
        }

        // ---------------- microphone ----------------
        Section {
            title: i18n("Microphone")
            RowLayout {
                Layout.fillWidth: true
                QQC2.Switch {
                    text: i18n("Improve the built-in microphone")
                    checked: root.d.mic.available
                    enabled: !busyMic.running
                    onToggled: { busyMic.running = true; root.audio("action", ["mic", checked ? "enable" : "disable"]) }
                }
                QQC2.BusyIndicator { id: busyMic; running: false; visible: running; implicitWidth: Kirigami.Units.gridUnit * 1.6; implicitHeight: implicitWidth }
            }
            Hint { text: i18n("Adds noise suppression and a small equaliser to the built-in microphone and makes it the default one. Turning it on or off restarts the sound system for a second or two.") }
            ColumnLayout {
                Layout.fillWidth: true
                enabled: root.d.mic.available
                RowLayout {
                    Layout.fillWidth: true
                    QQC2.ComboBox { id: micPreset; Layout.fillWidth: true; model: root.d.mic.presets.map(p => p.name + (p.builtin ? "" : i18n("  (yours)"))) }
                    QQC2.Button { text: i18n("Apply"); icon.name: "dialog-ok-apply"; onClicked: root.audio("action", ["mic", "preset", "apply", root.d.mic.presets[micPreset.currentIndex].name]) }
                    QQC2.Button { text: i18n("Save as..."); icon.name: "document-save-as"; onClicked: micName.begin(i18n("Save the microphone settings as a preset"), n => root.audio("action", ["mic", "preset", "save", n])) }
                    QQC2.Button {
                        icon.name: "edit-delete"; display: QQC2.AbstractButton.IconOnly
                        enabled: root.d.mic.presets.length > 0 && !root.d.mic.presets[micPreset.currentIndex].builtin
                        onClicked: root.audio("action", ["mic", "preset", "delete", root.d.mic.presets[micPreset.currentIndex].name])
                    }
                }
                Repeater {
                    model: [{ k: "gain", t: i18n("Gain"), u: "dB", s: 0.5, n: 0 }, { k: "lowcut", t: i18n("Low cut"), u: "Hz", s: 5, n: 80 },
                            { k: "bass", t: i18n("Bass"), u: "dB", s: 0.5, n: 0 }, { k: "presence", t: i18n("Presence"), u: "dB", s: 0.5, n: 0 },
                            { k: "treble", t: i18n("Treble"), u: "dB", s: 0.5, n: 0 }]
                    delegate: ValueSlider {
                        label: modelData.t; unit: modelData.u; step: modelData.s; neutral: modelData.n
                        from: root.d.mic.ranges[modelData.k] ? root.d.mic.ranges[modelData.k][0] : 0
                        to: root.d.mic.ranges[modelData.k] ? root.d.mic.ranges[modelData.k][1] : 1
                        value: root.d.mic.values[modelData.k] !== undefined ? root.d.mic.values[modelData.k] : 0
                        onEdited: v => root.setMic(modelData.k, v)
                    }
                }
                RowLayout {
                    QQC2.Button {
                        text: i18n("Record 5 seconds and play back"); icon.name: "media-record"
                        onClicked: kcm.call("record", ["audio", "record"])
                    }
                    QQC2.Button { text: i18n("Stop"); icon.name: "media-playback-stop"; onClicked: kcm.call("stop", ["audio", "stop"]) }
                }
                Hint { text: i18n("Speak while it records, then listen to the result. Gain raises or lowers the voice; Low cut removes rumble; Presence makes speech clearer.") }
            }
        }
    }
}
