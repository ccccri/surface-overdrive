// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// A titled box that groups a few settings. Its height is simply the height of what is inside: the card of Kirigami works its own
// height out in a way that came out too short for some contents, and the last line then hung out of the box.
Rectangle {
    id: section

    property string title
    default property alias content: body.data

    Layout.fillWidth: true
    implicitHeight: column.implicitHeight + 2 * Kirigami.Units.largeSpacing
    implicitWidth: column.implicitWidth + 2 * Kirigami.Units.largeSpacing
    radius: Kirigami.Units.cornerRadius
    Kirigami.Theme.colorSet: Kirigami.Theme.View
    Kirigami.Theme.inherit: false
    color: Kirigami.Theme.backgroundColor
    border.width: 1
    border.color: Qt.alpha(Kirigami.Theme.textColor, 0.15)

    ColumnLayout {
        id: column
        anchors.fill: parent
        anchors.margins: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.smallSpacing

        Kirigami.Heading { level: 4; text: section.title; visible: text.length > 0; Layout.fillWidth: true; elide: Text.ElideRight }
        ColumnLayout { id: body; Layout.fillWidth: true; spacing: Kirigami.Units.smallSpacing }
    }
}
