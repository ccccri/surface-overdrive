import math
import os
import tempfile
import unittest
from unittest import mock

from overdrive import userconfig
from overdrive.audio import eq, mic, store

SHIPPED = os.path.join(os.path.dirname(__file__), "..", "image/rootfs/usr/share/pipewire/pipewire.conf.d/10-overdrive-speaker-gain.conf")


class EqTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        p = mock.patch.object(userconfig, "CONFIG", self.tmp.name)
        p.start()
        self.addCleanup(p.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def test_shipped_chain_is_the_generated_one(self):
        self.assertEqual(open(SHIPPED).read(), eq.conf_text(eq.new_set()))

    def test_flat_set_is_transparent(self):
        for f in (50, 1000, 10000):
            self.assertAlmostEqual(eq.magnitude_db(eq.new_set()["bands"], f), 0.0, places=6)

    def test_peak_gain_at_its_centre(self):
        s = eq.new_set()
        s["bands"][4] = {"type": "peak", "freq": 1000.0, "gain": 6.0, "q": 1.0, "on": True}
        self.assertAlmostEqual(eq.magnitude_db(s["bands"], 1000), 6.0, places=1)

    def test_boost_is_cubic(self):
        self.assertAlmostEqual(eq.params(eq.new_set(120))["gainL:Mult"], 1.728, places=3)

    def test_sets_round_trip_and_sync(self):
        st = eq.load()
        self.assertTrue(st["sync"])
        s = eq.new_set()
        s["preamp"] = -3
        with mock.patch.object(eq, "apply"), mock.patch.object(eq.pw, "active_output", return_value="speaker"):
            eq.set_output("speaker", s)
            eq.set_sync(False)
        st = eq.load()
        self.assertFalse(st["sync"])
        self.assertEqual(st["sets"]["speaker"]["preamp"], -3.0)
        self.assertEqual(eq.effective(st, "headphones"), st["sets"]["headphones"])

    def test_presets(self):
        self.assertIn("Flat", [p["name"] for p in eq.preset_names()])
        self.assertEqual(eq.save_preset("Flat", eq.new_set()), "invalid")
        self.assertEqual(eq.save_preset("Mine", eq.new_set()), "ok")
        self.assertIn("Mine", [p["name"] for p in eq.preset_names()])
        eq.delete_preset("Mine")
        self.assertNotIn("Mine", [p["name"] for p in eq.preset_names()])

    def test_apo_import_export(self):
        text = "Preamp: -6.5 dB\nFilter 1: ON LSC Fc 105 Hz Gain 3.5 dB Q 0.70\nFilter 2: ON PK Fc 1500 Hz Gain -2.0 dB Q 1.5\n" \
               "Filter 3: ON HSC Fc 8000 Hz Gain 4.0 dB Q 0.70\n"
        s, notes = eq.parse_apo(text)
        self.assertEqual(s["preamp"], -6.5)
        self.assertEqual(s["bands"][0]["type"], "lowshelf")
        self.assertEqual(s["bands"][9]["type"], "highshelf")
        self.assertTrue(any(b["freq"] == 1500 for b in s["bands"]))
        again, _ = eq.parse_apo(eq.export_apo(s))
        self.assertEqual(again["preamp"], -6.5)
        self.assertIsNone(eq.parse_apo("nothing useful")[0])


class MicTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        p = mock.patch.object(userconfig, "CONFIG", self.tmp.name)
        p.start()
        self.addCleanup(p.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def test_values_are_clamped_and_stored(self):
        with mock.patch.object(mic.pw, "set_params", return_value=True) as sp:
            mic.set_one("gain", 99)
        self.assertEqual(mic.settings()["gain"], 24.0)
        self.assertAlmostEqual(sp.call_args[0][1]["gain:Mult"], 10 ** (24 / 20.0))

    def test_unknown_control(self):
        with self.assertRaises(KeyError):
            mic.set_one("volume", 1)

    def test_presets(self):
        with mock.patch.object(mic.pw, "set_params", return_value=True):
            self.assertTrue(mic.apply_preset("Clear voice"))
            self.assertEqual(mic.settings()["lowcut"], 110.0)
            self.assertEqual(mic.save_preset("Flat"), "invalid")
            self.assertEqual(mic.save_preset("Mine"), "ok")
        self.assertIn("Mine", [p["name"] for p in mic.presets()])


if __name__ == "__main__":
    unittest.main()
