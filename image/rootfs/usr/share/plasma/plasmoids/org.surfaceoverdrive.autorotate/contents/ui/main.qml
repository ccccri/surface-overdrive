// SPDX-License-Identifier: MIT
import QtQuick
import org.kde.kirigami as Kirigami
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasmoid
import org.kde.plasma.plasma5support as P5Support

// One button for the panel: automatic screen rotation on or off. It changes the same setting as "Orientation" in Display
// Configuration (Automatic, only in tablet mode / Manual), through kscreen-doctor, and shows which one is in effect.
PlasmoidItem {
    id: root

    property bool on: true
    readonly property string query: "kscreen-doctor -o"

    preferredRepresentation: fullRepresentation
    Plasmoid.icon: on ? "rotation-allowed-symbolic" : "rotation-locked-portrait-symbolic"
    toolTipMainText: i18n("Auto-Rotate")
    toolTipSubText: on ? i18n("The screen turns with the tablet. Tap to lock it as it is.") : i18n("The screen stays as it is. Tap to let it turn with the tablet.")

    P5Support.DataSource {
        id: shell
        engine: "executable"
        onNewData: (source, data) => {
            disconnectSource(source)
            if (source === root.query) {
                const line = /Auto Rotate Policy:\s*(\w+)/.exec(String(data.stdout).replace(/\x1b\[[0-9;]*m/g, ""))
                if (line) root.on = line[1] !== "never"
            } else {
                shell.connectSource(root.query)        // a change was made: read back what is in effect
            }
        }
    }
    function toggle() {
        // every output that can turn by itself; the built-in screen is the only one on this tablet
        shell.connectSource("sh -c 'for o in $(kscreen-doctor -o | sed \"s/\\x1b\\[[0-9;]*m//g\" | awk \"/^Output:/{print \\$3}\"); do kscreen-doctor output.$o.autoRotatePolicy." + (on ? "never" : "inTabletMode") + "; done'")
    }
    Timer { interval: 5000; repeat: true; running: true; triggeredOnStart: true; onTriggered: shell.connectSource(root.query) }

    fullRepresentation: MouseArea {
        implicitWidth: Kirigami.Units.iconSizes.medium
        implicitHeight: Kirigami.Units.iconSizes.medium
        onClicked: root.toggle()
        Kirigami.Icon {
            anchors.fill: parent
            source: Plasmoid.icon
            active: parent.containsMouse
        }
    }
}
