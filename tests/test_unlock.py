import getpass
import json
import os
import tempfile
import unittest

from overdrive import unlock

USER = getpass.getuser()


class UnlockTest(unittest.TestCase):
    def setUp(self):
        self.store = os.path.join(tempfile.mkdtemp(), "unlock")

    def test_valid_codes(self):
        self.assertTrue(unlock.valid("pin", "1234"))
        self.assertTrue(unlock.valid("pin", "123456789012"))
        self.assertFalse(unlock.valid("pin", "123"))
        self.assertFalse(unlock.valid("pin", "1234567890123"))
        self.assertFalse(unlock.valid("pin", "12a4"))
        self.assertFalse(unlock.valid("pin", "١٢٣٤"))          # digits of another script are not on the keypad
        self.assertTrue(unlock.valid("pattern", "1235"))
        self.assertFalse(unlock.valid("pattern", "1231"))      # a dot at most once
        self.assertFalse(unlock.valid("pattern", "1230"))
        self.assertFalse(unlock.valid("pattern", "123"))
        self.assertFalse(unlock.valid("other", "1234"))

    def test_no_code_means_no_answer(self):
        self.assertIsNone(unlock.check(USER, "1234", self.store))
        self.assertEqual(unlock.status(USER, self.store), {"kind": "", "blocked": False})

    def test_set_check_and_clear(self):
        self.assertEqual(unlock.set_code(USER, "pin", "2580", self.store), {"kind": "pin", "blocked": False})
        self.assertTrue(unlock.check(USER, "2580", self.store))
        self.assertFalse(unlock.check(USER, "2581", self.store))
        secret = open(os.path.join(self.store, USER, "secret")).read()
        self.assertNotIn("2580", secret)
        self.assertEqual(os.stat(os.path.join(self.store, USER, "secret")).st_mode & 0o777, 0o640)
        unlock.set_code(USER, "pattern", "14789", self.store)
        self.assertEqual(unlock.status(USER, self.store)["kind"], "pattern")
        self.assertFalse(os.path.exists(os.path.join(self.store, USER, "pin.svg")))
        self.assertFalse(unlock.check(USER, "2580", self.store))
        self.assertTrue(unlock.check(USER, "14789", self.store))
        unlock.clear(USER, self.store)
        self.assertIsNone(unlock.check(USER, "14789", self.store))

    def test_bad_codes_are_refused(self):
        for kind, code in (("pin", "12"), ("pattern", "1123"), ("face", "1234")):
            with self.assertRaises(ValueError):
                unlock.set_code(USER, kind, code, self.store)
        with self.assertRaises(ValueError):
            unlock.status("../etc", self.store)

    def test_wrong_tries_block_until_passed(self):
        unlock.set_code(USER, "pin", "2580", self.store)
        for _ in range(unlock.MAX_TRIES):
            self.assertFalse(unlock.check(USER, "0000", self.store))
        self.assertTrue(unlock.status(USER, self.store)["blocked"])
        self.assertFalse(unlock.check(USER, "2580", self.store))          # blocked: even the right code waits for the password
        unlock.passed(USER, self.store)
        self.assertTrue(unlock.check(USER, "2580", self.store))

    def test_a_password_is_not_a_try(self):
        unlock.set_code(USER, "pin", "2580", self.store)
        for _ in range(unlock.MAX_TRIES + 2):
            self.assertFalse(unlock.check(USER, "correct horse", self.store))
            self.assertFalse(unlock.check(USER, "9" * 100, self.store))
        self.assertFalse(unlock.status(USER, self.store)["blocked"])
        self.assertTrue(unlock.check(USER, "2580", self.store))

    def test_right_code_forgets_wrong_tries(self):
        unlock.set_code(USER, "pin", "2580", self.store)
        for _ in range(unlock.MAX_TRIES - 1):
            unlock.check(USER, "0000", self.store)
        self.assertTrue(unlock.check(USER, "2580", self.store))
        self.assertFalse(unlock.check(USER, "0000", self.store))
        self.assertFalse(unlock.status(USER, self.store)["blocked"])

    def test_damaged_secret_is_no_code(self):
        unlock.set_code(USER, "pin", "2580", self.store)
        with open(os.path.join(self.store, USER, "secret"), "w") as f:
            json.dump({"kind": "pin"}, f)
        self.assertIsNone(unlock.check(USER, "2580", self.store))


if __name__ == "__main__":
    unittest.main()
