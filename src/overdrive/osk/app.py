"""overdrive-osk: a floating on-screen keyboard (prototype, 2026-11-16).

What Plasma's own keyboard does not do, and the owner asked for: a keyboard that can be taken off the bottom edge and put
anywhere, with the clipboard history on it. And what came along: a row of keys a tablet lacks (Esc, Tab, Ctrl, Alt,
arrows), accents on a long press, the cursor moved by sliding on the space bar, word suggestions, emoji, sizes.

How it is made:
  - one transparent window over the whole screen (layer shell, "overlay" layer, never takes the keyboard focus), of which
    only the keyboard's rectangle takes touches (the window's input mask): moving the keyboard moves a picture inside
    that window, nothing is asked of the compositor;
  - keys go out through a virtual keyboard device (keys.py), so every application gets them as from a real keyboard;
  - it is NOT an input method: it does not know when a text field gets the focus, so it does not come up by itself. It is
    shown and hidden by its tab at the screen's edge, or by running `overdrive-osk toggle`.

usage: overdrive-osk [toggle|show|hide|quit]      (starts the keyboard when it is not running)
"""
import json
import os
import queue
import sys
import threading

from . import keys as keys_mod
from . import words as words_mod

APP_ID = "org.surfaceoverdrive.Osk"
SERVER = "overdrive-osk"
# "learn": the words typed are counted in a file to suggest them first. Off unless the user turns it on: the keyboard
# cannot tell a password field from any other, so with it on a password made of letters would be kept and offered.
# "auto": with the keyboard hidden, a touch on a text field brings it up in place of Plasma's (see stock_action). A draft,
# off by default: the rule is tested, the taking over itself was not seen working yet.
DEFAULTS = {"floating": True, "x": -1, "y": -1, "scale": 1.0, "opacity": 0.96, "extras": True, "visible": True, "learn": False,
            "auto": False}


def config_file():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "surface-overdrive", "osk.json")


def load_settings(path=None):
    out = dict(DEFAULTS)
    try:
        with open(path or config_file()) as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k, default in DEFAULTS.items():
                if isinstance(data.get(k), type(default)) or (isinstance(default, float) and isinstance(data.get(k), int)):
                    out[k] = type(default)(data[k])
    except (OSError, ValueError):
        pass
    out["scale"] = min(1.6, max(0.7, out["scale"]))
    out["opacity"] = min(1.0, max(0.4, out["opacity"]))
    return out


def save_settings(settings, path=None):
    path = path or config_file()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".new", "w") as f:
            json.dump(settings, f)
        os.replace(path + ".new", path)
    except OSError:
        pass


def system_layout(kxkbrc=None, run=None):
    """The first keyboard layout of the desktop ("us", "it"...), "" when it cannot be told: Plasma's own list when the
    user chose one, else the system's."""
    path = kxkbrc or os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "kxkbrc")
    try:
        with open(path) as f:
            for line in f:
                if line.startswith("LayoutList="):
                    first = line.split("=", 1)[1].split(",")[0].strip()
                    if first:
                        return first
    except OSError:
        pass
    try:
        import subprocess
        out = (run or subprocess.run)(["localectl", "status"], capture_output=True, text=True, timeout=3).stdout
        for line in out.splitlines():
            if "X11 Layout:" in line:
                return line.split(":", 1)[1].split(",")[0].strip()
    except (OSError, ValueError, AttributeError):
        pass
    return ""


# Windows that paste with Ctrl+Shift+V (in a terminal Ctrl+V is a control character), by the class KWin gives them.
TERMINALS = ("konsole", "yakuake", "kitty", "alacritty", "foot", "wezterm", "xterm", "gnome-terminal", "ptyxis", "ghostty", "terminator", "tilix")


def is_terminal(window_class):
    name = str(window_class or "").lower().rsplit(".", 1)[-1]
    return any(name == t or name.startswith(t + "-") for t in TERMINALS)


# Run inside KWin while the keyboard runs: it tells the keyboard which window has the focus (its class only).
KWIN_SCRIPT = """
function tell(w) { callDBus("%s", "/Osk", "%s", "active", w ? String(w.resourceClass) : ""); }
workspace.windowActivated.connect(tell);
tell(workspace.activeWindow);
""" % (APP_ID, APP_ID)
KWIN_SCRIPT_NAME = "overdrive-osk-active-window"


