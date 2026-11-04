// Screen Light in the system tray: one tap lights the face with a white frame round the screen (overdrive-screenlight).
import QtQuick
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    property bool lit: false

    Plasmoid.icon: lit ? "flashlight-on" : "flashlight-off"
    Plasmoid.title: "Screen Light"
    toolTipMainText: "Screen Light"
    toolTipSubText: lit ? "On: the screen lights your face. Tap to turn off."
                        : "Tap to light your face with the screen in a dark room."
    // always in sight, not in the hidden icons: it is needed quickly, before a call
    Plasmoid.status: PlasmaCore.Types.ActiveStatus
    preferredRepresentation: compactRepresentation

    compactRepresentation: MouseArea {
        // the tray sizes its icons from these (without them the icon had no width at all)
        implicitWidth: Kirigami.Units.iconSizes.small
        implicitHeight: Kirigami.Units.iconSizes.small
        hoverEnabled: true
        onClicked: root.run(root.lit ? "off" : "on")
        Kirigami.Icon {
            anchors.fill: parent
            source: Plasmoid.icon
            active: parent.containsMouse
        }
    }

    P5Support.DataSource {
        id: shell
        engine: "executable"
        onNewData: (source, data) => {
            if (source.indexOf("NameHasOwner") >= 0)
                root.lit = data["stdout"].indexOf("true") >= 0
            disconnectSource(source)
        }
    }

    // whether the light runs: its D-Bus name has an owner (cheap enough to ask every few seconds)
    readonly property string probe: "busctl --user call org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus NameHasOwner s org.surfaceoverdrive.ScreenLight"

    function run(command) {
        root.lit = command === "on"
        // "on" stays running as the light itself: start it detached
        if (command === "on")
            shell.connectSource("setsid -f overdrive-screenlight on >/dev/null 2>&1; sleep 1.5; " + probe)
        else
            shell.connectSource("overdrive-screenlight off; sleep 0.5; " + probe)
    }

    // the light can be turned on and off elsewhere too (the Camera app): follow it
    Timer {
        interval: 3000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: shell.connectSource(root.probe)
    }
}
