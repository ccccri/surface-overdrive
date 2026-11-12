import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(__file__)
spec = importlib.util.spec_from_file_location("patch_taskmanager", os.path.join(HERE, "..", "ci", "patch_taskmanager.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ForceQuit(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        shutil.copytree(Path(HERE) / "data" / "taskmanager-6.8.2", self.dir / "src")
        self.src = self.dir / "src"

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_patch(self):
        self.assertTrue(mod.patch(self.src))
        qml = (self.src / mod.QML).read_text()
        self.assertIn("id: forceQuitItem", qml)
        self.assertLess(qml.index("id: forceQuitItem"), qml.index("id: closeWindowItem"))
        self.assertIn("void forceQuit(qint64 pid) const;", (self.src / mod.H).read_text())
        cpp = (self.src / mod.CPP).read_text()
        self.assertIn("void Backend::forceQuit(qint64 pid) const", cpp)
        self.assertIn('"--signal=KILL"', cpp)

    def test_twice_and_other_layout(self):
        self.assertTrue(mod.patch(self.src))
        self.assertFalse(mod.patch(self.src))
        fresh = self.dir / "fresh"
        shutil.copytree(Path(HERE) / "data" / "taskmanager-6.8.2", fresh)
        q = fresh / mod.QML
        q.write_text(q.read_text().replace("id: closeWindowItem", "id: closeItem"))
        before = (fresh / mod.CPP).read_text()
        self.assertFalse(mod.patch(fresh))
        self.assertEqual((fresh / mod.CPP).read_text(), before)


if __name__ == "__main__":
    unittest.main()
