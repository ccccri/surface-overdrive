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
        active: root.visible
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

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: true
            type: root.n.device && root.n.daemon === "active" ? Kirigami.MessageType.Positive : Kirigami.MessageType.Warning
            text: !root.n.device ? i18n("NFC chip not found: the nxp_nci modules are not loaded for this kernel.")
                  : root.n.daemon !== "active" ? i18n("NFC chip found but the reader service is %1.", root.n.daemon)
                  : i18n("NFC reader ready. Touch a tag to the back of the tablet, at the right corner of the screen. While this page is open, tags show up here instead of as desktop notifications.")
        }

        Kirigami.Heading { level: 3; text: i18n("Last tag"); visible: root.tags.length > 0 }
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: root.tags.length > 0
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                QQC2.Label { text: root.tags.length > 0 ? root.describe(root.tags[0]) : ""; font.bold: true; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                Kirigami.FormLayout {
                    Layout.fillWidth: true
                    QQC2.Label { Kirigami.FormData.label: i18n("Type:"); text: root.tags.length > 0 ? root.tags[0].type : "" }
                    QQC2.Label { Kirigami.FormData.label: i18n("UID:"); text: root.tags.length > 0 ? root.tags[0].uid : "" }
                    QQC2.Label { Kirigami.FormData.label: i18n("Time:"); text: root.tags.length > 0 ? root.tags[0].when : "" }
                    QQC2.Label { Kirigami.FormData.label: i18n("Read from the tag in:"); text: root.tags.length > 0 && root.tags[0].read_ms >= 0 ? root.tags[0].read_ms + " ms" : i18n("n/a") }
                    QQC2.Label { Kirigami.FormData.label: i18n("Delivered to this page in:"); text: root.tags.length > 0 ? root.tags[0].deliverMs + " ms" : "" }
                }
                QQC2.Button {
                    visible: root.tags.length > 0 && /^(https?:|mailto:|tel:)/.test((root.tags[0].records && root.tags[0].records[0] && root.tags[0].records[0].value) || "")
                    text: i18n("Open"); icon.name: "document-open"
                    onClicked: Qt.openUrlExternally(root.tags[0].records[0].value)
                }
            }
        }

        Kirigami.Heading { level: 3; text: i18n("Reader test") }
        QQC2.Label {
            Layout.fillWidth: true; wrapMode: Text.WordWrap; opacity: 0.7
            text: i18n("Touch the same tag several times, lifting it each time. The test shows how fast and how reliably it is read: minimum / average / maximum of the time to read the tag and of the time to reach this page.")
        }
        RowLayout {
            QQC2.Button {
                text: root.testing ? i18n("Stop test") : i18n("Start test (10 taps)")
                icon.name: root.testing ? "media-playback-stop" : "media-playback-start"
                onClicked: {
                    if (root.testing) root.testTarget = 0
                    else { root.testStart = Date.now() / 1000; root.testTarget = 10 }
                }
            }
            QQC2.Label { visible: root.testTarget > 0; text: i18n("%1 / %2 taps", root.testTags.length, root.testTarget) + (root.testing ? "" : i18n(" - done")) }
        }
        Kirigami.FormLayout {
            Layout.fillWidth: true
            visible: root.testTarget > 0
            QQC2.Label { Kirigami.FormData.label: i18n("Read from the tag (min / avg / max):"); text: root.stats("read_ms") }
            QQC2.Label { Kirigami.FormData.label: i18n("Delivered here (min / avg / max):"); text: root.stats("deliverMs") }
        }

        Kirigami.Heading { level: 3; text: i18n("History"); visible: root.tags.length > 1 }
        Repeater {
            model: root.tags.slice(1)
            delegate: Kirigami.AbstractCard {
                Layout.fillWidth: true
                contentItem: RowLayout {
                    QQC2.Label { text: modelData.when; opacity: 0.7 }
                    QQC2.Label { Layout.fillWidth: true; text: root.describe(modelData).replace(/\n/g, "  "); elide: Text.ElideRight }
                    QQC2.Label { text: modelData.type; opacity: 0.7 }
                }
            }
        }
    }
}
