import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("patch_pam", Path(__file__).resolve().parent.parent / "ci" / "patch_pam.py")
patch_pam = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch_pam)

KDE = ("auth        substack      password-auth\n"
       "auth        include       postlogin\n"
       "account     required      pam_nologin.so\n")


class PamPatch(unittest.TestCase):
    def test_goes_before_the_password_once(self):
        once = patch_pam.patch(KDE)
        self.assertLess(once.index("unlock-check"), once.index("substack"))
        self.assertEqual(patch_pam.patch(once), once)

    def test_leaves_an_unknown_layout_alone(self):
        self.assertIsNone(patch_pam.patch("auth include system-auth\n"))
        self.assertIsNone(patch_pam.patch(KDE + KDE))


if __name__ == "__main__":
    unittest.main()
