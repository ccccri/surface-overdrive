import os
import tempfile
import unittest
from unittest import mock

from overdrive import welcome


class WelcomeTest(unittest.TestCase):
    def run_main(self, rc_text):
        d = tempfile.mkdtemp()
        if rc_text is not None:
            with open(os.path.join(d, "plasma-welcomerc"), "w") as f:
                f.write(rc_text)
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": d}), \
                mock.patch.object(welcome.userconfig, "CONFIG", os.path.join(d, "so")), \
                mock.patch.object(welcome.time, "sleep"), \
                mock.patch.object(welcome.subprocess, "Popen") as popen:
            welcome.main([])
            welcome.main([])
        return popen, os.path.exists(os.path.join(d, "so", welcome.DONE))

    def test_after_a_switch_our_pages_open_once(self):
        popen, done = self.run_main("[General]\nLastSeenVersion=6.8.2\n")
        self.assertEqual(popen.call_count, 1)
        self.assertIn(welcome.PAGES, popen.call_args[0][0])
        self.assertTrue(done)

    def test_a_brand_new_user_gets_them_inside_plasmas_own_welcome(self):
        popen, done = self.run_main(None)
        popen.assert_not_called()
        self.assertTrue(done)

    def test_pages_exist_in_the_image(self):
        root = os.path.join(os.path.dirname(__file__), "..", "image", "rootfs", "usr", "share", "plasma",
                            "plasma-welcome", "extra-pages")
        for page in welcome.PAGES.split(","):
            self.assertTrue(os.path.exists(os.path.join(root, page + ".qml")), page)


if __name__ == "__main__":
    unittest.main()
