import json
import unittest

from overdrive import sensors


class SensorsTest(unittest.TestCase):
    def test_describe_never_raises_and_is_json(self):
        json.dumps(sensors.describe())

    def test_missing_paths_give_defaults(self):
        self.assertEqual(sensors.read("/nonexistent", "x"), "x")
        self.assertIsNone(sensors.number("/nonexistent"))
        self.assertIsNone(sensors.iio_device("no-such-sensor"))


if __name__ == "__main__":
    unittest.main()
