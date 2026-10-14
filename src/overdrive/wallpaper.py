"""overdrive-wallpaper: keeps the wallpaper light enough for the tablet to turn its screen at once.

Plasma loads the wallpaper again at every turn of the screen. A photo from a phone or Fedora's own 4096x4096 JPEG XL takes about
a second to decode on the Surface Go, and during that second the desktop and the panel keep their old size: the turn looks
broken. Measured: with a JPEG at the size of the screen the desktop has its new size 70-190 ms after a turn.

So, whenever the wallpaper of the desktop or of the lock screen is an image bigger than the screen, this user service makes a
wallpaper package with two JPEGs at the size of the screen, one per orientation (Plasma picks the one that fits), and
points the setting at it. The picture looks the same; the original file is not touched. A package keeps the name of the
original and remembers where it came from, so it is made once per picture.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import unquote, urlparse

PREFIX = "surface-fit-"
APPLETS = "plasma-org.kde.plasma.desktop-appletsrc"
LOCKER = "kscreenlockerrc"
DEFAULT_SCREEN = (1800, 1200)
KEEP = 8                                  # packages of earlier wallpapers kept, so going back to one is instant
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".jxl", ".webp", ".avif", ".heic", ".heif", ".tif", ".tiff", ".bmp", ".svg", ".svgz")


def config_dir():
    return os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")


def wallpapers_dir():
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "wallpapers")


def is_ours(location):
    return os.path.basename(location.rstrip("/")).startswith(PREFIX)


def to_path(value):
    """The file or folder a wallpaper setting points at ("file:///x", "/x" or ""), or ""."""
    if not value:
        return ""
    if value.startswith("file:"):
        return unquote(urlparse(value).path)
    return value if value.startswith("/") else ""


def default_package():
    return os.path.realpath("/usr/share/wallpapers/Default")


def sources(location):
    """{"images": file, "images_dark": file} of what a wallpaper is: a single picture, or the biggest picture of each folder of a
    wallpaper package."""
    if os.path.isfile(location):
        return {"images": location}
    out = {}
    for variant in ("images", "images_dark"):
        folder = os.path.join(location, "contents", variant)
        try:
            names = [n for n in os.listdir(folder) if n.lower().endswith(IMAGE_EXT)]
        except OSError:
            continue
        best = max(names, key=lambda n: size_from_name(n) or (0, 0), default=None)
        if best:
            out[variant] = os.path.realpath(os.path.join(folder, best))
    return out


def size_from_name(name):
    m = re.match(r"(\d+)x(\d+)\.", name)
    return (int(m.group(1)) * int(m.group(2)), 0) if m else None


def has_screen_sizes(location, screen):
    folder = os.path.join(location, "contents", "images")
    long_side, short_side = max(screen), min(screen)
    return all(any(n.startswith("%dx%d." % size) for n in (os.listdir(folder) if os.path.isdir(folder) else []))
               for size in ((long_side, short_side), (short_side, long_side)))


def package_for(location):
    """Folder of the package made for this wallpaper. The name changes when the picture changes."""
    srcs = sources(location)
    stamp = "|".join("%s:%s:%s" % (k, v, os.path.getmtime(v)) for k, v in sorted(srcs.items()))
    return os.path.join(wallpapers_dir(), PREFIX + hashlib.sha1(stamp.encode()).hexdigest()[:12])


def needs_fitting(width, height, screen):
    """A picture is worth fitting when it has noticeably more pixels than the screen."""
    return width * height > screen[0] * screen[1] * 1.3


def title_of(location):
    if os.path.isfile(location):
        return os.path.splitext(os.path.basename(location))[0]
    try:
        with open(os.path.join(location, "metadata.json")) as f:
            return json.load(f)["KPlugin"]["Name"]
    except (OSError, ValueError, KeyError, TypeError):
        return os.path.basename(location.rstrip("/"))


# ---- what needs Qt and Plasma: kept apart so the rest can be tested without them ----
def image_size(path):
    from PySide6.QtGui import QImageReader
    reader = QImageReader(path)
    size = reader.size()
    return size.width(), size.height()


def write_fitted(src, folder, screen):
    """The two screen-sized JPEGs of one picture, cropped from its middle like Plasma's default fill does."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImageReader
    reader = QImageReader(src)
    reader.setAutoTransform(True)                     # photos taken upright stay upright
    image = reader.read()
    if image.isNull():
        raise OSError("cannot read %s: %s" % (src, reader.errorString()))
    os.makedirs(folder, exist_ok=True)
    long_side, short_side = max(screen), min(screen)
    for w, h in ((long_side, short_side), (short_side, long_side)):
        scaled = image.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        cropped = scaled.copy((scaled.width() - w) // 2, (scaled.height() - h) // 2, w, h)
        tmp = os.path.join(folder, ".%dx%d.jpg" % (w, h))
        if not cropped.save(tmp, "JPG", 92):
            raise OSError("cannot write " + tmp)
        os.replace(tmp, os.path.join(folder, "%dx%d.jpg" % (w, h)))


def make_package(location, screen):
    """The fitted package of a wallpaper, made if it is not there yet. None when the wallpaper is light enough as it is."""
    srcs = sources(location)
    if not srcs:
        return None
    if has_screen_sizes(location, screen):
        return None                                      # already has pictures at the size of this screen (the default does)
    if not any(needs_fitting(*image_size(p), screen) for p in srcs.values()):
        return None
    pkg = package_for(location)
    if os.path.isfile(os.path.join(pkg, "metadata.json")):
        return pkg
    work = pkg + ".part"
    shutil.rmtree(work, ignore_errors=True)
    for variant, src in srcs.items():
        write_fitted(src, os.path.join(work, "contents", variant), screen)
    meta = {"KPlugin": {"Id": os.path.basename(pkg), "Name": title_of(location), "Description": "Screen-sized copy, made by Surface Overdrive",
                        "License": "same as the original"}, "X-Surface-Overdrive-Source": location}
    with open(os.path.join(work, "metadata.json"), "w") as f:
        json.dump(meta, f, indent=1)
    os.replace(work, pkg)
    return pkg


def screen_size():
    """(width, height) of the built-in screen in pixels, as it stands now."""
    try:
        # without the offscreen platform of this service: kscreen-doctor needs the real one (it hangs otherwise)
        env = {k: v for k, v in os.environ.items() if k != "QT_QPA_PLATFORM"}
        out = subprocess.run(["kscreen-doctor", "-j"], capture_output=True, text=True, timeout=10, env=env).stdout
        for o in json.loads(out)["outputs"]:
            if o.get("enabled", True):
                mode = next(m for m in o["modes"] if m["id"] == o["currentModeId"])
                return mode["size"]["width"], mode["size"]["height"]
    except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError):
        pass
    return DEFAULT_SCREEN


