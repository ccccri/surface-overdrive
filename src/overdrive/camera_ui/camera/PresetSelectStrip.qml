// SPDX-FileCopyrightText: 2025 Devin Lin <devin@kde.org>
// SPDX-FileCopyrightText: 2026 Surface Overdrive
// SPDX-License-Identifier: GPL-2.0-or-later
//
// Surface Overdrive: in place of Plasma Camera's exposure strip (and in its style), the photo presets saved on the
// Embedded Cameras page of System Settings: "Default" (the tuning) and every saved preset, the one in use highlighted.

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

import org.kde.kirigami as Kirigami

Item {
    id: root

    // Whether the component should be shown
    required property bool shown

    readonly property var presets: {
        try { return JSON.parse(backend.presets) } catch (e) { return [] }
    }
    readonly property bool anyCurrent: presets.some(p => p.current)

    implicitHeight: shown ? columnLayout.implicitHeight + Kirigami.Units.smallSpacing : 0
    clip: true
    onShownChanged: if (shown) backend.refreshPresets()

    Behavior on implicitHeight {
        PropertyAnimation {
            duration: Kirigami.Units.shortDuration
            easing.type: Easing.InOutCubic
        }
    }

    ColumnLayout {
        id: columnLayout
        spacing: Kirigami.Units.smallSpacing
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top

        QQC2.Label {
            Layout.topMargin: Kirigami.Units.smallSpacing
            Layout.fillWidth: true
            text: qsTr("Photo preset")
            horizontalAlignment: Text.AlignHCenter
            font.weight: Font.Bold
            font.pointSize: Kirigami.Theme.smallFont.pointSize
        }

        QQC2.ScrollView {
            id: scroller
            Layout.fillWidth: true
            Layout.preferredHeight: Kirigami.Units.gridUnit * 2.5
            QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
            contentWidth: presetRow.implicitWidth

            Row {
                id: presetRow
                // centred while the presets fit, scrolled when they do not
                x: Math.max(0, (scroller.width - implicitWidth) / 2)
                spacing: Kirigami.Units.smallSpacing

                QQC2.Button {
                    text: qsTr("Default")
                    checkable: true
                    checked: !root.anyCurrent
                    enabled: !backend.applyingSize && !backend.recording
                    onClicked: { checked = Qt.binding(() => !root.anyCurrent); backend.applyPreset(""); }
                }
                Repeater {
                    model: root.presets
                    QQC2.Button {
                        required property var modelData
                        text: modelData.name
                        checkable: true
                        checked: modelData.current
                        enabled: !backend.applyingSize && !backend.recording
                        onClicked: { checked = Qt.binding(() => modelData.current); backend.applyPreset(modelData.id); }
                    }
                }
                QQC2.Label {
                    visible: root.presets.length === 0
                    anchors.verticalCenter: parent.verticalCenter
                    leftPadding: Kirigami.Units.largeSpacing
                    color: "white"
                    opacity: 0.8
                    text: qsTr("Save presets on the Embedded Cameras page")
                }
            }
        }
    }
}
