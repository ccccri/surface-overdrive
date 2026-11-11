import unittest

from overdrive import streamrotate as sr

HEAD = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode ref pointer drops\n"


class Streaming(unittest.TestCase):
    def test_sunshine_ports(self):
        line = "  12: 6443A8C0:D2F1 2D00A8C0:BB7E 01 00000000:00000000 00:00000000 00000000  1000        0 1 2 0 0\n"
        self.assertTrue(sr.streaming([HEAD + line]))

    def test_other_ports_and_listeners(self):
        other = "  12: 6443A8C0:D2F1 2D00A8C0:0035 01 0:0 0:0 0 1000 0 1 2 0 0\n"
        listen = "  13: 00000000:BB80 00000000:0000 07 0:0 0:0 0 1000 0 1 2 0 0\n"
        self.assertFalse(sr.streaming([HEAD + other + listen]))

    def test_udp6(self):
        line = "  5: 00000000000000000000000001000000:9C40 0000000000000000FFFF00002D00A8C0:BB80 01 0:0 0:0 0 1000 0 1 2 0 0\n"
        self.assertTrue(sr.streaming(["", HEAD + line]))


class Orientation(unittest.TestCase):
    def test_upright_and_upside_down(self):
        self.assertEqual(sr.orientation(1.6, -6.1), "none")
        self.assertEqual(sr.orientation(-1.0, 7.0), "inverted")

    def test_side_flat_unsure(self):
        self.assertIsNone(sr.orientation(9.0, -1.0))   # on its side
        self.assertIsNone(sr.orientation(0.5, -1.0))   # lying flat
        self.assertIsNone(sr.orientation(5.0, -6.0))   # between
        self.assertIsNone(sr.orientation(None, 3.0))


if __name__ == "__main__":
    unittest.main()
