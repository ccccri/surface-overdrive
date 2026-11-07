import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("patch_powerdevil", Path(__file__).resolve().parent.parent / "ci" / "patch_powerdevil.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
REL = "applets/brightness/PopupDialog.qml"


class PowerdevilTest(unittest.TestCase):
    def tree(self, d, text=None):
        path = Path(d) / REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text if text is not None else "head\n" + mod.CHANGES[REL][0][0] + "tail\n")
        return path

    def test_content_as_wide_as_the_popup(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.tree(d)
            self.assertTrue(mod.patch(d))
            self.assertIn("contentWidth: availableWidth", path.read_text())

    def test_another_layout_is_left_alone(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.tree(d, "contentItem: Something {}\n")
            self.assertFalse(mod.patch(d))
            self.assertEqual(path.read_text(), "contentItem: Something {}\n")

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(mod.patch(d))


if __name__ == "__main__":
    unittest.main()