def stock_action(shown, auto, locked, stock_visible, stock_mode, saved_mode):
    """What to do about Plasma's own on-screen keyboard, which comes up at the bottom on a touch in a text field and
    would cover ours. Answers (mode to set or None, show ours, mode to remember or None).

      - the screen is locked: Plasma's keyboard is the one of the lock screen, ours is not there. Its mode goes back
        to what it was and nothing else is done (never leave the lock screen without a keyboard);
      - ours is shown: Plasma's is switched off (mode 0), its mode remembered;
      - ours is hidden: Plasma's gets its mode back. With "auto", when Plasma's then comes up (a text field was
        touched), ours is shown in its place.
    """
    OFF = 0
    if locked:
        # the mode stays remembered: the on-screen keyboard guard of the image switches Plasma's on at the lock and off
        # again at the unlock by itself, and ours must still know what to give back when it is hidden later
        return (saved_mode if saved_mode is not None and stock_mode == OFF else None), False, saved_mode
    if shown:
        if stock_mode != OFF:
            return OFF, False, stock_mode
        return None, False, saved_mode
    if stock_visible and auto:
        return None, True, saved_mode                     # ours comes up; the next round switches Plasma's off
    if saved_mode is not None and stock_mode == OFF:
        return saved_mode, False, None
    return None, False, saved_mode


