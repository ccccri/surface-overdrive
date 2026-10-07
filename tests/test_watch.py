import unittest

from overdrive import health, watch


def check(title, status):
    return health.Check(title, "Group", title, status, "detail of " + title)


class WatchTest(unittest.TestCase):
    def test_first_problem_notifies_once(self):
        note, state = watch.decide({}, [check("a", health.OK), check("b", health.FAIL)])
        self.assertTrue(note["urgent"])
        again, _ = watch.decide(state, [check("a", health.OK), check("b", health.FAIL)])
        self.assertIsNone(again)

    def test_new_problem_notifies_again(self):
        _, state = watch.decide({}, [check("a", health.WARN)])
        note, _ = watch.decide(state, [check("a", health.WARN), check("b", health.WARN)])
        self.assertIsNotNone(note)
        self.assertFalse(note["urgent"])

    def test_recovery_notifies_and_green_stays_quiet(self):
        _, state = watch.decide({}, [check("a", health.FAIL)])
        note, state = watch.decide(state, [check("a", health.OK)])
        self.assertIn("again", note["body"])
        quiet, _ = watch.decide(state, [check("a", health.OK)])
        self.assertIsNone(quiet)


if __name__ == "__main__":
    unittest.main()
