"""Every launcher of the image imports what it names.

The launchers (usr/bin/overdrive-*, usr/libexec/overdrive/*) are three lines: the package path, "from overdrive.x import
main", a call. On 2026-11-16 a package overdrive/osk/ was added beside the module overdrive/osk.py: the package won, and
the lock-screen keyboard guard would have died at its start with "cannot import name 'main'". Nothing else would have
said so before the tablet was locked.
"""
import ast
import importlib
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
LAUNCHER_DIRS = ("image/rootfs/usr/bin", "image/rootfs/usr/libexec/overdrive")


def launchers():
    for d in LAUNCHER_DIRS:
        full = os.path.join(ROOT, d)
        for name in sorted(os.listdir(full)) if os.path.isdir(full) else ():
            path = os.path.join(full, name)
            try:
                with open(path) as f:
                    text = f.read()
            except (OSError, UnicodeDecodeError):
                continue
            if text.startswith("#!/usr/bin/python3"):
                yield path, text


class Launchers(unittest.TestCase):
    def test_there_are_launchers(self):
        self.assertGreater(len(list(launchers())), 3)

    def test_names_exist(self):
        for path, text in launchers():
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("overdrive"):
                    try:
                        module = importlib.import_module(node.module)
                    except ImportError as e:
                        # a module that needs what the test machine lacks (PySide6, GStreamer) still has to be found
                        spec = importlib.util.find_spec(node.module)
                        self.assertIsNotNone(spec, "%s: %s (%s)" % (path, node.module, e))
                        continue
                    for alias in node.names:
                        self.assertTrue(hasattr(module, alias.name), "%s: %s has no %s" % (path, node.module, alias.name))

    def test_no_package_beside_a_module(self):
        base = os.path.join(ROOT, "src", "overdrive")
        for name in os.listdir(base):
            if name.endswith(".py"):
                self.assertFalse(os.path.isdir(os.path.join(base, name[:-3])), "overdrive/%s and overdrive/%s/ both exist" % (name, name[:-3]))


if __name__ == "__main__":
    unittest.main()
