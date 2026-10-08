// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kcmutils as KCM
import org.kde.kirigami as Kirigami
import org.surfaceoverdrive.kcm

KCM.SimpleKCM {
    id: root

    property var n: ({ device: true, daemon: "unknown", notifier: "unknown" })
    property var tags: []                 // newest first
    property int testTarget: 0            // taps wanted by the running test, 0 = no test
    property double testStart: 0
    readonly property var testTags: tags.filter(t => t.received >= testStart)
    readonly property bool testing: testTarget > 0 && testTags.length < testTarget

    function reload() { kcm.call("nfc", ["nfc"]) }
    Component.onCompleted: reload()
    Timer { interval: 4000; repeat: true; running: root.visible; onTriggered: root.reload() }
    Connections {
        target: kcm
        function onCallFinished(tag, ok, output, error) {
            if (tag === "nfc" && ok) { try { root.n = JSON.parse(output) } catch (e) {} }
        }
    }

    // text of one NDEF record, like the desktop notification
    function lines(records) {
        let out = []
        for (const r of records || []) {
            if (r.kind === "uri") out.push(i18n("Link: %1", r.value))
            else if (r.kind === "text") out.push(i18n("Text: %1", r.value))
            else if (r.kind === "smartposter") out = out.concat(lines(r.value))
            else if (r.kind === "mime") out.push(i18n("Data: %1", r.value))
            else if (r.kind === "external") out.push(i18n("Record: %1", r.value))
            else out.push(String(r.value))
        }
        return out
    }
    function describe(t) {
        const l = lines(t.records)
        if (t.records === null || t.records === undefined) return i18n("Card or device, no readable data")
        return l.length > 0 ? l.join("\n") : i18n("Empty or non-NDEF tag")
    }
    function stats(key) {
        const v = testTags.map(t => t[key]).filter(x => x >= 0)
        if (v.length === 0) return "-"
        return Math.min(...v) + " / " + Math.round(v.reduce((a, b) => a + b, 0) / v.length) + " / " + Math.max(...v) + " ms"
    }

    NfcMonitor {
        active: root.visible && Qt.application.state === Qt.ApplicationActive    // minimised or behind another app: let the desktop notification show
        onTag: json => {
            try {
                const t = JSON.parse(json)
                t.received = Date.now() / 1000
                t.deliverMs = Math.max(0, Math.round(t.received * 1000 - t.time * 1000))
                t.when = new Date(t.time * 1000).toLocaleTimeString()
                root.tags = [t].concat(root.tags).slice(0, 50)
            } catch (e) {}
        }
    }

    readonly property bool ready: n.device && n.daemon === "active"
    readonly property var last: tags.length > 0 ? tags[0] : null
    readonly property string lastLink: {
        const value = last && last.records && last.records[0] ? String(last.records[0].value || "") : ""
        return /^(https?:|mailto:|tel:)/.test(value) ? value : ""
    }
    // the sections bring their own margins, like the headings of the Plasma pages
    leftPadding: 0
    rightPadding: 0
    topPadding: 0

    ColumnLayout {
        spacing: 0

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.largeSpacing
            visible: !root.ready
            type: Kirigami.MessageType.Warning
            text: !root.n.device ? i18n("NFC chip not found: the nxp_nci modules are not loaded for this kernel.")
                                 : i18n("NFC chip found, but the reader service is %1.", root.n.daemon)
        }

        Section {
            title: i18n("Reader")
            QQC2.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: root.ready ? i18n("Ready. Hold a tag to the back of the tablet, behind the right corner of the screen.") : i18n("Not ready.")
            }
            QQC2.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                opacity: 0.7
                visible: root.ready
                text: i18n("While this page is in front, tags show up here instead of as desktop notifications.")
            }
        }

        Section {
            title: i18n("Last Tag")
            visible: root.last !== null
            QQC2.Label { text: root.last ? root.describe(root.last) : ""; font.bold: true; wrapMode: Text.WrapAnywhere; maximumLineCount: 8; elide: Text.ElideRight; Layout.fillWidth: true }
            Kirigami.FormLayout {
                Layout.fillWidth: true
                QQC2.Label { Kirigami.FormData.label: i18n("Type:"); text: root.last ? root.last.type : "" }
                QQC2.Label { Kirigami.FormData.label: i18n("UID:"); text: root.last ? root.last.uid : "" }
                QQC2.Label { Kirigami.FormData.label: i18n("Time:"); text: root.last ? root.last.when : "" }
                QQC2.Label { Kirigami.FormData.label: i18n("Read from the tag in:"); text: root.last && root.last.read_ms >= 0 ? root.last.read_ms + " ms" : i18n("n/a") }
                QQC2.Label { Kirigami.FormData.label: i18n("Delivered to this page in:"); text: root.last ? root.last.deliverMs + " ms" : "" }
                QQC2.Button {
                    visible: root.lastLink.length > 0
                    text: i18n("Open"); icon.name: "document-open"
                    onClicked: Qt.openUrlExternally(root.lastLink)
                }
            }
        }

        Section {
            title: i18n("Reader Test")
            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.largeSpacing
                QQC2.Button {
                    text: root.testing ? i18n("Stop Test") : i18n("Start Test (10 Taps)")
                    icon.name: root.testing ? "media-playback-stop" : "media-playback-start"
                    onClicked: {
                        if (root.testing) root.testTarget = 0
                        else { root.testStart = Date.now() / 1000; root.testTarget = 10 }
                    }
                    QQC2.ToolTip.text: i18n("Touch the same tag ten times, lifting it each time. The test shows how fast and how reliably it is read: minimum / average / maximum of the time to read the tag and of the time to reach this page.")
                    QQC2.ToolTip.visible: hovered || pressed
                    QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                }
                QQC2.Label { visible: root.testTarget > 0; text: i18n("%1 / %2 taps", root.testTags.length, root.testTarget) + (root.testing ? "" : i18n(" (done)")) }
                Item { Layout.fillWidth: true }
            }
            Kirigami.FormLayout {
                Layout.fillWidth: true
                visible: root.testTarget > 0
                QQC2.Label { Kirigami.FormData.label: i18n("Read from the tag (min / avg / max):"); text: root.stats("read_ms") }
                QQC2.Label { Kirigami.FormData.label: i18n("Delivered here (min / avg / max):"); text: root.stats("deliverMs") }
            }
        }

        Section {
            title: i18n("History")
            visible: root.tags.length > 1
            Repeater {
                model: root.tags.slice(1)
                delegate: RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing
                    QQC2.Label { text: modelData.when; opacity: 0.7 }
                    QQC2.Label { Layout.fillWidth: true; text: root.describe(modelData).replace(/\n/g, "  "); elide: Text.ElideRight }
                    QQC2.Label { text: modelData.type; opacity: 0.7 }
                }
            }
        }
    }
}
