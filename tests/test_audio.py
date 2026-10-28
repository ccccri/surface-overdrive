import math
import os
import tempfile
import unittest
from unittest import mock

from overdrive import userconfig
from overdrive.audio import eq, graph, mic, store


class EqTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        p = mock.patch.object(userconfig, "CONFIG", self.tmp.name)
        p.start()
        self.addCleanup(p.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def test_graph_names_every_control_it_is_later_given(self):
        text = eq.graph_text(eq.new_set())
        for control in eq.params(eq.new_set()):
            node, key = control.split(":")
            self.assertIn("name = %s " % node, text)
            self.assertIn('"%s" =' % key, text)

    def test_swap_exchanges_left_and_right(self):
        straight, swapped = eq.params(eq.new_set()), eq.params(eq.new_set(), True)
        self.assertEqual((straight["outL:Gain 1"], straight["outL:Gain 2"]), (1.0, 0.0))
        self.assertEqual((swapped["outL:Gain 1"], swapped["outL:Gain 2"]), (0.0, 1.0))
        self.assertEqual((swapped["outR:Gain 1"], swapped["outR:Gain 2"]), (1.0, 0.0))
        st = eq.load()
        self.assertTrue(st["swap"]["headphones"])
        self.assertFalse(st["swap"]["speaker"])

    def test_reset_bands_keeps_the_boost(self):
        s = eq.new_set(150)
        s["bands"][3]["gain"] = 9.0
        with mock.patch.object(eq, "apply"), mock.patch.object(eq.pw, "active_output", return_value="speaker"):
            eq.set_output("speaker", s)
            eq.reset_bands("speaker")
        st = eq.load()["sets"]["speaker"]
        self.assertEqual(st["boost"], 150.0)
        self.assertEqual(st["bands"], eq.flat_bands())

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

    def test_nonsense_input_becomes_neutral_values(self):
        for bad in ([], None, "x", {"boost": "loud", "preamp": None}, {"bands": "x"}, {"bands": [1, None, "b"]}, {"boost": float("nan")}):
            s = eq._normalise(bad)
            self.assertEqual(len(s["bands"]), eq.N)
            self.assertEqual(s["boost"], float(eq.DEFAULT_BOOST))
        self.assertEqual(eq._normalise({"boost": 1e99, "preamp": -1e99})["boost"], 180.0)
        with mock.patch.object(eq, "apply"), mock.patch.object(eq.pw, "active_output", return_value="speaker"):
            for call in (lambda: eq.set_output("bogus", {}), lambda: eq.reset_bands("bogus"), lambda: eq.set_swap("bogus", True)):
                with self.assertRaises(KeyError):
                    call()
        self.assertEqual(sorted(eq.load()["sets"]), ["headphones", "speaker"])

    def test_a_damaged_settings_file_reads_as_defaults(self):
        for text in ("{broken", "[1, 2]", '{"eq": 5, "mic": "x", "presets": [], "mic_on": 1}', '{"eq": {"sets": {"speaker": 3}, "swap": 7}}'):
            with open(store.path(), "w") as f:
                f.write(text)
            self.assertEqual(eq.load()["sets"]["speaker"], eq.new_set())
            self.assertEqual(mic.settings(), mic.DEFAULTS)
            self.assertEqual([p["name"] for p in eq.preset_names()], list(eq.builtin_presets()))
            self.assertEqual(eq.save_preset("Mine", eq.new_set()), "ok")
            eq.delete_preset("Mine")

    def test_preset_names_are_tidied_and_limited(self):
        self.assertEqual(eq.save_preset("x" * 61, eq.new_set()), "invalid")
        self.assertEqual(eq.save_preset("   ", eq.new_set()), "invalid")
        self.assertEqual(eq.save_preset("  my \n set ", eq.new_set()), "ok")
        self.assertIn("my set", [p["name"] for p in eq.preset_names()])

    def test_current_preset_and_boost_kept(self):
        with mock.patch.object(eq, "apply"), mock.patch.object(eq.pw, "active_output", return_value="speaker"):
            eq.set_output("speaker", eq.new_set(150))
            self.assertEqual([p["name"] for p in eq.preset_names() if "speaker" in p["current"]], ["Flat"])
            moved = eq.new_set(150)
            moved["bands"][4].update(freq=700.0, q=0.8)                 # a band at 0 dB does nothing wherever it sits: still flat
            eq.set_output("speaker", moved)
            self.assertEqual([p["name"] for p in eq.preset_names() if "speaker" in p["current"]], ["Flat"])
            self.assertTrue(eq.apply_preset("speaker", "Warm"))
            self.assertFalse(eq.apply_preset("speaker", "Nope"))
        self.assertEqual(eq.load()["sets"]["speaker"]["boost"], 150.0)
        self.assertEqual([p["name"] for p in eq.preset_names() if "speaker" in p["current"]], ["Warm"])

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
        with mock.patch.object(mic.graph, "apply", return_value=True) as ga:
            mic.enable()
            mic.set_one("gain", 99)
            mic.set_all({"gain": "loud", "denoise": float("nan"), "lowcut": 1e9})
        self.assertEqual(mic.settings(), dict(mic.DEFAULTS, lowcut=400.0))
        self.assertAlmostEqual(ga.call_args_list[1][0][3]["gainL:Mult"], 10 ** (24 / 20.0))

    def test_off_takes_the_filters_out(self):
        with mock.patch.object(mic.graph, "apply") as ga, mock.patch.object(mic.graph, "clear", return_value=True) as gc:
            mic.set_one("gain", 3)
        ga.assert_not_called()
        gc.assert_called_once_with(mic.SOURCE)

    def test_graph_names_every_control_it_is_later_given(self):
        text = mic.graph_text(mic.DEFAULTS)
        for control in mic.controls(mic.DEFAULTS):
            node, key = control.split(":")
            self.assertIn("name = %s " % node, text)
            self.assertIn('"%s" =' % key, text)

    def test_unknown_control(self):
        with self.assertRaises(KeyError):
            mic.set_one("volume", 1)

    def test_presets(self):
        with mock.patch.object(mic.graph, "apply", return_value=True), mock.patch.object(mic.graph, "clear", return_value=True):
            self.assertTrue(mic.apply_preset("Clear voice"))
            self.assertEqual(mic.settings()["lowcut"], 110.0)
            self.assertEqual(mic.save_preset("Flat"), "invalid")
            self.assertEqual(mic.save_preset("Mine"), "ok")
        self.assertIn("Mine", [p["name"] for p in mic.presets()])


if __name__ == "__main__":
    unittest.main()


class GraphTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": self.tmp.name})
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_loads_once_then_only_sets_controls(self):
        sent = []
        with mock.patch.object(graph.pw, "node_serial", return_value=(40, "7")), \
                mock.patch.object(graph.pw, "set_params", side_effect=lambda name, p: sent.append(p) or True):
            self.assertFalse(graph.loaded("dev", "v1"))
            self.assertTrue(graph.apply("dev", "v1", lambda: "GRAPH", {"a:Mult": 1.0}))
            self.assertTrue(graph.loaded("dev", "v1"))
            self.assertTrue(graph.apply("dev", "v1", lambda: "GRAPH", {"a:Mult": 2.0}))
        self.assertEqual(sent, [{graph.PROP: "GRAPH"}, {"a:Mult": 2.0}])

    def test_a_node_made_again_gets_the_graph_again(self):
        sent = []
        with mock.patch.object(graph.pw, "set_params", side_effect=lambda name, p: sent.append(p) or True):
            with mock.patch.object(graph.pw, "node_serial", return_value=(40, "7")):
                graph.apply("dev", "v1", lambda: "GRAPH", {})
            with mock.patch.object(graph.pw, "node_serial", return_value=(52, "9")):
                self.assertFalse(graph.loaded("dev", "v1"))
                graph.apply("dev", "v1", lambda: "GRAPH", {})
        self.assertEqual(sent, [{graph.PROP: "GRAPH"}, {graph.PROP: "GRAPH"}])

    def test_no_node(self):
        with mock.patch.object(graph.pw, "node_serial", return_value=None):
            self.assertFalse(graph.apply("dev", "v1", lambda: "GRAPH", {}))
            self.assertTrue(graph.clear("dev"))

    def test_clear_removes_what_was_loaded(self):
        sent = []
        with mock.patch.object(graph.pw, "node_serial", return_value=(40, "7")), \
                mock.patch.object(graph.pw, "set_params", side_effect=lambda name, p: sent.append(p) or True):
            graph.apply("dev", "v1", lambda: "GRAPH", {})
            self.assertTrue(graph.clear("dev"))
            self.assertFalse(graph.loaded("dev", "v1"))
        self.assertEqual(sent[-1], {graph.PROP: ""})


class TopBandsTest(unittest.TestCase):
    def test_untouched_old_top_bands_move(self):
        old = eq.new_set()
        for i, f in eq.OLD_TOP.items():
            old["bands"][i]["freq"] = f
        old["bands"][8]["gain"] = 0.0
        moved = eq._normalise(old)
        self.assertEqual([b["freq"] for b in moved["bands"][7:]], [7000.0, 11000.0, 16000.0])

    def test_used_band_stays(self):
        s = eq.new_set()
        s["bands"][8]["freq"] = 12000.0
        s["bands"][8]["gain"] = -2.0
        self.assertEqual(eq._normalise(s)["bands"][8]["freq"], 12000.0)


class RouteTest(unittest.TestCase):
    def test_events(self):
        from overdrive.audio import route
        self.assertEqual(route.relevant("Event 'change' on sink #66"), (True, False))
        self.assertEqual(route.relevant("Event 'new' on source #70"), (True, True))
        self.assertEqual(route.relevant("Event 'change' on client #2809"), (False, False))
        self.assertEqual(route.relevant("Event 'change' on sink-input #2812"), (False, False))
