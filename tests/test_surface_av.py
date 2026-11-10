"""tools/pc-companion/surface-av: counting the apps that have the virtual camera open (the count once took an open of
surface-av's own for an app's, and the Surface's camera stayed on)."""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "tools" / "pc-companion" / "surface-av"


def load():
    loader = importlib.machinery.SourceFileLoader("surface_av", str(SCRIPT))
    spec = importlib.util.spec_from_loader("surface_av", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


try:
    import gi  # noqa: F401
    gi.require_version("Gst", "1.0")
    av = load()
except (ImportError, ValueError):
    av = None


@unittest.skipIf(av is None or not sys.platform.startswith("linux"), "needs GStreamer's Python bindings and inotify")
class Openers(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "video0")
        Path(self.path).touch()
        av.LOG = os.path.join(self.dir.name, "log")   # not the session's log

    def tearDown(self):
        self.dir.cleanup()

    def test_two_closes_in_a_row(self):
        openers = av.Openers(self.path)
        pid = os.fork()
        if pid == 0:
            a, b = open(self.path), open(self.path)
            __import__("time").sleep(0.5)
            a.close()
            b.close()                               # two identical inotify events in a row: merged into one
            os._exit(0)
        __import__("time").sleep(0.25)
        self.assertEqual(openers.poll(), 2)
        os.waitpid(pid, 0)
        self.assertEqual(openers.poll(), 0)

    def test_own_opens_are_not_apps(self):
        ours = open(self.path)                      # the writer, open before the count starts
        openers = av.Openers(self.path)
        self.assertEqual(openers.poll(), 0)
        again = open(self.path)                     # the writer opening it a second time later
        self.assertEqual(openers.poll(), 0)
        again.close()
        ours.close()
        self.assertEqual(openers.poll(), 0)

    def test_an_app_opens_and_closes(self):
        openers = av.Openers(self.path)
        pid = os.fork()
        if pid == 0:                                # the "app": another process
            f = open(self.path)
            __import__("time").sleep(0.5)
            f.close()
            os._exit(0)
        __import__("time").sleep(0.25)
        self.assertEqual(openers.poll(), 1)
        os.waitpid(pid, 0)
        self.assertEqual(openers.poll(), 0)


if __name__ == "__main__":
    unittest.main()
