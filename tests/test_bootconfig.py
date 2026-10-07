import tempfile
import unittest
from pathlib import Path

from overdrive import bootconfig


class BootConfigTest(unittest.TestCase):
    def test_merge_into_empty_and_idempotent(self):
        once = bootconfig.merge("", "set timeout=3\n")
        self.assertIn("set timeout=3", once)
        self.assertEqual(bootconfig.merge(once, "set timeout=3\n"), once)

    def test_merge_keeps_the_users_lines_and_replaces_our_block(self):
        text = "set foo=1\n" + bootconfig.merge("", "set timeout=3\n") + "set bar=2\n"
        new = bootconfig.merge(text, "set timeout=5\n")
        self.assertIn("set foo=1", new)
        self.assertIn("set bar=2", new)
        self.assertIn("set timeout=5", new)
        self.assertNotIn("set timeout=3", new)
        self.assertEqual(new.count(bootconfig.BEGIN), 1)

    def test_install_reports_change(self):
        with tempfile.TemporaryDirectory() as d:
            src, dst = Path(d, "src"), Path(d, "user.cfg")
            src.write_text("set timeout=3\n")
            self.assertTrue(bootconfig.install(src, dst))
            self.assertFalse(bootconfig.install(src, dst))


if __name__ == "__main__":
    unittest.main()
