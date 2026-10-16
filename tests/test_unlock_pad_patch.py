import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("patch_unlock_pad", Path(__file__).resolve().parent.parent / "ci" / "patch_unlock_pad.py")
patch_unlock_pad = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch_unlock_pad)


def stock(target):
    return "SessionManagementScreen {\n" + "".join(old for old, _ in patch_unlock_pad.TARGETS[target]["changes"]) + "}\n"


class UnlockPadPatch(unittest.TestCase):
    def test_lock_screen(self):
        once = patch_unlock_pad.patch(stock("lockscreen"), "lockscreen")
        self.assertIn("UnlockPad.qml", once)
        self.assertIn("visible: !overdrivePad.padActive", once)
        self.assertIn("function onFailed(kind)", once)
        self.assertEqual(patch_unlock_pad.patch(once, "lockscreen"), once)

    def test_login_screen(self):
        once = patch_unlock_pad.patch(stock("login"), "login")
        self.assertIn("root.userList.selectedUser", once)
        self.assertIn("function onLoginFailed()", once)
        self.assertLess(once.index("overdrivePad"), once.index("// Synchronise state"))

    def test_lock_screen_footer(self):
        footer = "Item {\n" + patch_unlock_pad.TARGETS["lockscreen-footer"]["changes"][0][0] + "}\n"
        once = patch_unlock_pad.patch("// Surface Overdrive: other change\n" + footer, "lockscreen-footer")
        self.assertIn("!mainBlock.overdrivePadActive", once)
        self.assertEqual(patch_unlock_pad.patch(once, "lockscreen-footer"), once)

    def test_leaves_an_unknown_layout_alone(self):
        self.assertIsNone(patch_unlock_pad.patch("SessionManagementScreen { }\n", "lockscreen"))
        self.assertIsNone(patch_unlock_pad.patch("SessionManagementScreen { }\n", "login"))


if __name__ == "__main__":
    unittest.main()
