import unittest

from overdrive.nfc.notify import describe, flatten


class NotifyTextTest(unittest.TestCase):
    def test_link_is_offered(self):
        text, url = describe({"uid": "04:aa", "type": "Type 2",
                              "records": [{"kind": "uri", "value": "https://example.com"}]})
        self.assertEqual(url, "https://example.com")
        self.assertIn("Link: https://example.com", text)
        self.assertEqual(text[-1], "Type 2, UID 04:aa")

    def test_text_record_has_no_link(self):
        text, url = describe({"uid": "1", "type": "Type 2", "records": [{"kind": "text", "value": "ciao"}]})
        self.assertIsNone(url)
        self.assertEqual(text[0], "Text: ciao")

    def test_unreadable_card(self):
        text, url = describe({"uid": "1", "type": "ISO-DEP (Type 4)", "records": None})
        self.assertIsNone(url)
        self.assertIn("Card or device, no readable data", text)

    def test_empty_tag(self):
        text, _ = describe({"uid": "1", "type": "Type 2", "records": []})
        self.assertIn("Empty or non-NDEF tag", text)

    def test_smart_poster_is_flattened(self):
        lines = flatten([{"kind": "smartposter", "value": [{"kind": "uri", "value": "tel:123"}]}])
        self.assertEqual(lines, [("Link: tel:123", "tel:123")])


if __name__ == "__main__":
    unittest.main()
