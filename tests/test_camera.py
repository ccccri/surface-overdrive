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


if __name__ == "__main__":
    unittest.main()
