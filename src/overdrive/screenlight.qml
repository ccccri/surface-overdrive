// Screen light: a soft white frame round the screen, above every window, taking no input (see screenlight.py).
import QtQuick
import QtQuick.Window
import org.kde.layershell as LayerShell

Window {
    id: light
    visible: true
    color: "transparent"
    title: "Screen light"

    LayerShell.Window.scope: "overdrive-screenlight"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorTop | LayerShell.Window.AnchorBottom
                               | LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorRight
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone
    // over the panel too, and pushing nothing aside
    LayerShell.Window.exclusionZone: -1

    // slightly warm white: kinder to skin than the blue of a pure white
    readonly property color lamp: "#fff3e3"
    readonly property real band: Math.min(width, height) * 0.075
    readonly property real fade: Math.min(width, height) * 0.09

    component Edge: Rectangle {
        property bool horizontal: false
        property bool reversed: false
        color: "transparent"
        gradient: Gradient {
            orientation: horizontal ? Gradient.Horizontal : Gradient.Vertical
            GradientStop { position: 0.0; color: reversed ? "transparent" : light.lamp }
            GradientStop { position: reversed ? 1.0 - light.band / (light.band + light.fade) : light.band / (light.band + light.fade); color: light.lamp }
            GradientStop { position: 1.0; color: reversed ? light.lamp : "transparent" }
        }
    }

    Edge { anchors { top: parent.top; left: parent.left; right: parent.right } height: light.band + light.fade }
    Edge { anchors { bottom: parent.bottom; left: parent.left; right: parent.right } height: light.band + light.fade; reversed: true }
    Edge { anchors { top: parent.top; bottom: parent.bottom; left: parent.left } width: light.band + light.fade; horizontal: true }
    Edge { anchors { top: parent.top; bottom: parent.bottom; right: parent.right } width: light.band + light.fade; horizontal: true; reversed: true }

    // a gentle fade in, so it does not flash at the face
    opacity: 0
    NumberAnimation on opacity { to: 1; duration: 350; easing.type: Easing.OutCubic }
}
