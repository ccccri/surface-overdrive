import unittest

from overdrive.nfc.ndef import parse_ndef, tlv_ndef


def record(flags, rtype, payload):
    return bytes([flags, len(rtype), len(payload)]) + rtype + payload


class TlvTest(unittest.TestCase):
    def test_complete_message(self):
        msg = record(0xD1, b"U", b"\x04example.com")
        data = b"\x00\x00" + bytes([0x03, len(msg)]) + msg + b"\xfe"
        self.assertEqual(tlv_ndef(data), msg)

    def test_incomplete_message_asks_for_more(self):
        msg = record(0xD1, b"U", b"\x04example.com")
        data = bytes([0x03, len(msg)]) + msg[:5]
        self.assertIsNone(tlv_ndef(data))

    def test_terminator_means_empty(self):
        self.assertEqual(tlv_ndef(b"\xfe"), b"")

    def test_long_length_form(self):
        # a record with a payload above 255 bytes uses the four-byte length (SR flag cleared)
        payload = b"\x02en" + b"x" * 300
        msg = bytes([0xC1, 1]) + len(payload).to_bytes(4, "big") + b"T" + payload
        data = bytes([0x03, 0xFF]) + len(msg).to_bytes(2, "big") + msg
        self.assertEqual(tlv_ndef(data), msg)
        self.assertEqual(parse_ndef(msg)[0]["value"], "x" * 300)

    def test_other_tlv_is_skipped(self):
        msg = record(0xD1, b"U", b"\x03a.b")
        data = bytes([0x01, 0x02, 0xAA, 0xBB, 0x03, len(msg)]) + msg
        self.assertEqual(tlv_ndef(data), msg)


class NdefTest(unittest.TestCase):
    def test_uri_with_prefix(self):
        recs = parse_ndef(record(0xD1, b"U", b"\x04example.com"))
        self.assertEqual(recs, [{"kind": "uri", "value": "https://example.com"}])

    def test_uri_unknown_prefix_is_kept_plain(self):
        recs = parse_ndef(record(0xD1, b"U", b"\xf0abc"))
        self.assertEqual(recs, [{"kind": "uri", "value": "abc"}])

    def test_text_utf8(self):
        recs = parse_ndef(record(0xD1, b"T", b"\x02enciao"))
        self.assertEqual(recs, [{"kind": "text", "lang": "en", "value": "ciao"}])

    def test_text_utf16(self):
        payload = bytes([0x82]) + b"it" + "ciao".encode("utf-16")
        recs = parse_ndef(record(0xD1, b"T", payload))
        self.assertEqual(recs[0]["value"], "ciao")
        self.assertEqual(recs[0]["lang"], "it")

    def test_two_records(self):
        msg = record(0x91, b"T", b"\x02enone") + record(0x51, b"U", b"\x05123")
        recs = parse_ndef(msg)
        self.assertEqual([r["kind"] for r in recs], ["text", "uri"])
        self.assertEqual(recs[1]["value"], "tel:123")

    def test_smart_poster_nests_records(self):
        inner = record(0xD1, b"U", b"\x04example.com")
        recs = parse_ndef(record(0xD1, b"Sp", inner))
        self.assertEqual(recs[0]["kind"], "smartposter")
        self.assertEqual(recs[0]["value"], [{"kind": "uri", "value": "https://example.com"}])

    def test_mime_and_external(self):
        recs = parse_ndef(record(0x92, b"text/plain", b"abc") + record(0x54, b"x:y", b"1"))
        self.assertEqual(recs[0], {"kind": "mime", "value": "text/plain", "size": 3})
        self.assertEqual(recs[1], {"kind": "external", "value": "x:y"})

    def test_truncated_record_raises_index_error(self):
        # the daemon catches IndexError and struct.error from a tag that disappeared mid-read
        with self.assertRaises(IndexError):
            parse_ndef(b"\xd1\x01")

    def test_empty_message(self):
        self.assertEqual(parse_ndef(b""), [])


if __name__ == "__main__":
    unittest.main()
