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
