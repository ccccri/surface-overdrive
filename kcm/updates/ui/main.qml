// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Dialogs
import QtCore
import org.kde.kirigami as Kirigami

// "Software Update": first the state of what the system image adds for the Surface (kernel patches, modules and the other fixes),
// which is what one comes to look at; under it the page of Plasma, which only holds how and how often updates are fetched.
Kirigami.Page {
    id: wrapper

    title: kcm.name
    padding: 0
    // A page that the Plasma page opens on top of itself takes the whole view with a way back, as it does in Plasma.
    Kirigami.ColumnView.fillWidth: true
    Component.onCompleted: kcm.loadStock("kcm_updates")
    Bars { target: wrapper }
    actions: [
        Kirigami.Action {
            text: i18n("Check Again")
            icon.name: "view-refresh"
            enabled: !kcm.busy
            onTriggered: kcm.refresh()
        },
        Kirigami.Action {
            text: i18n("Export Surface Settings…")
            icon.name: "document-export"
            displayHint: Kirigami.DisplayHint.AlwaysHide
            onTriggered: {
                exportDialog.selectedFile = StandardPaths.writableLocation(StandardPaths.DocumentsLocation) + "/surface-settings-" + Qt.formatDate(new Date(), "yyyy-MM-dd") + ".json"
                exportDialog.open()
            }
        },
        Kirigami.Action {
            text: i18n("Import Surface Settings…")
            icon.name: "document-import"
            displayHint: Kirigami.DisplayHint.AlwaysHide
            onTriggered: importDialog.open()
        },
        Kirigami.Action {
            text: i18n("Report a Problem…")
            icon.name: "tools-report-bug"
            displayHint: Kirigami.DisplayHint.AlwaysHide
            onTriggered: reportDialog.open()
        }
    ]

    // ---- settings in and out, and the report: each tells what it did in the message at the top ----
    property string pendingImport: ""
    property bool canUndo: false
    function localPath(url) { return decodeURIComponent(url.toString().replace(/^file:\/\//, "")) }
    function say(text, type) { message.type = type || Kirigami.MessageType.Positive; message.text = text }
    FileDialog {
        id: exportDialog
        title: i18n("Save the Surface settings in a file")
        fileMode: FileDialog.SaveFile
        defaultSuffix: "json"
        nameFilters: [i18n("Surface settings (*.json)")]
        currentFolder: StandardPaths.writableLocation(StandardPaths.DocumentsLocation)
        onAccepted: kcm.call("export", ["settings", "export", wrapper.localPath(selectedFile)])
    }
    FileDialog {
        id: importDialog
        title: i18n("Choose a Surface settings file")
        nameFilters: [i18n("Surface settings (*.json)"), i18n("All files (*)")]
        currentFolder: StandardPaths.writableLocation(StandardPaths.DocumentsLocation)
        onAccepted: { wrapper.pendingImport = wrapper.localPath(selectedFile); kcm.call("inspect", ["settings", "inspect", wrapper.pendingImport]) }
    }
    QQC2.Dialog {
        id: importConfirm
        property var contents: []
        modal: true
        anchors.centerIn: QQC2.Overlay.overlay
        width: Math.min(Kirigami.Units.gridUnit * 28, wrapper.width)
        title: i18n("Replace the settings with the ones of this file?")
        standardButtons: QQC2.Dialog.Yes | QQC2.Dialog.No
        contentItem: QQC2.Label {
            wrapMode: Text.WordWrap
            text: i18n("The file holds:") + "\n• " + importConfirm.contents.join("\n• ") + "\n\n" + i18n("The settings of now are kept aside, so this can be undone.")
        }
        onAccepted: kcm.call("import", ["settings", "import", wrapper.pendingImport])
    }
    QQC2.Dialog {
        id: reportDialog
        modal: true
        anchors.centerIn: QQC2.Overlay.overlay
        width: Math.min(Kirigami.Units.gridUnit * 30, wrapper.width)
        title: i18n("Report a problem")
        standardButtons: QQC2.Dialog.Ok | QQC2.Dialog.Cancel
        contentItem: QQC2.Label {
            wrapMode: Text.WordWrap
            text: i18n("This writes a report into your Documents folder: the state of the fixes, the system images, and the recent log of the services of this project, of the sound and camera services and of crashes. User name, computer name and network addresses are taken out.\n\nThen the page for a new report on GitHub opens in the browser. Drag the report file into it and describe what happened. Reports on GitHub are public: have a look at the file first if you are not sure.")
        }
        onAccepted: kcm.call("report", ["report"])
    }
    Connections {
        target: kcm
        function onCallFinished(tag, ok, output, error) {
            if (["export", "inspect", "import", "undo", "report"].indexOf(tag) < 0) return
            let r = null
            try { r = JSON.parse(output) } catch (e) {}
            if (!r) { wrapper.say(error || i18n("That did not work."), Kirigami.MessageType.Error); return }
            if (r.result !== "ok") { wrapper.say(r.error || i18n("That did not work."), Kirigami.MessageType.Error); return }
            if (tag === "export") wrapper.say(i18n("Settings saved in %1", r.path))
            else if (tag === "inspect") { importConfirm.contents = r.contents; importConfirm.open() }
            else if (tag === "import") { wrapper.canUndo = true; wrapper.say(i18n("Settings imported and applied.")) }
            else if (tag === "undo") { wrapper.canUndo = false; wrapper.say(i18n("The settings are back as they were before the import.")) }
            else if (tag === "report") { wrapper.say(i18n("Report written to %1. Attach it to the page that opened in the browser.", r.path)); Qt.openUrlExternally(r.url) }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Kirigami.InlineMessage {
            id: message
            Layout.fillWidth: true
            Layout.margins: visible ? Kirigami.Units.largeSpacing : 0
            visible: text.length > 0
            showCloseButton: true
            actions: [
                Kirigami.Action {
                    text: i18n("Undo the Import")
                    icon.name: "edit-undo"
                    visible: wrapper.canUndo
                    onTriggered: kcm.call("undo", ["settings", "undo"])
                }
            ]
        }
        QQC2.ScrollView {
            id: scroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: availableWidth
            QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
            ColumnLayout {
                width: scroll.availableWidth
                spacing: 0
                Health { }
                SystemImage { }
            }
        }
        Kirigami.ListSectionHeader {
            Layout.fillWidth: true
            visible: kcm.stockPage !== null
            text: i18n("Updates")
        }
        Item {
            id: holder
            Layout.fillWidth: true
            // the page of Plasma is a short form: it gets the height of its content, at most half of the page
            Layout.preferredHeight: !page ? (kcm.stockError.length > 0 ? Kirigami.Units.gridUnit * 6 : 0)
                                    : Math.min(wrapper.height * 0.3, (page.flickable ? page.flickable.contentHeight : Kirigami.Units.gridUnit * 8) + Kirigami.Units.largeSpacing * 2)
            readonly property Item page: kcm.stockPage
            onPageChanged: if (page) { page.parent = holder; page.anchors.fill = holder; page.visible = true }
            QQC2.Label {
                anchors.centerIn: parent
                width: parent.width - Kirigami.Units.gridUnit * 4
                visible: kcm.stockError.length > 0
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                opacity: 0.7
                text: i18n("The update settings of Plasma could not be loaded: %1", kcm.stockError)
            }
        }
    }
}
