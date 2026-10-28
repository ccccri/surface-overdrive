import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("patch_plasma_pa", Path(__file__).resolve().parent.parent / "ci" / "patch_plasma_pa.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class PlasmaPaTest(unittest.TestCase):
    def tree(self, d, broken=False):
        for rel, changes in mod.CHANGES.items():
            path = Path(d) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("head\n" + "\n".join(old for old, new in changes) + "\ntail\n")
        if broken:
            (Path(d) / "src/kcm/ui/main.qml").write_text("something else\n")

    def test_patched_once(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d)
            mod.main(["x", d])
            text = (Path(d) / "applet/main.qml").read_text()
            self.assertIn("visible: false", text)
            self.assertNotIn("config.raiseMaximumVolume", text)
            mod.main(["x", d])
            self.assertEqual((Path(d) / "applet/main.qml").read_text(), text)

    def test_all_or_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, broken=True)
            mod.main(["x", d])
            self.assertIn("visible: !micTestActive", (Path(d) / "applet/main.qml").read_text())


if __name__ == "__main__":
    unittest.main()
