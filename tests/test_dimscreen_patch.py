import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("patch_dimscreen", Path(__file__).resolve().parent.parent / "ci" / "patch_dimscreen.py")
patch_dimscreen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch_dimscreen)

STOCK = "    startAnimation: function (window) {\n" + patch_dimscreen.ANCHOR + "    }\n"


class DimScreenPatch(unittest.TestCase):
    def test_keyboard_left_bright_once(self):
        once = patch_dimscreen.patch(STOCK)
        self.assertIn("window.utility && !window.moveable && window.skipSwitcher", once)
        self.assertEqual(patch_dimscreen.patch(once), once)

    def test_leaves_an_unknown_layout_alone(self):
        self.assertIsNone(patch_dimscreen.patch("var x = 1;\n"))


if __name__ == "__main__":
    unittest.main()
