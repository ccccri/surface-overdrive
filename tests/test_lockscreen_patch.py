import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("patch_lockscreen", Path(__file__).resolve().parent.parent / "ci" / "patch_lockscreen.py")
patch_lockscreen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch_lockscreen)

STOCK = "MouseArea {\n" + "".join(old for old, _ in patch_lockscreen.CHANGES) + "}\n"


class LockScreenPatch(unittest.TestCase):
    def test_patches_once(self):
        once = patch_lockscreen.patch(STOCK)
        self.assertIn("PointHandler", once)
        self.assertIn("if (!touched)", once)
        self.assertEqual(patch_lockscreen.patch(once), once)

    def test_leaves_an_unknown_layout_alone(self):
        self.assertIsNone(patch_lockscreen.patch("MouseArea { }\n"))


if __name__ == "__main__":
    unittest.main()
