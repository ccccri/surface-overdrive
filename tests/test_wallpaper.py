import json
import os
import tempfile
import unittest
from unittest import mock

from overdrive import wallpaper


class Wallpaper(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_paths(self):
        self.assertEqual(wallpaper.to_path("file:///home/me/Pictures/my%20photo.jpg"), "/home/me/Pictures/my photo.jpg")
        self.assertEqual(wallpaper.to_path("/usr/share/wallpapers/Next/"), "/usr/share/wallpapers/Next/")
        self.assertEqual(wallpaper.to_path(""), "")
        self.assertTrue(wallpaper.is_ours("/home/me/.local/share/wallpapers/surface-fit-0123abcd/"))
        self.assertFalse(wallpaper.is_ours("/usr/share/wallpapers/F44"))

    def test_only_big_pictures(self):
        self.assertTrue(wallpaper.needs_fitting(4096, 4096, (1800, 1200)))
        self.assertTrue(wallpaper.needs_fitting(4032, 3024, (1800, 1200)))
        self.assertFalse(wallpaper.needs_fitting(1920, 1200, (1800, 1200)))

    def test_sources_of_a_package_take_the_biggest_picture(self):
        pkg = os.path.join(self.tmp.name, "Pkg")
        for variant, names in (("images", ("1280x800.png", "3840x2160.png", "notes.txt")), ("images_dark", ("1920x1080.jpg",))):
            os.makedirs(os.path.join(pkg, "contents", variant))
            for n in names:
                open(os.path.join(pkg, "contents", variant, n), "w").close()
        found = wallpaper.sources(pkg)
        self.assertEqual(os.path.basename(found["images"]), "3840x2160.png")
        self.assertEqual(os.path.basename(found["images_dark"]), "1920x1080.jpg")
        photo = os.path.join(self.tmp.name, "IMG_0001.HEIC")
        open(photo, "w").close()
        self.assertEqual(wallpaper.sources(photo), {"images": photo})
        self.assertEqual(wallpaper.title_of(photo), "IMG_0001")

    def test_package_name_follows_the_picture(self):
        photo = os.path.join(self.tmp.name, "a.jpg")
        open(photo, "w").close()
        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": self.tmp.name}):
            first = wallpaper.package_for(photo)
            self.assertEqual(first, wallpaper.package_for(photo))
            os.utime(photo, (1, 1))
            self.assertNotEqual(first, wallpaper.package_for(photo))
            self.assertTrue(os.path.basename(first).startswith(wallpaper.PREFIX))

    def test_ours_and_missing_are_left_alone(self):
        with mock.patch.object(wallpaper, "make_package") as make:
            self.assertIsNone(wallpaper.fit("file:///x/.local/share/wallpapers/surface-fit-abc/", (1800, 1200)))
            self.assertIsNone(wallpaper.fit("file:///nowhere/at/all.jpg", (1800, 1200)))
        make.assert_not_called()


class LoginWallpaper(unittest.TestCase):
    def test_pack_round_trip_and_bad_input(self):
        from overdrive import loginwallpaper as lw
        data = lw.pack(b"landscape", b"portrait!")
        self.assertEqual(lw.unpack(data), [b"landscape", b"portrait!"])
        for bad in (b"", b"hello", data[:-1], data + b"x", lw.MAGIC + b"\xff\xff\xff\xff"):
            with self.assertRaises(ValueError):
                lw.unpack(bad)

    def test_only_pictures_of_the_right_shape(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("no Pillow")
        import io
        from overdrive import loginwallpaper as lw
        buf = io.BytesIO()
        Image.new("RGB", (180, 120), "blue").save(buf, "PNG")
        jpeg, size = lw.clean_jpeg(buf.getvalue(), True)
        self.assertEqual(size, (180, 120))
        self.assertTrue(jpeg.startswith(b"\xff\xd8"))
        with self.assertRaises(ValueError):
            lw.clean_jpeg(buf.getvalue(), False)              # landscape where a portrait picture is expected
        with self.assertRaises(ValueError):
            lw.clean_jpeg(b"#!/bin/sh\necho not a picture\n", True)

    def test_install_writes_package_and_login_configuration(self):
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest("no Pillow")
        from pathlib import Path
        from overdrive import loginwallpaper as lw
        with tempfile.TemporaryDirectory() as tmp:
            dest, conf = Path(tmp, "login-wallpaper"), Path(tmp, "plasmalogin.conf")
            with mock.patch("subprocess.run") as run:
                for _ in range(2):                              # a second install replaces the first
                    lw.install([(b"L", (1800, 1200)), (b"P", (1200, 1800))], dest, conf)
            self.assertEqual(sorted(p.name for p in (dest / "contents" / "images").iterdir()), ["1200x1800.jpg", "1800x1200.jpg"])
            written = [c.args[0] for c in run.call_args_list]
            self.assertIn(["kwriteconfig6", "--file", str(conf)] + lw.GROUP + ["--key", "Image", "file://%s/" % dest], written)
            self.assertFalse(Path(tmp, "login-wallpaper.new").exists() or Path(tmp, "login-wallpaper.old").exists())


class PlasmaTheme(unittest.TestCase):
    def test_dark_style_from_user_or_look_and_feel_defaults(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp}):
            self.assertFalse(wallpaper.plasma_theme_is_dark())
            os.makedirs(os.path.join(tmp, "kdedefaults"))
            with open(os.path.join(tmp, "kdedefaults", "plasmarc"), "w") as f:
                f.write("[Theme]\nname=breeze-dark\n")
            self.assertTrue(wallpaper.plasma_theme_is_dark())
            with open(os.path.join(tmp, "plasmarc"), "w") as f:
                f.write("[Other]\nname=x\n\n[Theme]\nname=breeze-light\n")
            self.assertFalse(wallpaper.plasma_theme_is_dark())
