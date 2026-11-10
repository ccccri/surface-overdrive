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


class UpdateGuardTest(unittest.TestCase):
    def test_first_run_only_remembers(self):
        note, state = watch.decide_update({}, "img1", "45.1", [check("a", health.FAIL)], True)
        self.assertIsNone(note)
        self.assertEqual(state, {"image": "img1", "problems_on_image": ["a"]})

    def test_update_that_breaks_a_fix_offers_going_back(self):
        _, state = watch.decide_update({}, "img1", "45.1", [check("a", health.OK), check("b", health.WARN)], True)
        note, state = watch.decide_update(state, "img2", "45.2", [check("a", health.FAIL), check("b", health.WARN)], True)
        self.assertTrue(note["go_back"])
        self.assertIn("45.2", note["title"])
        self.assertIn("a:", note["body"])
        self.assertNotIn("b:", note["body"])          # already broken before the update
        again, _ = watch.decide_update(state, "img2", "45.2", [check("a", health.FAIL)], True)
        self.assertIsNone(again)                      # asked once per image

    def test_update_that_breaks_nothing_stays_quiet(self):
        _, state = watch.decide_update({}, "img1", "45.1", [check("b", health.WARN)], True)
        note, _ = watch.decide_update(state, "img2", "45.2", [check("b", health.WARN)], True)
        self.assertIsNone(note)

    def test_no_previous_image_no_offer(self):
        _, state = watch.decide_update({}, "img1", "45.1", [], True)
        note, _ = watch.decide_update(state, "img2", "45.2", [check("a", health.FAIL)], False)
        self.assertIsNone(note)

    def test_judged_against_the_last_check_before_the_update(self):
        _, state = watch.decide_update({}, "img1", "45.1", [], True)
        _, state = watch.decide_update(state, "img1", "45.1", [check("a", health.FAIL)], True)   # broke before the update
        note, _ = watch.decide_update(state, "img2", "45.2", [check("a", health.FAIL)], True)
        self.assertIsNone(note)
