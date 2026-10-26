import os
import tempfile
import unittest
import datetime

from overdrive import cameraapp


def node(name, sizes, fmt="NV12"):
    return {"type": "PipeWire:Interface:Node", "info": {"props": {"node.name": name},
            "params": {"EnumFormat": [{"format": fmt, "size": {"width": w, "height": h}} for w, h in sizes]}}}


class CamerasFromDump(unittest.TestCase):
    def test_both_cameras_with_their_first_size(self):
        dump = [node("libcamera_input.__SB_.PCI0.LNK1", [(2560, 1920), (2560, 1920)]),
                node("libcamera_input.__SB_.PCI0.LNK0", [(1536, 1152), (3200, 2400)]),
                node("alsa_input.pci", [])]
        cams = cameraapp.cameras_from_dump(dump)
        self.assertEqual(cams["front"]["size"], (2560, 1920))
        self.assertEqual(cams["rear"]["size"], (1536, 1152))
        self.assertEqual(cams["rear"]["node"], "libcamera_input.__SB_.PCI0.LNK0")

    def test_no_formats_no_camera(self):
        self.assertEqual(cameraapp.cameras_from_dump([node("libcamera_input.__SB_.PCI0.LNK1", [])]), {})
        self.assertEqual(cameraapp.cameras_from_dump(None), {})


class Sizes(unittest.TestCase):
    def test_preview_is_scaled_down_and_even(self):
        self.assertEqual(cameraapp.preview_size(2560, 1920), (1280, 960))
        self.assertEqual(cameraapp.preview_size(3200, 2400), (1280, 960))
        self.assertEqual(cameraapp.preview_size(1152, 864), (1152, 864))
        w, h = cameraapp.preview_size(2592, 1944)
        self.assertEqual((w % 2, h % 2), (0, 0))

    def test_bitrate(self):
        self.assertEqual(cameraapp.video_bitrate(2560, 1920), 12000)
        self.assertEqual(cameraapp.video_bitrate(1152, 864), 4000)


class Pipelines(unittest.TestCase):
    def test_record_uses_the_gpu_encoder_and_sound(self):
        d = cameraapp.record_description("n", 2560, 1920, "/tmp/a b.mp4")
        self.assertIn("vah264enc", d)
        self.assertIn("fdkaacenc", d)
        self.assertIn('location="/tmp/a b.mp4"', d)
        self.assertNotIn("pulsesrc", cameraapp.record_description("n", 2560, 1920, "/tmp/x.mp4", audio=False))

    def test_preview_has_both_sinks(self):
        d = cameraapp.preview_description("n", 2560, 1920)
        self.assertIn("appsink name=preview", d)
        self.assertIn("appsink name=photo", d)
        self.assertIn("width=1280,height=960", d)


class OutputPath(unittest.TestCase):
    def test_never_overwrites(self):
        now = datetime.datetime(2026, 10, 26, 17, 0, 0)
        with tempfile.TemporaryDirectory() as d:
            first = cameraapp.output_path(d, "video", now)
            self.assertTrue(first.endswith("VID_2026-10-26_17-00-00.mp4"))
            open(first, "w").close()
            second = cameraapp.output_path(d, "video", now)
            self.assertNotEqual(first, second)
            self.assertTrue(cameraapp.output_path(d, "photo", now).endswith(".jpg"))


if __name__ == "__main__":
    unittest.main()
