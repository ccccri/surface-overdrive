// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// The system images on the disk: the one in use, the one before it (which can be started again), and one that waits for the
// next restart. With what differs between them, and the way back to the previous one.
ColumnLayout {
    id: root

    Layout.fillWidth: true
    spacing: 0

    property var info: ({ images: [], can_go_back: false })
    property var diff: null               // { lines, more } once asked for
    property bool busy: false
    property string note: ""
    readonly property bool hasNext: info.images.some(i => i.state === "next")

    function reload() { kcm.call("image", ["image"]) }
    Component.onCompleted: reload()
    Connections {
        target: kcm
        function onCallFinished(tag, ok, output, error) {
            if (["image", "image-changes", "image-back", "image-cancel"].indexOf(tag) < 0) return
            let r = null
            try { r = JSON.parse(output) } catch (e) {}
            if (tag === "image") { if (r && r.images) root.info = r; return }
            if (tag === "image-changes") { root.diff = r && r.lines ? r : { lines: [], more: 0 }; return }
            root.busy = false
            if (r && r.result === "ok") root.note = tag === "image-back" ? i18n("Done. The previous image starts at the next restart.") : i18n("Done. The image in use stays.")
            else root.note = i18n("That did not work: %1", (r && r.error) || error || i18n("no answer"))
            root.reload()
        }
    }

    Kirigami.ListSectionHeader { Layout.fillWidth: true; text: i18n("System Image"); visible: root.info.images.length > 0 }
    Repeater {
        model: root.info.images
        delegate: RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: Kirigami.Units.largeSpacing
            Layout.rightMargin: Kirigami.Units.largeSpacing
            Layout.bottomMargin: Kirigami.Units.smallSpacing
            spacing: Kirigami.Units.largeSpacing
            Kirigami.Icon {
                implicitWidth: Kirigami.Units.iconSizes.smallMedium; implicitHeight: implicitWidth
                source: modelData.state === "in use" ? "emblem-ok-symbolic" : modelData.state === "next" ? "system-reboot-symbolic" : "view-history-symbolic"
            }
            QQC2.Label { text: modelData.version; font.bold: modelData.state === "in use" }
            QQC2.Label {
                Layout.fillWidth: true
                elide: Text.ElideRight
                opacity: 0.7
                text: (modelData.state === "in use" ? i18n("in use") : modelData.state === "next" ? i18n("starts at the next restart") : i18n("previous"))
                      + (modelData.built ? i18n(", built %1", modelData.built) : "")
            }
            QQC2.Button {
                visible: modelData.state === "previous" && root.info.can_go_back
                enabled: !root.busy
                text: i18n("Go Back to This One…")
                icon.name: "edit-undo"
                onClicked: confirm.open()
            }
            QQC2.Button {
                visible: modelData.went_back === true
                enabled: !root.busy
                text: i18n("Undo")
                icon.name: "edit-undo"
                onClicked: { root.busy = true; root.note = ""; kcm.call("image-cancel", ["image", "cancel"]) }
                QQC2.ToolTip.text: i18n("Keep the image in use: do not go back at the next restart. Asks for your password.")
                QQC2.ToolTip.visible: hovered; QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
            }
        }
    }
    RowLayout {
        visible: root.info.images.length > 1
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        Layout.rightMargin: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.largeSpacing
        QQC2.Button {
            text: root.diff === null ? i18n("What Changed") : i18n("Hide the Changes")
            icon.name: root.diff === null ? "arrow-down" : "arrow-up"
            onClicked: { if (root.diff === null) { root.diff = { lines: [i18n("Reading…")], more: 0 }; kcm.call("image-changes", ["image", "changes"]) } else root.diff = null }
        }
        QQC2.BusyIndicator { running: root.busy; visible: running; implicitWidth: Kirigami.Units.gridUnit * 1.5; implicitHeight: implicitWidth }
        QQC2.Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; opacity: 0.7; text: root.note }
    }
    QQC2.Label {
        visible: root.diff !== null
        Layout.fillWidth: true
        Layout.margins: Kirigami.Units.largeSpacing
        wrapMode: Text.WrapAnywhere
        opacity: 0.8
        font.family: "monospace"
        text: root.diff === null ? "" : root.diff.lines.length === 0 ? i18n("The two images hold the same packages: only files of this project differ.")
              : root.diff.lines.join("\n") + (root.diff.more > 0 ? "\n" + i18n("… and %1 more", root.diff.more) : "")
    }

    QQC2.Dialog {
        id: confirm
        modal: true
        anchors.centerIn: QQC2.Overlay.overlay
        width: Math.min(Kirigami.Units.gridUnit * 28, parent ? parent.width : Kirigami.Units.gridUnit * 28)
        title: i18n("Go back to the previous image?")
        standardButtons: QQC2.Dialog.Yes | QQC2.Dialog.No
        contentItem: QQC2.Label {
            wrapMode: Text.WordWrap
            text: i18n("The previous system image will start at the next restart, and this one becomes the previous. Your files and settings stay as they are. You will be asked for your password.")
        }
        onAccepted: { root.busy = true; root.note = ""; kcm.call("image-back", ["image", "go-back"]) }
    }
}
