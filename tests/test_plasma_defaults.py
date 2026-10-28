import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("patch_plasma_defaults",
                                              Path(__file__).resolve().parent.parent / "ci" / "patch_plasma_defaults.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

DELEGATE = """Item {
    Rectangle {
        anchors.centerIn: imageSource
        color: Kirigami.Theme.backgroundColor
        opacity: 0.6
    }

    Item {
        id: imageSource
        width: 10
    }

    ShaderEffect {
        width: imageSource.width
    }
}
"""


class PanelTest(unittest.TestCase):
    def test_settings_before_the_widgets(self):
        text = 'var panel = new Panel\npanel.addWidget("org.kde.plasma.kickoff")\n'
        out = mod.patch_panel(text)
        self.assertLess(out.index('panel.hiding = "dodgewindows"'), out.index("kickoff"))
        self.assertIn('panel.opacity = "translucent"', out)
        self.assertEqual(mod.patch_panel(out), out)

    def test_unknown_layout(self):
        self.assertIsNone(mod.patch_panel("var panel = new Panel\n"))


class FaceTest(unittest.TestCase):
    def test_picture_hidden(self):
        out = mod.patch_face(DELEGATE)
        self.assertEqual(out.count("visible: false"), 3)
        self.assertEqual(mod.patch_face(out), out)

    def test_unknown_layout(self):
        self.assertIsNone(mod.patch_face(DELEGATE.replace("ShaderEffect", "Image")))

    def test_qmldir(self):
        text = "module org.kde.breeze.components\nprefer :/qt/qml/org/kde/breeze/components/\nUserDelegate 254.0 UserDelegate.qml\n"
        self.assertEqual(mod.patch_qmldir(text), "module org.kde.breeze.components\nUserDelegate 254.0 UserDelegate.qml\n")
        self.assertIsNone(mod.patch_qmldir("module x\n"))


if __name__ == "__main__":
    unittest.main()
