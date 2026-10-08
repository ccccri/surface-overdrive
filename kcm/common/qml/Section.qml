// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// A group of settings under a heading with a line, the way the pages of Plasma separate their parts ("Playback Devices" on the
// Sound page), so that our groups and the ones of Plasma read as one page.
ColumnLayout {
    id: section

    property string title
    default property alias content: body.data

    Layout.fillWidth: true
    Layout.fillHeight: false
    spacing: 0

    Kirigami.ListSectionHeader {
        Layout.fillWidth: true
        visible: section.title.length > 0
        text: section.title
    }
    ColumnLayout {
        id: body
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        Layout.rightMargin: Kirigami.Units.largeSpacing
        Layout.bottomMargin: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.smallSpacing
    }
}
