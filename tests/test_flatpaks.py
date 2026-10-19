import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from overdrive import flatpaks  # noqa: E402


class Flatpaks(unittest.TestCase):
    def test_remove_list_skips_comments(self):
        self.assertEqual(flatpaks.wanted_gone("# head\norg.a.b\n\norg.c.d  # why\n"), ["org.a.b", "org.c.d"])

    def run_main(self, present, done=""):
        with TemporaryDirectory() as tmp:
            remove, state = Path(tmp, "remove.list"), Path(tmp, "state", "done")
            remove.write_text("org.kde.kmines\norg.kde.elisa\n")
            if done:
                state.parent.mkdir()
                state.write_text(done)
            calls = []
            with mock.patch.object(flatpaks, "REMOVE_LIST", remove), mock.patch.object(flatpaks, "DONE", state), \
                    mock.patch.object(flatpaks, "installed", return_value=set(present)), \
                    mock.patch.object(flatpaks, "flatpak", side_effect=lambda *a: calls.append(a) or 0):
                flatpaks.main()
            return calls, state.read_text().split()

    def test_removes_each_app_once_then_preinstalls(self):
        calls, done = self.run_main({"org.kde.kmines", "org.kde.okular"})
        self.assertIn(("uninstall", "--system", "-y", "--noninteractive", "org.kde.kmines"), calls)
        self.assertNotIn("org.kde.elisa", [c[-1] for c in calls])
        self.assertIn(("preinstall", "--system", "-y", "--noninteractive"), calls)
        self.assertEqual(done, ["org.kde.elisa", "org.kde.kmines"])

    def test_an_app_installed_again_by_hand_stays(self):
        calls, _ = self.run_main({"org.kde.kmines"}, done="org.kde.elisa\norg.kde.kmines\n")
        self.assertFalse([c for c in calls if c[0] == "uninstall" and c[-1] == "org.kde.kmines"])


if __name__ == "__main__":
    unittest.main()
