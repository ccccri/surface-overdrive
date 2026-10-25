import os
import tempfile
import unittest
from unittest import mock

from overdrive import camera


class CameraTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = self.tmp.name
        for name, val in (("PROFILE_DIR", base + "/camera"), ("PRESET_DIR", base + "/presets"), ("UI_FILE", base + "/ui.json"),
                          ("STATE_DIR", base), ("TUNING_DIR", base)):
            p = mock.patch.object(camera, name, val)
            p.start()
            self.addCleanup(p.stop)
        open(base + "/ov8865.yaml", "w").write("black: [ 1, 5, 1, 1 ]\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_values_leave_no_profile(self):
        camera.set_setting("rear", "saturation", 1.4)
        self.assertEqual(camera.read_profile("rear"), {"saturation": [1.4]})
        camera.set_setting("rear", "saturation", 1)
        self.assertEqual(camera.read_profile("rear"), {})
        self.assertFalse(os.path.exists(camera.profile_path("rear")))

    def test_black_point_is_relative_to_the_tuning(self):
        camera.set_setting("rear", "blackShift", 3)
        self.assertEqual(camera.read_profile("rear")["black"], [4, 8, 4, 4])
        self.assertEqual(camera.settings("rear")["blackShift"], 3)

    def test_temporal_default_is_per_camera(self):
        self.assertEqual(camera.settings("front")["temporal"], camera.TNR_DEFAULTS["front"])
        self.assertEqual(camera.settings("rear")["temporal"], camera.TNR_DEFAULTS["rear"])
        camera.set_setting("front", "temporal", camera.TNR_DEFAULTS["front"])
        self.assertNotIn("tnr", camera.read_profile("front"))

    def test_temporal_levels_round_trip(self):
        for level in range(6):
            camera.set_setting("rear", "temporal", level)
            self.assertEqual(camera.settings("rear")["temporal"], level)

    def test_manual_focus(self):
        camera.set_setting("rear", "focusManual", 1)
        self.assertTrue(camera.settings("rear")["focusManual"])
        camera.set_setting("rear", "focus", 5000)
        self.assertEqual(camera.read_profile("rear")["focus"], [1023.0])
        camera.set_setting("rear", "focusManual", 0)
        self.assertNotIn("focus", camera.read_profile("rear"))

    def test_size_change_restarts_the_service(self):
        with mock.patch.object(camera, "restart_camera_service") as r:
            self.assertTrue(camera.set_setting("front", "minWidth", 2048))
            r.assert_called_once()

    def test_unknown_key(self):
        with self.assertRaises(KeyError):
            camera.set_setting("rear", "nonsense", 1)

    def test_presets(self):
        camera.set_setting("rear", "contrast", 0.5)
        self.assertEqual(camera.save_preset("rear", "Warm room"), "ok")
        self.assertEqual(camera.save_preset("rear", "Warm room"), "exists")
        self.assertEqual(camera.save_preset("rear", "  "), "invalid")
        self.assertEqual(camera.list_presets("rear"), [{"id": "Warm_room", "name": "Warm room", "current": True}])
        camera.reset_all("rear")
        self.assertEqual(camera.matching_preset("rear"), "")
        camera.apply_preset("rear", "Warm_room")
        self.assertEqual(camera.settings("rear")["contrast"], 0.5)
        self.assertEqual(camera.duplicate_preset("rear", "Warm_room", "Copy"), "ok")
        self.assertEqual(camera.rename_preset("rear", "Copy", "Other"), "ok")
        camera.delete_preset("rear", "Other")
        self.assertEqual([p["id"] for p in camera.list_presets("rear")], ["Warm_room"])

    def test_describe_is_json_serialisable(self):
        import json
        json.dumps(camera.describe("front"))


class CameraRobustness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for name, value in (("PRESET_DIR", os.path.join(self.tmp.name, "presets")), ("UI_FILE", os.path.join(self.tmp.name, "ui.json"))):
            p = mock.patch.object(camera, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(camera, "read_profile", return_value={"gamma": [1.4]})
        p.start()
        self.addCleanup(p.stop)

    def test_preset_ids_cannot_leave_the_preset_folder(self):
        victim = os.path.join(self.tmp.name, "victim.json")
        with open(victim, "w") as f:
            f.write("{}")
        for pid in ("../victim", "../../victim", "/etc/passwd", "", "a/b", ".."):
            camera.delete_preset("rear", pid)
            self.assertEqual(camera.rename_preset("rear", pid, "x"), "invalid")
            self.assertEqual(camera.duplicate_preset("rear", pid, "y"), "invalid")
            self.assertFalse(camera.apply_preset("rear", pid))
        self.assertTrue(os.path.exists(victim))

    def test_preset_names(self):
        self.assertEqual(camera.save_preset("rear", "x" * 61), "invalid")
        self.assertEqual(camera.save_preset("rear", " \n "), "invalid")
        self.assertEqual(camera.save_preset("rear", "  Evening \n light "), "ok")
        self.assertEqual(camera.save_preset("rear", "Evening light"), "exists")
        self.assertEqual([p["name"] for p in camera.list_presets("rear")], ["Evening light"])

    def test_damaged_files_read_as_empty(self):
        os.makedirs(os.path.join(camera.PRESET_DIR, "rear"))
        for text in ("{broken", "[1, 2]", '"x"'):
            with open(camera.UI_FILE, "w") as f:
                f.write(text)
            with open(os.path.join(camera.PRESET_DIR, "rear", "bad.json"), "w") as f:
                f.write(text)
            with open(os.path.join(camera.PRESET_DIR, "rear", "not a slug.json"), "w") as f:
                f.write('{"name": "n", "profile": {}}')
            self.assertEqual(camera.ui_setting("anything", 7), 7)
            self.assertEqual(camera.list_presets("rear"), [])
            self.assertEqual(camera.matching_preset("rear"), "")
            camera.set_ui_setting("k", 1)
            self.assertEqual(camera.ui_setting("k", 0), 1)

    def test_unknown_setting(self):
        with self.assertRaises(KeyError):
            camera.reset_setting("rear", "bogus")


if __name__ == "__main__":
    unittest.main()
