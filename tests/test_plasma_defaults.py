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

    def test_no_pager(self):
        text = ('var panel = new Panel\npanel.addWidget("org.kde.plasma.kickoff")\npanel.addWidget("org.kde.plasma.pager")\n'
                'panel.addWidget("org.kde.plasma.icontasks")\n')
        out = mod.patch_panel(text)
        self.assertNotIn('\npanel.addWidget("org.kde.plasma.pager")', out)
        self.assertIn('panel.addWidget("org.kde.plasma.icontasks")', out)
        self.assertEqual(mod.patch_panel(out), out)


class ClockTest(unittest.TestCase):
    def test_24_hours_and_the_date_untouched(self):
        text = ('    Label {\n        text: Qt.formatTime(timeSource.dateTime, Qt.locale(), Locale.ShortFormat)\n    }\n'
                '    Label {\n        text: Qt.formatDate(timeSource.dateTime, Qt.locale(), Locale.LongFormat)\n    }\n')
        out = mod.patch_clock(text)
        self.assertIn('Qt.formatTime(timeSource.dateTime, "HH:mm")', out)
        self.assertIn("Qt.formatDate(timeSource.dateTime, Qt.locale(), Locale.LongFormat)", out)
        self.assertEqual(mod.patch_clock(out), out)

    def test_unknown_layout(self):
        self.assertIsNone(mod.patch_clock("Label { text: clock.time }\n"))


class WallpaperTest(unittest.TestCase):
    GRID = ("Item {\n    id: thumbnailsComponent\n    KCM.GridView {\n        id: wallpapersGrid\n    }\n\n"
            "    KCM.SettingHighlighter {\n        target: wallpapersGrid\n        highlight: true\n    }\n}\n")

    def test_outer_areas_scroll_only_with_something_to_scroll(self):
        out = mod.patch_wallpaper(self.GRID)
        self.assertIn("Flickable.StopAtBounds", out)
        self.assertIn("area.contentHeight > area.height + 1", out)
        self.assertLess(out.index("Timer {"), out.index("KCM.SettingHighlighter"))
        self.assertEqual(out.count("{"), out.count("}"))
        self.assertEqual(mod.patch_wallpaper(out), out)

    def test_unknown_layout(self):
        self.assertIsNone(mod.patch_wallpaper("Item { GridView { } }\n"))


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
