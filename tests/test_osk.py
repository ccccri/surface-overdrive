import unittest

from overdrive import osk


class OskGuard(unittest.TestCase):
    def test_lock_switches_it_on_and_unlock_puts_it_back(self):
        self.assertEqual(osk.decide(True, osk.OFF, False), (osk.TOUCH, True))
        self.assertEqual(osk.decide(False, osk.TOUCH, True), (osk.OFF, False))

    def test_leaves_alone_a_keyboard_that_is_on(self):
        self.assertEqual(osk.decide(True, osk.TOUCH, False), (None, False))
        self.assertEqual(osk.decide(False, osk.TOUCH, False), (None, False))
        self.assertEqual(osk.decide(True, 2, False), (None, False))

    def test_keeps_a_change_made_while_locked(self):
        self.assertEqual(osk.decide(False, 2, True), (None, False))

    def test_parse(self):
        self.assertIs(osk.parse("/ScreenSaver: org.freedesktop.ScreenSaver.ActiveChanged (true,)"), True)
        self.assertIs(osk.parse("/ScreenSaver: org.freedesktop.ScreenSaver.ActiveChanged (false,)"), False)
        self.assertIsNone(osk.parse("/ScreenSaver: org.freedesktop.ScreenSaver.Other (true,)"))


if __name__ == "__main__":
    unittest.main()
