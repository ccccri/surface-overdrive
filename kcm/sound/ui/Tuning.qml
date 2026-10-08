// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Dialogs
import org.kde.kirigami as Kirigami

// What this project adds to the Sound page of Plasma, in two parts that the page places where they belong:
//   speakerPart  volume boost and equalizer of the built-in output, to go under the list of playback devices
//   micPart      the improvement of the built-in microphone, to go under the list of recording devices
// Left alone (a Plasma page built differently) they simply follow each other.
ColumnLayout {
    id: root

    Layout.fillWidth: true
    spacing: 0

    property alias messagePart: message
    property alias speakerPart: speaker
    property alias micPart: microphone
    // True once the page has put the list of presets into the "Profile" selector of the device row: the lists here then go.
    property bool eqProfilesInRow: false
    property bool micProfilesInRow: false
    readonly property var eqPresets: d.presets
    readonly property var micPresets: d.mic.presets
    readonly property int eqCurrent: d.presets.findIndex(p => p.current && p.current.indexOf(editing) >= 0)
    readonly property int micCurrent: d.mic.presets.findIndex(p => p.current === true)
    function applyEqPreset(name) { audio("action", ["eq", "preset", "apply", editing, name]) }
    function applyMicPreset(name) { audio("action", ["mic", "preset", "apply", name]) }

    property var d: ({ eq: { sync: true, swap: { speaker: false, headphones: true },
                             sets: { speaker: { boost: 120, preamp: 0, bands: [] }, headphones: { boost: 100, preamp: 0, bands: [] } } },
                       active: "speaker", presets: [], mic: { available: false, running: false, values: {}, ranges: {}, defaults: {}, presets: [] },
                       output: {}, input: {}, volume_hold: "on" })
    property string editing: "speaker"
    property int sel: 4
    readonly property var cur: d.eq.sets[editing]
    readonly property var band: cur.bands[sel] || ({ type: "peak", freq: 1000, gain: 0, q: 1, on: true })
    readonly property var kindNames: ({ peak: i18n("Peak"), lowshelf: i18n("Low shelf"), highshelf: i18n("High shelf"),
                                        highpass: i18n("High-pass (low cut)"), lowpass: i18n("Low-pass (high cut)") })
    function kindsFor(i) { return i === 0 ? ["peak", "lowshelf", "highpass"] : i === 9 ? ["peak", "highshelf", "lowpass"] : ["peak"] }
    function presetAt(list, index) { return index >= 0 && index < list.length ? list[index] : null }

    // ---- talking to overdrivectl ----
    function audio(tag, args) { kcm.call(tag, ["audio"].concat(args)) }
    function load() { audio("load", ["describe"]) }
    Component.onCompleted: load()
    Timer { interval: 4000; repeat: true; running: root.visible; onTriggered: if (!sendTimer.running && !micTimer.running) root.audio("quiet", ["describe"]) }
    Connections {
        target: kcm
        function onCallFinished(tag, ok, output, error) {
            if (["load", "action", "quiet", "set"].indexOf(tag) < 0) return
            if (!ok) { if (tag !== "quiet") message.text = error || i18n("The change was not applied."); return }
            let r
            try { r = JSON.parse(output) } catch (e) { return }
            if (!r || !r.eq || !r.mic) return
            if (tag === "quiet" || tag === "set") {
                // keep what the sliders show while the user is working: only what changes by itself is refreshed
                root.d = Object.assign({}, root.d, { active: r.active, output: r.output, input: r.input, volume_hold: r.volume_hold, presets: r.presets,
                                                     mic: Object.assign({}, root.d.mic, { available: r.mic.available, running: r.mic.running, presets: r.mic.presets }) })
                return
            }
            root.d = r
            if (r.eq.sync) root.editing = "speaker"
            if (r.notes && r.notes.length > 0) message.text = r.notes.join("\n")
            else if (r.result === "invalid") message.text = i18n("Please type a name that is not one of the built-in profiles.")
            else if (r.result === false && tag === "action") message.text = i18n("That did not work.")
            else message.text = ""
        }
        function onChangeFinished(ok, msg) {
            if (!ok) message.text = msg || i18n("The change was not applied.")
            root.load()
        }
    }

    // ---- equalizer edits: stored and applied live, a moment after the last change ----
    property var pendingEq: null
    function pushEq(set) {
        const sets = Object.assign({}, d.eq.sets); sets[editing] = set
        d = Object.assign({}, d, { eq: Object.assign({}, d.eq, { sets: sets }) })
        pendingEq = { output: editing, set: set }
        sendTimer.restart()
    }
    function copyOfCurrent() { return JSON.parse(JSON.stringify(cur)) }
    function setBand(i, key, value) { const c = copyOfCurrent(); if (!c.bands[i]) return; c.bands[i][key] = value; pushEq(c) }
    function setBandPos(i, f, g) {
        const c = copyOfCurrent(); if (!c.bands[i]) return
        c.bands[i].freq = Math.round(f); c.bands[i].gain = Math.round(g * 10) / 10; pushEq(c)
    }
    function setTop(key, value) { const c = copyOfCurrent(); c[key] = value; pushEq(c) }
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

    // A line of controls that goes on to a second line when the window is too narrow for all of them, instead of pushing
    // the page wider than the window.
    component Line: Flow {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing
    }
    // the text in front of such a line, level with the controls after it
    component Caption: QQC2.Label {
        height: Math.max(implicitHeight, outputBox.implicitHeight)
        verticalAlignment: Text.AlignVCenter
    }

    component NameDialog: QQC2.Dialog {
        id: nd
        property var accepted_: null
        modal: true
        anchors.centerIn: QQC2.Overlay.overlay
        standardButtons: QQC2.Dialog.Ok | QQC2.Dialog.Cancel
        contentItem: ColumnLayout {
            QQC2.Label { text: i18n("Name:") }
            QQC2.TextField { id: nameField; Layout.fillWidth: true; Layout.minimumWidth: Kirigami.Units.gridUnit * 18; maximumLength: 60; onAccepted: nd.accept() }
        }
        function begin(t, fn) { title = t; accepted_ = fn; nameField.text = ""; open(); nameField.forceActiveFocus() }
        onAccepted: if (accepted_) accepted_(nameField.text)
    }
    NameDialog { id: eqName }
    NameDialog { id: micName }
    function localPath(url) { return decodeURIComponent(url.toString().replace(/^file:\/\//, "")) }
    FileDialog {
        id: importDialog
        title: i18n("Import an Equalizer APO / AutoEQ text file")
        nameFilters: [i18n("Text files (*.txt)"), i18n("All files (*)")]
        onAccepted: root.audio("action", ["eq", "import", root.editing, root.localPath(selectedFile)])
    }
    FileDialog {
        id: exportDialog
        title: i18n("Export as an Equalizer APO text file")
        fileMode: FileDialog.SaveFile
        nameFilters: [i18n("Text files (*.txt)")]
        onAccepted: root.audio("action", ["eq", "export", root.editing, root.localPath(selectedFile)])
    }

    Kirigami.InlineMessage {
        id: message
        Layout.fillWidth: true
        Layout.margins: visible ? Kirigami.Units.largeSpacing : 0
        visible: text.length > 0
        type: Kirigami.MessageType.Warning
        showCloseButton: true
    }

    // ================= built-in output: boost and equalizer =================
    ColumnLayout {
        id: speaker
        Layout.fillWidth: true
        Layout.fillHeight: false
        spacing: 0

        Section {
            title: i18n("Volume Boost")
            Line {
                Caption { text: i18n("Settings for:") }
                QQC2.ComboBox {
                    id: outputBox
                    width: Kirigami.Units.gridUnit * 14
                    readonly property var outputs: ["speaker", "headphones"]
                    model: [i18n("Speakers"), i18n("Headphones")].map((t, i) => t + (root.d.active === outputs[i] ? i18n(" (in use)") : ""))
                    enabled: !root.d.eq.sync
                    currentIndex: Math.max(0, outputs.indexOf(root.editing))
                    onActivated: i => root.editing = outputs[i]
                }
                Check {
                    height: outputBox.implicitHeight          // level with the list next to it
                    text: i18n("Same for both")
                    help: i18n("Use the settings of the speakers for the headphones too. Turn it off to give the headphones their own boost and equalizer, which apply by themselves when headphones are plugged in.")
                    checked: root.d.eq.sync
                    onToggled: { if (checked) root.editing = "speaker"; root.audio("action", ["eq", "sync", checked ? "on" : "off"]) }
                }
            }
            Adjust {
                onReset: edited(neutral)
                label: i18n("Volume boost")
                from: 100; to: 180; step: 1; unit: "%"; neutral: root.editing === "speaker" ? 120 : 100
                value: root.cur.boost
                onEdited: v => root.setTop("boost", v)
                help: i18n("Extra volume on top of the volume slider (100% = none). The Surface Go speakers are quiet: 120% suits them. Loud passages are held just below the maximum instead of distorting. For headphones keep it near 100%.")
            }
            Adjust {
                onReset: edited(neutral)
                label: i18n("Pre-amplifier")
                from: -24; to: 12; step: 0.5; unit: "dB"; neutral: 0
                value: root.cur.preamp
                onEdited: v => root.setTop("preamp", v)
                help: i18n("Changes the level before the equalizer. Use a negative value when raising bands a lot, to keep the loud passages clean.")
            }
            Check {
                text: root.editing === "headphones" ? i18n("Swap left and right on the headphones") : i18n("Swap left and right on the speakers")
                help: i18n("Exchanges the left and the right channel of this output. Use the Test button of the device above to hear which side is which.")
                checked: root.d.eq.swap ? root.d.eq.swap[swapOutput.target] : false
                onToggled: root.audio("action", ["eq", "swap", swapOutput.target, checked ? "on" : "off"])
                // with "Same for both" the equalizer is shared, the sides are not: this then acts on the output in use
                QtObject { id: swapOutput; readonly property string target: root.d.eq.sync ? root.d.active : root.editing }
            }
            Check {
                text: i18n("Holding a volume button keeps changing the volume")
                help: i18n("The volume buttons of the Surface Go send one step per press by default. With this on, holding a button repeats. Asks for your password.")
                checked: root.d.volume_hold === "on"
                enabled: root.d.volume_hold !== "unavailable" && !kcm.busy
                onToggled: kcm.changeSetting("volume-hold", checked ? "on" : "off")
            }
        }

        Section {
            title: i18n("Equalizer")
            Line {
                Caption { text: i18n("Profile:"); visible: !root.eqProfilesInRow }
                ProfileBox {
                    visible: !root.eqProfilesInRow
                    presets: root.eqPresets; current: root.eqCurrent
                    onChosen: name => root.applyEqPreset(name)
                }
                QQC2.Button {
                    text: i18n("Save As…"); icon.name: "document-save-as"
                    onClicked: eqName.begin(i18n("Save the current equalizer as a profile"), n => root.audio("action", ["eq", "preset", "save", n, root.editing]))
                }
                QQC2.Button {
                    icon.name: "edit-delete"; display: QQC2.AbstractButton.IconOnly
                    text: i18n("Delete This Profile")
                    readonly property var preset: root.presetAt(root.d.presets, root.eqCurrent)
                    enabled: preset !== null && !preset.builtin
                    onClicked: root.audio("action", ["eq", "preset", "delete", preset.name])
                    QQC2.ToolTip.text: text; QQC2.ToolTip.visible: hovered; QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                }
                QQC2.Button {
                    text: i18n("Reset"); icon.name: "edit-reset"
                    onClicked: root.audio("action", ["eq", "flat", root.editing])
                    QQC2.ToolTip.text: i18n("All ten bands back to flat. The boost and the pre-amplifier stay as they are.")
                    QQC2.ToolTip.visible: hovered; QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                }
            }
            EqGraph {
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 13
                bands: root.cur.bands
                selected: root.sel
                onBandSelected: i => root.sel = i
                onBandMoved: (i, f, g) => root.setBandPos(i, f, g)
            }
            Line {
                Caption { text: i18n("Band %1:", root.sel + 1) }
                QQC2.ComboBox {
                    width: Kirigami.Units.gridUnit * 12
                    model: root.kindsFor(root.sel).map(k => root.kindNames[k])
                    enabled: count > 1
                    currentIndex: Math.max(0, root.kindsFor(root.sel).indexOf(root.band.type))
                    onActivated: i => root.setBand(root.sel, "type", root.kindsFor(root.sel)[i])
                }
                Check {
                    height: outputBox.implicitHeight          // level with the list next to it
                    text: i18n("Active")
                    help: i18n("Turn the band off to hear the sound without it.")
                    checked: root.band.on
                    onToggled: root.setBand(root.sel, "on", checked)
                }
                QQC2.Button {
                    text: i18n("Play a Sweep"); icon.name: "media-playback-start"
                    onClicked: kcm.call("play", ["audio", "play", "sweep"])
                    QQC2.ToolTip.text: i18n("A tone that rises from 40 Hz to 16 kHz, to hear where the speakers rattle or fade")
                    QQC2.ToolTip.visible: hovered; QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                }
                QQC2.Button {
                    icon.name: "media-playback-stop"; display: QQC2.AbstractButton.IconOnly
                    text: i18n("Stop")
                    onClicked: kcm.call("stop", ["audio", "stop"])
                    QQC2.ToolTip.text: text; QQC2.ToolTip.visible: hovered; QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                }
                QQC2.Button { text: i18n("Import…"); icon.name: "document-import"; enabled: kcm.startTab !== "stress"; onClicked: importDialog.open() }
                QQC2.Button { text: i18n("Export…"); icon.name: "document-export"; enabled: kcm.startTab !== "stress"; onClicked: exportDialog.open() }
            }
            Adjust {
                label: i18n("Frequency"); help: i18n("Where the band acts: low numbers are bass, high numbers treble."); from: 20; to: 20000; step: 1; unit: "Hz"; showReset: false
                value: root.band.freq
                onEdited: v => root.setBand(root.sel, "freq", v)
            }
            Adjust {
                onReset: edited(neutral)
                label: i18n("Gain"); help: i18n("How much the band raises (positive) or lowers (negative) the sound around its frequency."); from: -15; to: 15; step: 0.5; unit: "dB"; neutral: 0
                value: root.band.gain
                onEdited: v => root.setBand(root.sel, "gain", v)
            }
            Adjust {
                onReset: edited(neutral)
                label: i18n("Width (Q)"); help: i18n("How narrow the band is: a high number changes only the sound right at the frequency, a low one a wide range around it."); from: 0.2; to: 10; step: 0.1; unit: ""; neutral: 1
                value: root.band.q
                onEdited: v => root.setBand(root.sel, "q", v)
            }
        }
    }

    // ================= built-in microphone =================
    ColumnLayout {
        id: microphone
        Layout.fillWidth: true
        Layout.fillHeight: false
        spacing: 0

        Section {
            title: i18n("Microphone Enhancement")
            Check {
                text: i18n("Improve the built-in microphone")
                help: i18n("Adds noise suppression and a small equalizer to the built-in microphone. Every app that records from it gets the improved sound.")
                checked: root.d.mic.available
                onToggled: root.audio("action", ["mic", checked ? "enable" : "disable"])
            }
            ColumnLayout {
                Layout.fillWidth: true
                enabled: root.d.mic.available
                spacing: Kirigami.Units.smallSpacing
                Line {
                    Caption { text: i18n("Profile:"); visible: !root.micProfilesInRow }
                    ProfileBox {
                        visible: !root.micProfilesInRow
                        presets: root.micPresets; current: root.micCurrent
                        onChosen: name => root.applyMicPreset(name)
                    }
                    QQC2.Button {
                        text: i18n("Save As…"); icon.name: "document-save-as"
                        onClicked: micName.begin(i18n("Save the microphone settings as a profile"), n => root.audio("action", ["mic", "preset", "save", n]))
                    }
                    QQC2.Button {
                        icon.name: "edit-delete"; display: QQC2.AbstractButton.IconOnly
                        text: i18n("Delete This Profile")
                        readonly property var preset: root.presetAt(root.d.mic.presets, root.micCurrent)
                        enabled: preset !== null && !preset.builtin
                        onClicked: root.audio("action", ["mic", "preset", "delete", preset.name])
                        QQC2.ToolTip.text: text; QQC2.ToolTip.visible: hovered; QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                    }
                    QQC2.Button {
                        id: recordButton
                        // 0 idle, 5..1 recording (seconds left), -1 playing back
                        property int phase: 0
                        text: phase > 0 ? i18n("Recording: Speak Now (%1)", phase) : phase < 0 ? i18n("Playing It Back…") : i18n("Record 5 Seconds and Play Back")
                        icon.name: phase < 0 ? "media-playback-start" : "media-record"
                        enabled: phase === 0
                        onClicked: { phase = 5; recordTick.start(); kcm.call("record", ["audio", "record"]) }
                        Timer { id: recordTick; interval: 1000; repeat: true; onTriggered: { recordButton.phase--; if (recordButton.phase <= 0) { recordButton.phase = -1; stop() } } }
                        Connections {
                            target: kcm
                            function onCallFinished(tag, ok, output, error) {
                                if (tag !== "record") return
                                recordTick.stop(); recordButton.phase = 0
                                if (!ok) message.text = error || i18n("The recording did not work.")
                            }
                        }
                        QQC2.ToolTip.text: i18n("Records the microphone as apps hear it, then plays it back, so you can hear what these settings do.")
                        QQC2.ToolTip.visible: hovered && phase === 0
                        QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                    }
                    QQC2.Button {
                        text: i18n("Stop"); icon.name: "media-playback-stop"
                        visible: recordButton.phase !== 0
                        onClicked: kcm.call("stop", ["audio", "stop"])
                    }
                }
                Repeater {
                    model: [{ k: "denoise", t: i18n("Noise suppression"), u: "%", s: 5, h: i18n("How much of the background noise (fans, hiss, the room) is taken out. 0% leaves the sound untouched.") },
                            { k: "gain", t: i18n("Gain"), u: "dB", s: 0.5, h: i18n("Makes your voice louder or quieter for the apps that listen.") },
                            { k: "lowcut", t: i18n("Low cut"), u: "Hz", s: 5, h: i18n("Removes everything below this frequency: rumble, bumps on the table, wind. Too high and the voice gets thin.") },
                            { k: "bass", t: i18n("Bass"), u: "dB", s: 0.5, h: i18n("The body of the voice (around 200 Hz). Raise it for a fuller voice, lower it if it booms.") },
                            { k: "presence", t: i18n("Presence"), u: "dB", s: 0.5, h: i18n("The part that makes speech easy to understand (around 3 kHz).") },
                            { k: "treble", t: i18n("Treble"), u: "dB", s: 0.5, h: i18n("The airy top of the voice (above 8 kHz). Lower it if the microphone hisses.") }]
                    delegate: Adjust {
                        onReset: edited(neutral)
                        label: modelData.t; help: modelData.h; unit: modelData.u; step: modelData.s
                        neutral: root.d.mic.defaults && root.d.mic.defaults[modelData.k] !== undefined ? root.d.mic.defaults[modelData.k] : 0
                        from: root.d.mic.ranges[modelData.k] ? root.d.mic.ranges[modelData.k][0] : 0
                        to: root.d.mic.ranges[modelData.k] ? root.d.mic.ranges[modelData.k][1] : 1
                        value: root.d.mic.values[modelData.k] !== undefined ? root.d.mic.values[modelData.k] : 0
                        onEdited: v => root.setMic(modelData.k, v)
                    }
                }
            }
        }
    }
}
