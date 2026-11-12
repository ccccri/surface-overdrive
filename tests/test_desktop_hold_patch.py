import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(__file__)
spec = importlib.util.spec_from_file_location("patch_desktop_hold", os.path.join(HERE, "..", "ci", "patch_desktop_hold.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
DATA = Path(HERE) / "data"


class DesktopHold(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        shutil.copy(DATA / "desktopcontainment-main-6.8.2.qml", self.dir / "main.qml")
        shutil.copy(DATA / "desktopcontainment-FolderView-6.8.2.qml", self.dir / "FolderView.qml")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_patch(self):
        self.assertTrue(mod.main(str(self.dir)))
        main = (self.dir / "main.qml").read_text()
        folder = (self.dir / "FolderView.qml").read_text()
        self.assertNotIn("AfterPressAndHold", main)
        self.assertIn("interval: %d" % mod.HOLD_MS, folder)
        # moving, lifting, a cancel, a desktop change and another app's window
        self.assertEqual(folder.count("editHoldTimer.stop()"), 5)
        self.assertIn("import org.kde.taskmanager as TaskManager", folder)
        self.assertIn("TaskManager.VirtualDesktopInfo", folder)

    def test_twice_changes_nothing(self):
        mod.main(str(self.dir))
        before = [(self.dir / f).read_text() for f in ("main.qml", "FolderView.qml")]
        self.assertFalse(mod.main(str(self.dir)))
        self.assertEqual(before, [(self.dir / f).read_text() for f in ("main.qml", "FolderView.qml")])

    def test_other_layout_leaves_both(self):
        f = self.dir / "FolderView.qml"
        f.write_text(f.read_text().replace("function pressCanceled()", "function cancelPress()"))
        main_before = (self.dir / "main.qml").read_text()
        self.assertFalse(mod.main(str(self.dir)))
        self.assertEqual((self.dir / "main.qml").read_text(), main_before)


if __name__ == "__main__":
    unittest.main()
