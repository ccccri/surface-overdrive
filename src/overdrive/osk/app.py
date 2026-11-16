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
DEFAULTS = {"floating": True, "x": -1, "y": -1, "scale": 1.0, "opacity": 0.96, "extras": True, "visible": True}


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
    from PySide6.QtCore import Property, QObject, QRect, QTimer, QUrl, Signal, Slot
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
            self._clips = []
            self._jobs = queue.Queue()
            self._window = None
            self._error = ""
            try:
                self.keyboard.open()
            except OSError as exc:
                self._error = "The keyboard cannot send keys (%s)." % (exc.strerror or exc)
            threading.Thread(target=self._work, daemon=True).start()
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
                        self.keyboard.type(value, held)
            self._jobs.put(job)

        def _after(self):
            self.suggestionsChanged.emit()
            if self.typing.sentence_start and not self.typing.word:
                self.shiftWanted.emit()

        # -- for the window
        def _get_error(self):
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
                self.settingsChanged.emit()
                self._save.start()

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
            self._jobs.put(lambda: self.keyboard.paste_kept(text))
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
            self.typing.words.save()
            save_settings(self.settings)
            self._jobs.put(None)
            self.keyboard.close()

    backend = Backend()
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
