// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// The parts of a page as a slim row of buttons that lies on the page itself, without a bar of its own under the title bar.
RowLayout {
    id: tabs

    property var model: []            // [{ text, icon }]
    property int current: 0
    signal chosen(int index)

    Layout.fillWidth: true
    Layout.fillHeight: false
    spacing: Kirigami.Units.smallSpacing

    Repeater {
        model: tabs.model
        delegate: QQC2.Button {
            Layout.fillWidth: true
            Layout.preferredWidth: 1          // equal parts whatever the text
            text: modelData.text
            icon.name: modelData.icon
            checkable: true
            autoExclusive: true
            checked: index === tabs.current
            onClicked: tabs.chosen(index)
        }
    }
}
