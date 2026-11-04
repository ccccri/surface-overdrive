"""Screen light: the display as a soft light for the front camera.

In a dim room the front camera runs at its longest exposure and highest gain, and the picture is mostly grain. The
tablet's own screen, half a metre from the face, is a large soft light: a white frame round the edges at full brightness
(as phones do with their front "flash" and macOS with Edge Light). Measured on the Surface Go (2026-11-04): a white
screen lowered the grain of the room behind by a quarter; on a face at 40 cm it does far more.

`overdrive-screenlight [on|off|toggle|status]`. The light is a layer-shell surface on the overlay layer (above every
window, full screen ones too) that takes no input: touches and keys go to the windows under it. While it shines the
backlight is at its brightest, and goes back to where it was when it turns off. One instance at a time, found through
its D-Bus name; "toggle" asks the running one to quit.
"""

import os
import signal
import sys

BUS_NAME = "org.surfaceoverdrive.ScreenLight"
POWER = "org.kde.Solid.PowerManagement"
BRIGHTNESS_PATH = "/org/kde/Solid/PowerManagement/Actions/BrightnessControl"
BRIGHTNESS_IFACE = "org.kde.Solid.PowerManagement.Actions.BrightnessControl"
QML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenlight.qml")


def _bus():
    from PySide6.QtDBus import QDBusConnection
    return QDBusConnection.sessionBus()


def running():
    from PySide6.QtDBus import QDBusConnectionInterface
    iface = _bus().interface()
    reply = iface.isServiceRegistered(BUS_NAME)
    return bool(reply.value()) if hasattr(reply, "value") else bool(reply)


def stop_running():
    from PySide6.QtDBus import QDBusMessage
    msg = QDBusMessage.createMethodCall(BUS_NAME, "/", "org.surfaceoverdrive.ScreenLight", "Quit")
    _bus().call(msg)


def _brightness(method, *args):
    from PySide6.QtDBus import QDBusMessage
    msg = QDBusMessage.createMethodCall(POWER, BRIGHTNESS_PATH, BRIGHTNESS_IFACE, method)
    if args:
        msg.setArguments(list(args))
    reply = _bus().call(msg)
    values = reply.arguments()
    return values[0] if values else None


def run():
    from PySide6.QtCore import QObject, QUrl, Slot, QTimer, Qt
    from PySide6.QtDBus import QDBusConnection
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine

    app = QGuiApplication(sys.argv)
    app.setApplicationName("overdrive-screenlight")
    app.setDesktopFileName("org.surfaceoverdrive.ScreenLight")

    bus = QDBusConnection.sessionBus()

    class Service(QObject):
        @Slot()
        def Quit(self):
            app.quit()

    service = Service()
    if not bus.registerService(BUS_NAME):
        print("screen light already on", file=sys.stderr)
        return 0
    bus.registerObject("/", "org.surfaceoverdrive.ScreenLight", service, QDBusConnection.ExportAllSlots)

    # brightest while it shines, back to where it was afterwards
    before = None
    try:
        before = int(_brightness("brightness"))
        top = int(_brightness("brightnessMax"))
        _brightness("setBrightness", top)
    except (TypeError, ValueError):
        before = None

    def restore():
        if before is not None:
            _brightness("setBrightness", before)

    app.aboutToQuit.connect(restore)
    signal.signal(signal.SIGTERM, lambda *a: app.quit())
    signal.signal(signal.SIGINT, lambda *a: app.quit())
    # let Python see the signals while Qt's loop runs
    tick = QTimer()
    tick.start(250)
    tick.timeout.connect(lambda: None)

    engine = QQmlApplicationEngine()
    engine.load(QUrl.fromLocalFile(QML))
    if not engine.rootObjects():
        restore()
        return 1
    # no input at all: touches and keys reach the windows under the light
    for window in engine.rootObjects():
        window.setFlag(Qt.WindowTransparentForInput, True)
    return app.exec()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    command = argv[0] if argv else "toggle"
    if command not in ("on", "off", "toggle", "status"):
        print("usage: overdrive-screenlight [on|off|toggle|status]", file=sys.stderr)
        return 2
    from PySide6.QtCore import QCoreApplication
    probe = QCoreApplication.instance() or QCoreApplication([])
    is_on = running()
    if command == "status":
        print("on" if is_on else "off")
        return 0
    if command == "off" or (command == "toggle" and is_on):
        if is_on:
            stop_running()
        return 0
    if is_on:
        return 0
    del probe
    # the light itself runs in a process of its own: the layer-shell integration must be chosen before Qt starts
    os.environ["QT_WAYLAND_SHELL_INTEGRATION"] = "layer-shell"
    os.execv(sys.executable, [sys.executable, os.path.abspath(__file__), "--run"])


if __name__ == "__main__":
    if sys.argv[1:] == ["--run"]:
        sys.exit(run())
    sys.exit(main())
