import unittest

from overdrive import tabletmode as t


class TabletModeTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(t.parse_panels("2:46:1,7:30:-1\n"), {"2": (46, 1), "7": (30, -1)})
        self.assertEqual(t.parse_panels(""), {})

    def test_enter_and_leave(self):
        want, buttons, kept = t.plan_enter({"2": (46, 1)}, "ButtonDefault")
        self.assertEqual(want, {"2": (t.TABLET_PANEL, t.TABLET_SPACING)})
        self.assertEqual(buttons, t.TABLET_BUTTONS)
        back, restore = t.plan_leave(kept, {"2": (t.TABLET_PANEL, t.TABLET_SPACING)}, t.TABLET_BUTTONS)
        self.assertEqual(back, {"2": (46, 1)})
        self.assertEqual(restore, "ButtonDefault")

    def test_hand_changes_win(self):
        _, _, kept = t.plan_enter({"2": (46, 1)}, "ButtonDefault")
        # meanwhile the panel was made 80 high by hand and the buttons small: those stay
        back, restore = t.plan_leave(kept, {"2": (80, t.TABLET_SPACING)}, "ButtonSmall")
        self.assertEqual(back, {"2": (None, 1)})
        self.assertIsNone(restore)

    def test_already_big(self):
        want, _, kept = t.plan_enter({"2": (70, 3)}, "ButtonDefault")
        self.assertEqual(want, {"2": (None, None)})
        back, _ = t.plan_leave(kept, {"2": (70, 3)}, t.TABLET_BUTTONS)
        self.assertEqual(back, {})

    def test_script(self):
        s = t.panel_write_script({"2": (62, None)})
        self.assertIn('"2": [62, null]', s)


if __name__ == "__main__":
    unittest.main()
