import unittest

from overdrive import pen


class PenTest(unittest.TestCase):
    def test_digitizer_names(self):
        text = 'I: Bus=0018\nN: Name="ELAN9038:00 04F3:261A"\nN: Name="ELAN UNKNOWN"\nN: Name="Power Button"\n'
        self.assertEqual(pen.digitizers(text), ["ELAN9038:00 04F3:261A"])

    def test_fake_battery_is_whatever_is_not_charger_or_tablet(self):
        self.assertEqual(pen.fake_batteries(["ACAD", "BAT1", "hid-0018:04F3:261A.0001-battery"]), ["hid-0018:04F3:261A.0001-battery"])
        self.assertEqual(pen.fake_batteries(["ACAD", "BAT1"]), [])


if __name__ == "__main__":
    unittest.main()