def plasma(script):
    try:
        out = subprocess.run(["busctl", "--user", "--json=short", "call", "org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell",
                              "evaluateScript", "s", script], capture_output=True, text=True, timeout=20).stdout
        return json.loads(out)["data"][0]
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError):
        return None


def desktop_wallpapers():
    """{desktop id: Image setting} of the desktops that use a picture."""
    out = plasma('var d=desktops(); var o={}; for (var i=0;i<d.length;i++){ if (d[i].wallpaperPlugin != "org.kde.image") continue; '
                 'd[i].currentConfigGroup=["Wallpaper","org.kde.image","General"]; o[d[i].id]=d[i].readConfig("Image",""); } print(JSON.stringify(o))')
    try:
        return json.loads(out) if out else {}
    except ValueError:
        return {}


def set_desktop_wallpaper(desktop_id, url):
    plasma('var d=desktops(); for (var i=0;i<d.length;i++){ if (d[i].id != %d) continue; d[i].currentConfigGroup=["Wallpaper","org.kde.image","General"]; '
           'd[i].writeConfig("Image",%s); }' % (int(desktop_id), json.dumps(url)))


LOCK_GROUP = ["--group", "Greeter", "--group", "Wallpaper", "--group", "org.kde.image", "--group", "General", "--key", "Image"]


def lock_wallpaper():
    try:
        return subprocess.run(["kreadconfig6", "--file", LOCKER] + LOCK_GROUP, capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def set_lock_wallpaper(url):
    subprocess.run(["kwriteconfig6", "--file", LOCKER] + LOCK_GROUP + [url], timeout=10)


def fit(value, screen):
    """The setting a wallpaper should have instead of `value`, or None when it is fine as it is."""
    location = to_path(value) or default_package()
    if is_ours(location) or not os.path.exists(location):
        return None
    try:
        pkg = make_package(location, screen)
    except OSError as exc:
        print("could not fit %s: %s" % (location, exc), flush=True)
        return None
    return "file://" + pkg + "/" if pkg else None


def tidy():
    """Remove packages of old wallpapers: keep the ones in use and the most recent others."""
    in_use = {to_path(v).rstrip("/") for v in list(desktop_wallpapers().values()) + [lock_wallpaper()]}
    try:
        ours = [os.path.join(wallpapers_dir(), n) for n in os.listdir(wallpapers_dir()) if n.startswith(PREFIX)]
    except OSError:
        return
    ours.sort(key=os.path.getmtime, reverse=True)
    for path in ours[KEEP:]:
        if path.rstrip("/") not in in_use:
            shutil.rmtree(path, ignore_errors=True)


def check_once():
    screen = screen_size()
    changed = False
    for desktop_id, value in desktop_wallpapers().items():
        new = fit(value, screen)
        if new:
            set_desktop_wallpaper(desktop_id, new)
            print("desktop %s: %s -> %s" % (desktop_id, value or "(default)", new), flush=True)
            changed = True
    value = lock_wallpaper()
    if value or changed:
        new = fit(value, screen)
        if new:
            set_lock_wallpaper(new)
            print("lock screen: %s -> %s" % (value or "(default)", new), flush=True)
    tidy()


def mtimes():
    out = []
    for name in (APPLETS, LOCKER):
        try:
            out.append(os.path.getmtime(os.path.join(config_dir(), name)))
        except OSError:
            out.append(0)
    return out


def main():
    """Check now, then every time the wallpaper settings are saved (polling their files every few seconds costs nothing)."""
    from PySide6.QtGui import QGuiApplication           # image plugins (JPEG XL, HEIC...) need an application object
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QGuiApplication(sys.argv[:1])                  # noqa: F841 (kept alive)
    for _ in range(30):                                  # Plasma may still be starting
        if plasma("print(1)") is not None:
            break
        time.sleep(2)
    last = None
    while True:
        now = mtimes()
        if now != last:
            time.sleep(1)                                # let the settings finish writing
            check_once()
            last = mtimes()
        time.sleep(4)
