import os
import tempfile
import unittest
from unittest import mock

from overdrive import paneldefaults as pd

APPLETS = """[ActionPlugins][0]
RightButton;NoModifier=org.kde.contextmenu

[Containments][1]
plugin=org.kde.plasma.folder

[Containments][2]
location=4
plugin=org.kde.panel

[Containments][2][Applets][3]
plugin=org.kde.plasma.kickoff

[Containments][2][Applets][4]
immutability=1
plugin=org.kde.plasma.pager

[Containments][2][Applets][4][Configuration]
displayedText=Number

[Containments][2][Applets][5]
plugin=org.kde.plasma.icontasks

[Containments][2][Applets][40]
plugin=org.kde.plasma.digitalclock

[Containments][2][General]
AppletOrder=3;4;5;40
"""

SHELLRC = """[PlasmaViews][Panel 2][Defaults]
thickness=46

[Updates]
performed=a.js
"""


class PanelDefaultsTest(unittest.TestCase):
    def test_pager_gone_and_order_kept(self):
        applets, _, ids = pd.apply(APPLETS, SHELLRC)
        self.assertEqual(ids, ["2"])
        self.assertNotIn("org.kde.plasma.pager", applets)
        self.assertNotIn("[Containments][2][Applets][4]", applets)
        self.assertIn("[Containments][2][Applets][40]", applets)          # 40 is not 4
        self.assertIn("AppletOrder=3;5;40\n", applets)
        self.assertIn("RightButton;NoModifier=org.kde.contextmenu", applets)

    def test_view_settings_added_or_changed(self):
        _, shell, _ = pd.apply(APPLETS, SHELLRC)
        self.assertIn("[PlasmaViews][Panel 2]\npanelVisibility=2\npanelOpacity=2\nfloating=1\n", shell)
        self.assertIn("[PlasmaViews][Panel 2][Defaults]\nthickness=46", shell)
        _, again, _ = pd.apply(APPLETS, shell.replace("panelOpacity=2", "panelOpacity=1"))
        self.assertEqual(again.count("panelOpacity="), 1)
        self.assertIn("panelOpacity=2", again)

    def test_idempotent(self):
        applets, shell, _ = pd.apply(APPLETS, SHELLRC)
        self.assertEqual(pd.apply(applets, shell)[:2], (applets, shell))

    def test_no_panel_no_change(self):
        text = "[Containments][1]\nplugin=org.kde.plasma.folder\n"
        self.assertEqual(pd.apply(text, ""), (text, "", []))

    def test_main_once_and_keeps_file_modes(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "cfg")
            os.makedirs(cfg)
            ap = os.path.join(cfg, "plasma-org.kde.plasma.desktop-appletsrc")
            with open(ap, "w") as f:
                f.write(APPLETS)
            os.chmod(ap, 0o600)
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": cfg}), \
                    mock.patch.object(pd.userconfig, "CONFIG", os.path.join(d, "state")):
                pd.main()
                self.assertNotIn("pager", open(ap).read())
                self.assertEqual(os.stat(ap).st_mode & 0o777, 0o600)
                self.assertTrue(os.path.exists(os.path.join(d, "state", pd.DONE)))
                with open(ap, "a") as f:
                    f.write("[Containments][2][Applets][9]\nplugin=org.kde.plasma.pager\n")
                pd.main()                                     # done once: a pager added later stays
                self.assertIn("pager", open(ap).read())

    def test_main_without_desktop_waits(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": d}), \
                    mock.patch.object(pd.userconfig, "CONFIG", os.path.join(d, "state")):
                pd.main()
                self.assertFalse(os.path.exists(os.path.join(d, "state", pd.DONE)))


if __name__ == "__main__":
    unittest.main()
