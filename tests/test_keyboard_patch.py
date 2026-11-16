"""The patch of Plasma's on-screen keyboard (patches/plasma-keyboard) and its place in the image."""
import os
import re
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PATCH = os.path.join(ROOT, "patches", "plasma-keyboard", "0001-overdrive-keyboard.patch")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class KeyboardPatch(unittest.TestCase):
    def setUp(self):
        self.patch = read(PATCH)
        self.files = set(re.findall(r"^\+\+\+ b/(\S+)", self.patch, flags=re.M))

    def test_new_sources_are_built(self):
        """A source file the patch adds and CMake does not name would compile to nothing, silently."""
        cmake = "\n".join(line[1:] for line in self.patch.split("diff --git a/src/CMakeLists.txt")[1].split("diff --git")[0].splitlines()
                          if line.startswith("+"))
        for path in self.files:
            name = os.path.basename(path)
            if path.startswith("src/") and "/layouts/" not in path and "/styles/" not in path and "/qmlplugin/" not in path \
                    and name.endswith((".cpp", ".h", ".qml")) and ("new file mode" in self.patch.split("b/" + path)[1][:200]):
                self.assertIn(name, cmake, path)

    def test_no_debug_traces(self):
        added = [line for line in self.patch.splitlines() if line.startswith("+")]
        self.assertFalse([line for line in added if "DBG" in line or "console.log" in line])

    def test_floating_never_on_the_lock_screen(self):
        """The floating keyboard's window is not shown above the lock screen: the setting must not decide alone."""
        self.assertIn("PlasmaKeyboardSettings.floating && !screenLock.locked", self.patch)
        self.assertIn("bool m_locked = true;", self.patch)          # unknown counts as locked

    def test_image_builds_and_installs_it(self):
        container = read(os.path.join(ROOT, "Containerfile"))
        self.assertIn("plasma-keyboard > /plasma-keyboard-nvr", container)
        self.assertIn("AS keyboard", container)
        self.assertIn("COPY --from=keyboard /out/rpms", container)
        script = read(os.path.join(ROOT, "ci", "build_keyboard.sh"))
        self.assertIn("patch -p1 --dry-run", script)                 # a patch that does not fit keeps Fedora's keyboard


if __name__ == "__main__":
    unittest.main()
