import io
import json
import unittest
import unittest.mock

from overdrive import sensors


class SensorsTest(unittest.TestCase):
    def test_describe_never_raises_and_is_json(self):
        json.dumps(sensors.describe())

    def test_missing_paths_give_defaults(self):
        self.assertEqual(sensors.read("/nonexistent", "x"), "x")
        self.assertIsNone(sensors.number("/nonexistent"))
        self.assertIsNone(sensors.iio_device("no-such-sensor"))


class FollowTest(unittest.TestCase):
    def run_follow(self, script):
        """script: what each wait gives: None (time to read), a command line, "" (end of input)."""
        out, rates, steps = io.StringIO(), [], iter(script)
        with unittest.mock.patch.object(sensors, "set_rate", rates.append), \
             unittest.mock.patch.object(sensors, "describe", lambda: {"device": {}, "lux": 1, "motion": None}), \
             unittest.mock.patch.object(sensors, "motion", lambda: {"accel": [0, 0, 9.8]}), \
             unittest.mock.patch.object(sensors, "light", lambda: 42.0):
            code = sensors.follow(out=out, wait=lambda seconds: next(steps))
        return code, [json.loads(line) for line in out.getvalue().splitlines()], rates

    def test_whole_picture_first_then_motion_and_light_every_fifth(self):
        code, lines, rates = self.run_follow([None] * 5 + [""])
        self.assertEqual(code, 0)
        self.assertIn("device", lines[0])
        self.assertEqual([sorted(l) for l in lines[1:]], [["motion"]] * 5 + [["lux"]])
        self.assertEqual(rates, [50, 10])              # fast while it runs, back to the hub's default at the end

    def test_paused_reads_nothing(self):
        code, lines, rates = self.run_follow(["pause\n", None, None, "go\n", None, ""])
        self.assertEqual(len(lines), 2)                # the first picture and one round after "go"
        self.assertEqual(rates, [50, 10, 50, 10])

    def test_a_closed_reader_ends_it_quietly(self):
        class Closed(io.StringIO):
            def write(self, text):
                raise BrokenPipeError
        with unittest.mock.patch.object(sensors, "set_rate", lambda r: None):
            self.assertEqual(sensors.follow(out=Closed(), wait=lambda s: None), 0)


if __name__ == "__main__":
    unittest.main()
