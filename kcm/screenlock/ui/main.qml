// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "file:///usr/share/surface-overdrive/unlock" as Unlock

// "Screen Locking": the page of Plasma as it is, with "Unlock with: Password only / PIN / Pattern" added at the end of its form, in
// its columns. The PIN or pattern works on the lock screen and on the login screen; the password keeps working everywhere (see
// src/overdrive/unlock.py). Setting or removing one asks for the password of the user, through polkit.
Kirigami.Page {
    id: wrapper

    title: kcm.name
    padding: 0
    Kirigami.ColumnView.fillWidth: true
    actions: kcm.stockPage ? kcm.stockPage.actions : []        // "Configure Appearance..." of Plasma
    Bars { target: wrapper }

    property var unlock: ({ kind: "", blocked: false })   // overdrivectl unlock
    property bool working: false
    property string message: ""
    property bool messageIsError: false

    function reload() { kcm.call("state", ["unlock"]) }
    function setCode(kind, code) {
        working = true
        kcm.callWithInput("set", ["unlock", "set", kind], code + "\n")
    }
    function clearCode() {
        working = true
        kcm.call("clear", ["unlock", "clear"])
    }
    Connections {
        target: kcm
        function onCallFinished(tag, ok, output, error) {
            if (tag !== "state" && tag !== "set" && tag !== "clear") return
            let answer = null
            try { answer = JSON.parse(output) } catch (e) {}
            if (answer && answer.kind !== undefined) wrapper.unlock = answer
            if (tag === "state") return
            wrapper.working = false
            const result = answer ? answer.result : "failed"
            wrapper.messageIsError = result === "failed"
            wrapper.message = result === "done"
                ? (wrapper.unlock.kind === "pin" ? "The PIN is set. It unlocks the screen from the next lock."
                   : wrapper.unlock.kind === "pattern" ? "The pattern is set. It unlocks the screen from the next lock."
                   : "The screen unlocks with the password only.")
                : result === "cancelled" ? "" : "That did not work: " + ((answer && answer.error) || error || "unknown error")
            radios.sync()
        }
    }
    Component.onCompleted: { kcm.loadStock("kcm_screenlocker"); reload() }

    // The form of Plasma's page: ours sits right under it and is its twin, so that the labels of both share one column
    function form(item, depth) {
        if (!item || depth > 10) return null
        if (String(item).indexOf("FormLayout") >= 0) return item
        for (let i = 0; item.children && i < item.children.length; i++) {
            const found = form(item.children[i], depth + 1)
            if (found) return found
        }
        return null
    }
    property Item stockForm: null
    function twin() {
        const page = kcm.stockPage
        if (!page || stockForm) return
        try {
            const found = form(page.flickable ? page.flickable.contentItem : page, 0)
            if (!found) return
            found.twinFormLayouts = [ours]
            ours.twinFormLayouts = [found]
            stockForm = found
        } catch (e) {
            console.warn("Surface Control: could not line up with the Screen Locking page of Plasma:", e)
        }
    }
    Timer { interval: 300; repeat: true; running: kcm.stockPage !== null && wrapper.stockForm === null && tries < 10; property int tries: 0; onTriggered: { tries++; wrapper.twin() } }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.smallSpacing
            visible: wrapper.message.length > 0
            type: wrapper.messageIsError ? Kirigami.MessageType.Error : Kirigami.MessageType.Positive
            text: wrapper.message
            showCloseButton: true
            onVisibleChanged: if (!visible) wrapper.message = ""
        }
        Item {
            id: holder
            Layout.fillWidth: true
            // as high as the content of the Plasma page, so that ours follows right under its last row
            Layout.preferredHeight: page && page.flickable ? page.flickable.contentHeight + Kirigami.Units.largeSpacing : Kirigami.Units.gridUnit * 12
            readonly property Item page: kcm.stockPage
            onPageChanged: if (page) { page.parent = holder; page.anchors.fill = holder; page.visible = true; wrapper.twin() }
            Kirigami.PlaceholderMessage {
                anchors.centerIn: parent
                width: parent.width - Kirigami.Units.gridUnit * 4
                visible: kcm.stockError.length > 0
                icon.name: "dialog-warning"
                text: i18n("This page could not be loaded")
                explanation: kcm.stockError
            }
        }
        Kirigami.FormLayout {
            id: ours
            Layout.fillWidth: true
            Layout.leftMargin: Kirigami.Units.largeSpacing
            Layout.rightMargin: Kirigami.Units.largeSpacing

            Kirigami.Separator {
                Kirigami.FormData.isSection: true
            }
            QQC2.RadioButton {
                id: passwordChoice
                Kirigami.FormData.label: "Unlock with:"
                text: "Password only"
                QQC2.ButtonGroup.group: unlockGroup
                enabled: !wrapper.working
                checked: wrapper.unlock.kind === ""
                onClicked: if (wrapper.unlock.kind !== "") wrapper.clearCode(); else radios.sync()
            }
            QQC2.RadioButton {
                id: pinChoice
                text: "PIN"
                QQC2.ButtonGroup.group: unlockGroup
                enabled: !wrapper.working
                checked: wrapper.unlock.kind === "pin"
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                QQC2.ToolTip.text: "4 to 12 digits on a keypad, on the lock screen and on the login screen"
                onClicked: if (wrapper.unlock.kind !== "pin") setup.start("pin"); else radios.sync()
            }
            QQC2.RadioButton {
                id: patternChoice
                text: "Pattern"
                QQC2.ButtonGroup.group: unlockGroup
                enabled: !wrapper.working
                checked: wrapper.unlock.kind === "pattern"
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                QQC2.ToolTip.text: "A line through at least 4 of nine dots, on the lock screen and on the login screen"
                onClicked: if (wrapper.unlock.kind !== "pattern") setup.start("pattern"); else radios.sync()
            }
            QQC2.Button {
                id: changeButton
                visible: wrapper.unlock.kind !== ""
                enabled: !wrapper.working
                text: wrapper.unlock.kind === "pin" ? "Change PIN…" : "Change Pattern…"
                icon.name: "document-edit"
                onClicked: setup.start(wrapper.unlock.kind)
            }
            QQC2.Label {
                id: note
                visible: wrapper.unlock.kind !== ""
                Layout.maximumWidth: Kirigami.Units.gridUnit * 22
                wrapMode: Text.WordWrap
                font: Kirigami.Theme.smallFont
                opacity: 0.8
                text: wrapper.unlock.blocked
                      ? "Off after too many wrong tries: unlock once with the password to turn it back on."
                      : "The password still works everywhere. After five wrong tries only the password unlocks, until it is used once. "
                        + "After logging in with the " + (wrapper.unlock.kind === "pin" ? "PIN" : "pattern")
                        + ", KDE Wallet asks for the password the first time an app needs it."
            }
        }
        Item { Layout.fillHeight: true }
    }

    // ---- our rows, in the form "ours" 
    Item {
        id: radios
        visible: false
        // the buttons follow the state; a click that is cancelled (dialog closed, password not given) puts them back
        function sync() {
            passwordChoice.checked = wrapper.unlock.kind === ""
            pinChoice.checked = wrapper.unlock.kind === "pin"
            patternChoice.checked = wrapper.unlock.kind === "pattern"
        }
        Connections { target: wrapper; function onUnlockChanged() { radios.sync() } }
    }
    QQC2.ButtonGroup { id: unlockGroup }

    // ---- choosing a new PIN or pattern: twice, the second time to be sure of it
    Kirigami.Dialog {
        id: setup
        property string kind: "pin"
        property string first: ""
        property string code: ""
        property string problem: ""
        readonly property bool again: first.length > 0

        function start(newKind) {
            kind = newKind
            first = ""
            code = ""
            problem = ""
            open()
        }
        function done(entered) {
            if (!again) {
                first = entered
                code = ""
                problem = ""
                return
            }
            if (entered !== first) {
                first = ""
                code = ""
                problem = kind === "pin" ? "The two PINs were different. Start again." : "The two patterns were different. Start again."
                return
            }
            const chosen = entered
            first = ""
            code = ""
            close()
            wrapper.setCode(kind, chosen)
        }
        onRejected: radios.sync()
        onClosed: if (!wrapper.working) radios.sync()

        title: kind === "pin" ? "Choose a PIN" : "Choose a Pattern"
        standardButtons: Kirigami.Dialog.Cancel
        padding: Kirigami.Units.largeSpacing * 2
        preferredWidth: Kirigami.Units.gridUnit * 20

        ColumnLayout {
            spacing: Kirigami.Units.largeSpacing
            focus: true
            Keys.onPressed: event => {
                if (setup.kind !== "pin") return
                if (event.key === Qt.Key_Backspace) { setup.code = setup.code.slice(0, -1); event.accepted = true }
                else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { if (setup.code.length >= 4) setup.done(setup.code); event.accepted = true }
                else if (event.text.length === 1 && event.text >= "0" && event.text <= "9" && setup.code.length < 12) { setup.code += event.text; event.accepted = true }
            }
            QQC2.Label {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: setup.kind === "pin"
                      ? (setup.again ? "Type the same PIN again" : "Type a PIN of 4 to 12 digits")
                      : (setup.again ? "Draw the same pattern again" : "Draw a pattern through at least 4 dots")
            }
            QQC2.Label {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                visible: setup.problem.length > 0
                color: Kirigami.Theme.negativeTextColor
                text: setup.problem
            }
            Unlock.PinPad {
                Layout.alignment: Qt.AlignHCenter
                visible: setup.kind === "pin"
                code: setup.code
                onEdited: code => setup.code = code
                onSubmit: setup.done(setup.code)
            }
            Unlock.PatternPad {
                Layout.alignment: Qt.AlignHCenter
                visible: setup.kind === "pattern"
                onDrawn: dots => {
                    if (dots.length < 4) {
                        setup.problem = "Join at least 4 dots."
                        return
                    }
                    setup.done(dots)
                }
            }
        }
    }
}
