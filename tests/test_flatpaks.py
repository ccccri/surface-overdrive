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
                    mock.patch.object(flatpaks, "OVERRIDDEN", Path(tmp, "state", "overridden")), \
                    mock.patch.object(flatpaks, "installed", return_value=set(present)), \
                    mock.patch.object(flatpaks, "flatpak", side_effect=lambda *a: calls.append(a) or 0):
                flatpaks.main([])
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

    def test_camera_apps_lose_raw_devices_once(self):
        calls, _ = self.run_main(set())
        self.assertIn(("override", "--system", "--nodevice=all", "--device=dri", "--device=input",
                       "com.obsproject.Studio"), calls)
        with TemporaryDirectory() as tmp:
            state = Path(tmp, "overridden")
            state.write_text("".join(a + "\n" for a in flatpaks.CAMERA_APPS))
            calls = []
            with mock.patch.object(flatpaks, "OVERRIDDEN", state), \
                    mock.patch.object(flatpaks, "flatpak", side_effect=lambda *a: calls.append(a) or 0):
                flatpaks.camera_overrides()
            self.assertEqual(calls, [])

    def test_feature_joins_the_last_enable_features_line(self):
        self.assertEqual(flatpaks.with_feature(""), "--enable-features=WebRtcPipeWireCamera\n")
        self.assertEqual(flatpaks.with_feature("--ozone-platform=wayland\n--enable-features=Foo\n"),
                         "--ozone-platform=wayland\n--enable-features=Foo,WebRtcPipeWireCamera\n")
        once = "--enable-features=WebRtcPipeWireCamera\n"
        self.assertEqual(flatpaks.with_feature(once), once)


if __name__ == "__main__":
    unittest.main()


class MoonlightTouch(unittest.TestCase):
    def test_library_copied_refreshed_and_preloaded_once(self):
        with TemporaryDirectory() as d:
            lib = Path(d, "moonlight-touch-cancel.so")
            lib.write_bytes(b"one")
            state = Path(d, "done")
            with mock.patch.object(flatpaks.subprocess, "run") as run:
                run.return_value.returncode = 0
                flatpaks.moonlight_touch(Path(d, "home"), state, lib)
                dest = Path(d, "home", ".var", "app", flatpaks.MOONLIGHT, "lib", lib.name)
                self.assertEqual(dest.read_bytes(), b"one")
                self.assertIn("--env=LD_PRELOAD=" + str(dest), run.call_args[0][0])
                lib.write_bytes(b"two")
                flatpaks.moonlight_touch(Path(d, "home"), state, lib)
                self.assertEqual(dest.read_bytes(), b"two")
                self.assertEqual(run.call_count, 1)

    def test_nothing_without_the_library(self):
        with TemporaryDirectory() as d, mock.patch.object(flatpaks.subprocess, "run") as run:
            flatpaks.moonlight_touch(Path(d), Path(d, "done"), Path(d, "missing.so"))
            run.assert_not_called()


class MoonlightMouse(unittest.TestCase):
    def test_added_to_general(self):
        self.assertEqual(flatpaks.with_absolute_mouse("[General]\nfps=60\n[hosts]\n1\\x=1\n"),
                         "[General]\nabsolutemousemode=true\nfps=60\n[hosts]\n1\\x=1\n")

    def test_existing_value_changed(self):
        self.assertEqual(flatpaks.with_absolute_mouse("[General]\nabsolutemousemode=false\n"),
                         "[General]\nabsolutemousemode=true\n")

    def test_new_file(self):
        self.assertEqual(flatpaks.with_absolute_mouse(""), "[General]\nabsolutemousemode=true\n")

    def test_once_and_not_while_running(self):
        with TemporaryDirectory() as d, mock.patch.object(flatpaks.subprocess, "run") as run:
            state = Path(d, "done")
            run.return_value.returncode = 0          # moonlight running
            flatpaks.moonlight_absolute_mouse(d, state)
            self.assertFalse(state.exists())
            run.return_value.returncode = 1
            flatpaks.moonlight_absolute_mouse(d, state)
            self.assertIn("absolutemousemode=true", Path(d, flatpaks.MOONLIGHT_CONF).read_text())
            self.assertTrue(state.exists())
