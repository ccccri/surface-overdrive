import tempfile
import unittest
from pathlib import Path

from overdrive import helper


class VolumeHoldTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.param = self.tmp / "volume_hold"
        self.conf = self.tmp / "modprobe.d" / "overdrive-intel-hid.conf"

    def test_unavailable_without_the_module(self):
        self.assertEqual(helper.volume_hold_state(self.param), "unavailable")
        with self.assertRaises(RuntimeError):
            helper.set_volume_hold(True, self.param, self.conf)

    def test_off_and_on_are_applied_and_kept(self):
        self.param.write_text("Y")
        self.assertEqual(helper.volume_hold_state(self.param), "on")
        helper.set_volume_hold(False, self.param, self.conf)
        self.assertEqual(self.param.read_text(), "N")
        self.assertEqual(helper.volume_hold_state(self.param), "off")
        self.assertIn("options intel_hid volume_hold=0", self.conf.read_text())
        helper.set_volume_hold(True, self.param, self.conf)
        self.assertIn("volume_hold=1", self.conf.read_text())


class StylusFilterTest(unittest.TestCase):
    def test_mask_file_switches_it_off(self):
        mask = Path(tempfile.mkdtemp()) / "rules.d" / "80-overdrive-stylus.rules"
        self.assertEqual(helper.stylus_filter_state(mask), "on")
        helper.set_stylus_filter(False, mask, reload_udev=False)
        self.assertEqual(helper.stylus_filter_state(mask), "off")
        self.assertEqual(mask.read_text(), "")
        helper.set_stylus_filter(True, mask, reload_udev=False)
        self.assertEqual(helper.stylus_filter_state(mask), "on")


class CommandLineTest(unittest.TestCase):
    def test_rejects_anything_not_on_the_list(self):
        for argv in ([], ["volume-hold"], ["reboot", "on"], ["volume-hold", "maybe"], ["volume-hold", "on", "x"]):
            self.assertEqual(helper.main(argv), 2, argv)


if __name__ == "__main__":
    unittest.main()
