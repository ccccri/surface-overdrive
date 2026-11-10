import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("patch_discover", Path(__file__).resolve().parent.parent / "ci" / "patch_discover.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class DiscoverTest(unittest.TestCase):
    def tree(self, d, text=None):
        path = Path(d) / mod.REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text if text is not None else "head\n" + mod.OLD + "}\n")
        return path

    def test_repeated_download_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.tree(d)
            self.assertTrue(mod.patch(d))
            text = path.read_text()
            self.assertIn("FWUPD_ERROR_NOT_REACHABLE", text)
            self.assertIn("helper->handleError(error);", text)       # other errors still shown

    def test_another_layout_is_left_alone(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.tree(d, "void f() {}\n")
            self.assertFalse(mod.patch(d))
            self.assertEqual(path.read_text(), "void f() {}\n")

    def test_left_alone_once_discover_fixes_it(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d)
            self.assertTrue(mod.patch(d))
            self.assertFalse(mod.patch(d))

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(mod.patch(d))


if __name__ == "__main__":
    unittest.main()