def send_command(word):
    """word to the running keyboard; False when none runs."""
    from PySide6.QtNetwork import QLocalSocket
    sock = QLocalSocket()
    sock.connectToServer(SERVER)
    if not sock.waitForConnected(500):
        return False
    sock.write(word.encode() + b"\n")
    sock.waitForBytesWritten(500)
    sock.disconnectFromServer()
    return True


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    command = argv[0] if argv and argv[0] in ("toggle", "show", "hide", "quit") else ""
    from PySide6.QtCore import SLOT, ClassInfo, Property, QObject, QRect, QTimer, QUrl, Signal, Slot
    from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage
    from PySide6.QtGui import QGuiApplication, QRegion
    from PySide6.QtNetwork import QLocalServer
    from PySide6.QtQml import QQmlApplicationEngine

    QGuiApplication.setDesktopFileName(APP_ID)
    app = QGuiApplication(sys.argv[:1])
    if command and send_command(command):
        return 0
    if command in ("hide", "quit"):
        return 0

    class Backend(QObject):
        settingsChanged = Signal()
        suggestionsChanged = Signal()
        clipboardChanged = Signal()
        shiftWanted = Signal()                 # a sentence starts: the next letter is a capital
        command = Signal(str)
        problem = Signal(str)

        def __init__(self):
            super().__init__()
            self.settings = load_settings()
            self.keyboard = keys_mod.Keyboard()
            self.typing = words_mod.Typing(words_mod.Words(os.path.join(os.path.dirname(config_file()), "osk-words.json")))
            self.typing.words.learning = self.settings["learn"]
            self.layout = system_layout()
            self._clips = []
            self._jobs = queue.Queue()
            self._window = None
            self._error = ""
            self.terminal = False                  # the window with the focus pastes with Ctrl+Shift+V
            try:
                self.keyboard.open()
            except OSError as exc:
                self._error = "The keyboard cannot send keys (%s)." % (exc.strerror or exc)
            threading.Thread(target=self._work, daemon=True).start()
            # Plasma's own keyboard (KWin's VirtualKeyboard) and the lock state, for stock_action()
            self._bus = QDBusConnection.sessionBus()
            self._stock = QDBusInterface("org.kde.KWin", "/VirtualKeyboard", "org.kde.kwin.VirtualKeyboard", self._bus)
            self._saved_mode = None
            self._locked = self._ask_locked()
            for signal in ("visibleChanged", "modeChanged"):
                self._bus.connect("org.kde.KWin", "/VirtualKeyboard", "org.kde.kwin.VirtualKeyboard", signal, self, SLOT("stockChanged()"))
            self._bus.connect("org.freedesktop.ScreenSaver", "/ScreenSaver", "org.freedesktop.ScreenSaver", "ActiveChanged",
                              self, SLOT("lockChanged(bool)"))
            QTimer.singleShot(0, self.stockChanged)
            self._save = QTimer(self, interval=800, singleShot=True, timeout=lambda: save_settings(self.settings))

        # -- keys go out on a thread of their own: a paste waits a moment for the clipboard, the window must not
        def _work(self):
            while True:
                job = self._jobs.get()
                if job is None:
                    return
                try:
                    job()
                except (OSError, KeyError) as exc:
                    self.problem.emit(str(exc))

        def _send(self, steps, held=()):
            def job():
                for kind, value in steps:
                    if kind == "back":
                        for _ in range(value):
                            self.keyboard.tap(keys_mod.NAMED["backspace"])
                    else:
                        for step in keys_mod.plan(value):
                            if step[0] == "paste":
                                self.keyboard.paste(step[1], self.terminal)
                            else:
                                self.keyboard.tap(step[1], [keys_mod.NAMED[m] for m in held] + ([keys_mod.NAMED["shift"]] if step[2] else []))
            self._jobs.put(job)

        def _after(self):
            self.suggestionsChanged.emit()
            if self.typing.sentence_start and not self.typing.word:
                self.shiftWanted.emit()

        # -- Plasma's own keyboard
        def _ask_locked(self):
            answer = self._bus.call(QDBusMessage.createMethodCall("org.freedesktop.ScreenSaver", "/ScreenSaver",
                                                                 "org.freedesktop.ScreenSaver", "GetActive")).arguments()
            return bool(answer[0]) if answer else False

        @Slot(bool)
        def lockChanged(self, locked):
            self._locked = bool(locked)
            self.stockChanged()

        @Slot()
        def stockChanged(self):
            if not self._stock.isValid():
                return
            mode, visible = self._stock.property("mode"), self._stock.property("visible")
            if mode is None:
                return
            if os.environ.get("OSK_DEBUG"):
                print("stock", "shown", self.settings["visible"], "locked", self._locked, "visible", visible, "mode", mode, "saved", self._saved_mode, flush=True)
            set_mode, show, self._saved_mode = stock_action(self.settings["visible"], self.settings["auto"], self._locked,
                                                           bool(visible), int(mode), self._saved_mode)
            if show:
                self.settings["visible"] = True
                self.settingsChanged.emit()
                QTimer.singleShot(0, self.stockChanged)
            elif set_mode is not None:
                self._stock.setProperty("mode", set_mode)

        def release_stock(self):
            """At the end: Plasma's keyboard as it was."""
            if self._saved_mode is not None and self._stock.isValid():
                self._stock.setProperty("mode", self._saved_mode)
                self._saved_mode = None

        # -- for the window
        def _get_error(self):
            if not self._error and self.layout not in ("", "us"):
                return 'The keyboard layout is "%s": this prototype knows "us" only, some keys will type other characters.' % self.layout
            return self._error

        error = Property(str, _get_error, constant=True)

        def _get_settings(self):
            return json.dumps(self.settings)

        settingsJson = Property(str, _get_settings, notify=settingsChanged)

        @Slot(str, "QVariant")
        def setSetting(self, key, value):
            if key in DEFAULTS:
                kind = type(DEFAULTS[key])
                try:
                    self.settings[key] = kind(value)
                except (TypeError, ValueError):
                    return
                self.typing.words.learning = self.settings["learn"]
                self.settingsChanged.emit()
                self._save.start()
                if key in ("visible", "auto"):
                    self.stockChanged()

        @Slot(str, "QVariantList")
        def typeText(self, text, held):
            """Characters from the keys. With a modifier latched (Ctrl+c) nothing is followed: it is a shortcut."""
            held = [str(h) for h in held if str(h) in keys_mod.MODIFIERS and str(h) != "shift"]
            if held:
                self.typing.forget()
                self._send([("text", text)], held)
            else:
                self._send(self.typing.text(text))
            self._after()

        @Slot()
        def backspace(self):
            self._send(self.typing.backspace())
            self.suggestionsChanged.emit()

        @Slot(str, "QVariantList")
        def pressKey(self, name, held):
            """A named key (enter, tab, left...), with the latched modifiers."""
            if name not in keys_mod.NAMED:
                return
            held = [str(h) for h in held if str(h) in keys_mod.MODIFIERS]
            if name == "enter" and not held:
                self._send(self.typing.text("\n"))
            else:
                self.typing.forget()
                self._jobs.put(lambda: self.keyboard.combo(held + [name]))
            self._after()

        @Slot("QVariantList")
        def combo(self, names):
            self.typing.forget()
            names = [str(n) for n in names]
            self._jobs.put(lambda: self.keyboard.combo(names))
            self.suggestionsChanged.emit()

        def _get_suggestions(self):
            return self.typing.suggestions()

        suggestions = Property("QVariantList", _get_suggestions, notify=suggestionsChanged)

        @Slot(str)
        def pick(self, word):
            self._send(self.typing.pick(word))
            self.suggestionsChanged.emit()

        # -- the clipboard history (Plasma's Klipper)
        def _get_clips(self):
            return self._clips

        clips = Property("QVariantList", _get_clips, notify=clipboardChanged)

        @Slot()
        def refreshClips(self):
            def job():
                found = self.keyboard.clipboard.history()
                if found != self._clips:
                    self._clips = found
                    self.clipboardChanged.emit()
            self._jobs.put(job)

        @Slot(str)
        def pasteClip(self, text):
            self.typing.forget()
            terminal = self.terminal
            self._jobs.put(lambda: self.keyboard.paste_kept(text, terminal))
            self.suggestionsChanged.emit()

        # -- the part of the window that takes touches
        @Slot("QVariantList")
        def setTouchRects(self, rects):
            if self._window is None:
                return
            region = QRegion()
            for r in rects:
                region = region.united(QRegion(QRect(int(r[0]), int(r[1]), int(r[2]), int(r[3]))))
            self._window.setMask(region)

        @Slot()
        def quit(self):
            app.quit()

        def shutdown(self):
            self.release_stock()
            self.typing.words.save()
            save_settings(self.settings)
            self._jobs.put(None)
            self.keyboard.close()

    backend = Backend()

    @ClassInfo({"D-Bus Interface": APP_ID})
    class ActiveWindow(QObject):
        """What the KWin script calls. An object of its own: nothing else of the keyboard is offered on the bus."""
        @Slot(str)
        def active(self, window_class):
            backend.terminal = is_terminal(window_class)

    bus = QDBusConnection.sessionBus()
    listener = ActiveWindow()
    script_file = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/tmp", "overdrive-osk-active-window.js")
    scripting = QDBusInterface("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", bus)
    if bus.registerService(APP_ID) and bus.registerObject("/Osk", listener, QDBusConnection.ExportAllSlots):
        try:
            with open(script_file, "w") as f:
                f.write(KWIN_SCRIPT)
            scripting.call("unloadScript", KWIN_SCRIPT_NAME)
            loaded = scripting.call("loadScript", script_file, KWIN_SCRIPT_NAME).arguments()
            if loaded and int(loaded[0]) >= 0:
                QDBusInterface("org.kde.KWin", "/Scripting/Script%d" % int(loaded[0]), "org.kde.kwin.Script", bus).call("run")
        except (OSError, ValueError, TypeError):
            pass                                   # without it: Ctrl+V everywhere, as before
    app.aboutToQuit.connect(lambda: scripting.call("unloadScript", KWIN_SCRIPT_NAME))
    server = QLocalServer()
    QLocalServer.removeServer(SERVER)
    server.listen(SERVER)

    def incoming():
        sock = server.nextPendingConnection()
        sock.waitForReadyRead(300)
        word = bytes(sock.readAll()).decode("ascii", "ignore").strip()
        sock.close()
        if word == "quit":
            app.quit()
        elif word in ("toggle", "show", "hide"):
            backend.command.emit(word)
    server.newConnection.connect(incoming)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "Keyboard.qml")))
    if not engine.rootObjects():
        return 1
    backend._window = engine.rootObjects()[0]
    app.aboutToQuit.connect(backend.shutdown)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
