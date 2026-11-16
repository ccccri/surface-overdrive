import io
import unittest

from overdrive import autobrightness as ab


def run(controller, lux, brightness, seconds, start=0.0, tick=1.0, apply=True):
    """Feeds the same light for a while; what the controller asks for is set, as the service does. The brightness at the end."""
    t = start
    while t < start + seconds:
        target = controller.tick(lux, brightness, t)
        if target is not None and apply:
            brightness = target
            controller.ours = target
        t += tick if target is None else 0.15
    return brightness


class Curve(unittest.TestCase):
    def test_rises_with_the_light_and_stays_in_range(self):
        last = 0
        for lux in (0, 1, 3, 5, 10, 20, 50, 80, 150, 300, 600, 1000, 2500, 4000, 8000, 10000, 50000):
            value = ab.curve(lux)
            self.assertGreaterEqual(value, last, lux)
            self.assertTrue(0.0 < value <= 1.0)
            last = value
        self.assertEqual(ab.curve(-5), ab.curve(0))
        self.assertEqual(ab.curve(1e9), 1.0)

    def test_the_points_themselves(self):
        for lux, value in ab.CURVE:
            self.assertAlmostEqual(ab.curve(lux), value, places=6)


class Follows(unittest.TestCase):
    def test_goes_to_the_curve_and_stops_near_it(self):
        c = ab.Controller()
        end = run(c, 300, 0.10, 60)
        self.assertAlmostEqual(end, ab.curve(300), delta=ab.DEADBAND + 0.001)
        self.assertIsNone(c.tick(300, end, 100.0))                 # and then leaves it alone

    def test_a_short_shadow_does_nothing(self):
        c = ab.Controller()
        level = run(c, 300, 0.10, 60)
        after = run(c, 2, level, ab.DARKER_AFTER - 1.5, start=60)   # a hand over the sensor for a few seconds
        self.assertEqual(after, level)
        self.assertEqual(run(c, 300, after, 20, start=70), level)

    def test_brighter_sooner_than_darker(self):
        up, down = ab.Controller(), ab.Controller()
        run(up, 50, ab.curve(50), 10)
        run(down, 2000, ab.curve(2000), 10)
        self.assertGreater(run(up, 2000, ab.curve(50), 3.5, start=10), ab.curve(50))
        self.assertEqual(run(down, 50, ab.curve(2000), 3.5, start=10), ab.curve(2000))

    def test_moves_in_small_steps(self):
        c = ab.Controller()
        level, t, biggest = 0.10, 0.0, 0.0
        for _ in range(400):
            target = c.tick(3000, level, t)
            if target is not None:
                biggest = max(biggest, abs(target - level))
                level = target
                c.ours = target
            t += 0.15 if target is not None else 1.0
        self.assertLessEqual(biggest, ab.STEP + 1e-9)
        self.assertGreater(level, 0.7)

    def test_never_black(self):
        c = ab.Controller(bias=-0.35)
        self.assertGreaterEqual(run(c, 0, 0.5, 120), c.floor)

    def test_no_sensor_no_change(self):
        c = ab.Controller()
        self.assertIsNone(c.tick(None, 0.5, 0.0))
        self.assertIsNone(c.tick(100, None, 1.0))


class HandsOff(unittest.TestCase):
    def test_a_brightness_of_the_user_is_kept_until_the_room_changes(self):
        c = ab.Controller()
        level = run(c, 300, 0.10, 60)
        # the user wants it much brighter than the curve, in the same light
        self.assertEqual(run(c, 300, 0.90, 120, start=60), 0.90)
        self.assertEqual(run(c, 380, 0.90, 60, start=180), 0.90)    # a little more light is not another room
        # outdoors now: it works again, and keeps the user's taste (brighter than the curve)
        end = run(c, 4000, 0.90, 60, start=240)
        self.assertGreater(c.bias, 0.2)
        self.assertGreaterEqual(end, 0.90)
        self.assertNotEqual(level, 0.90)

    def test_dimmed_by_plasma_and_back_is_left_alone(self):
        c = ab.Controller()
        level = run(c, 300, 0.10, 60)
        self.assertEqual(run(c, 300, level * 0.3, 30, start=60), level * 0.3)     # Plasma dims the idle screen
        self.assertEqual(run(c, 300, level, 30, start=90), level)                 # and gives the brightness back
        self.assertAlmostEqual(c.bias, 0.0, delta=0.05)

    def test_in_the_dark_small_numbers_are_not_another_room(self):
        c = ab.Controller()
        run(c, 1, 0.08, 30)
        self.assertEqual(run(c, 1, 0.30, 60, start=30), 0.30)       # reading in bed, brighter by hand
        self.assertEqual(run(c, 2.5, 0.30, 60, start=90), 0.30)     # 1 lux to 2.5 lux is more than double, and nothing
        self.assertEqual(run(c, 0.2, 0.30, 60, start=150), 0.30)

    def test_bias_is_bounded(self):
        self.assertEqual(ab.Controller(bias=5).bias, ab.BIAS_LIMIT)
        self.assertEqual(ab.Controller(bias=-5).bias, -ab.BIAS_LIMIT)


class Service(unittest.TestCase):
    def test_dry_run_sets_nothing(self):
        calls, out, clock = [], io.StringIO(), [0.0]

        def call(method, *args):
            calls.append(method)
            return 1500 if method == "brightnessMax" else 0

        def sleep(seconds):
            clock[0] += seconds

        ab.serve(clock=lambda: clock[0], sleep=sleep, light=lambda: 800.0, level=lambda: 0.10, call=call, dry=True, out=out, rounds=12)
        self.assertNotIn("setBrightnessSilent", calls)
        self.assertIn("would set", out.getvalue())

    def test_sets_through_plasma_in_its_units(self):
        calls, clock, level = [], [0.0], [0.10]

        def call(method, *args):
            calls.append((method,) + args)
            if method == "setBrightnessSilent":
                level[0] = int(args[1]) / 1500
            return 1500 if method == "brightnessMax" else 0

        def sleep(seconds):
            clock[0] += seconds

        ab.serve(clock=lambda: clock[0], sleep=sleep, light=lambda: 800.0, level=lambda: level[0], call=call, rounds=200)
        sets = [c for c in calls if c[0] == "setBrightnessSilent"]
        self.assertTrue(sets)
        self.assertTrue(all(c[1] == "i" and 1 <= int(c[2]) <= 1500 for c in sets))
        self.assertAlmostEqual(level[0], ab.curve(800), delta=ab.DEADBAND + 0.002)

    def test_no_sensor_ends_quietly(self):
        out = io.StringIO()
        self.assertEqual(ab.serve(light=lambda: None, level=lambda: 0.5, call=lambda *a: 1500, out=out, rounds=3), 0)
        self.assertIn("nothing to do", out.getvalue())


if __name__ == "__main__":
    unittest.main()
