import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from overdrive import penquit  # noqa: E402

DEVICES = '''I: Bus=0018 Vendor=04f3 Product=261a Version=0100
N: Name="ELAN9038:00 04F3:261A"
H: Handlers=mouse0 event6

I: Bus=0018 Vendor=04f3 Product=261a Version=0100
N: Name="ELAN9038:00 04F3:261A Stylus"
H: Handlers=mouse1 event9
'''


class PenQuit(unittest.TestCase):
    def test_the_stylus_device(self):
        self.assertEqual(penquit.stylus_device(DEVICES), "/dev/input/event9")
        self.assertIsNone(penquit.stylus_device('N: Name="Keyboard"\nH: Handlers=kbd event2\n'))

    def test_host_from_the_command_line(self):
        self.assertEqual(penquit.stream_host(["moonlight", "stream", "100.67.70.95", "Desktop"], "/nowhere"), "100.67.70.95")

    def test_host_from_moonlight_settings(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as home:
            d = os.path.join(home, ".var/app", penquit.APP, "config/Moonlight Game Streaming Project")
            os.makedirs(d)
            open(os.path.join(d, "Moonlight.conf"), "w").write("[hosts]\n1\\hostname=DSKTP\n1\\manualaddress=100.67.70.95\n")
            self.assertEqual(penquit.stream_host(["moonlight"], home), "100.67.70.95")


if __name__ == "__main__":
    unittest.main()
