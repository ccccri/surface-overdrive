"""overdrive-wallpaper: keeps the wallpaper light enough for the tablet to turn its screen at once.

Plasma loads the wallpaper again at every turn of the screen. A photo from a phone or Fedora's own 4096x4096 JPEG XL takes about
a second to decode on the Surface Go, and during that second the desktop and the panel keep their old size: the turn looks
broken. Measured: with a JPEG at the size of the screen the desktop has its new size 70-190 ms after a turn.

So, whenever the wallpaper of the desktop or of the lock screen is an image bigger than the screen, this user service makes a
wallpaper package with two JPEGs at the size of the screen, one per orientation (Plasma picks the one that fits), and
points the setting at it. The picture looks the same; the original file is not touched. A package keeps the name of the
original and remembers where it came from, so it is made once per picture.

One wallpaper everywhere: when the wallpaper of the desktop changes, the lock screen and the login screen get it too. The
login screen runs as another user and cannot read the home folder, so its copy goes to the system through
/usr/libexec/overdrive/login-wallpaper (polkit, no password for the user at the screen), which gets the pictures themselves.
A lock screen wallpaper chosen on its own stays until the desktop one changes again.
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
LOGIN_HELPER = "/usr/libexec/overdrive/login-wallpaper"
KEEP = 8                                  # packages of earlier wallpapers kept, so going back to one is instant
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".jxl", ".webp", ".avif", ".heic", ".heif", ".tif", ".tiff", ".bmp", ".svg", ".svgz")


def config_dir():
    return os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")


def wallpapers_dir():
    """Where the screen-sized copies go. Not ~/.local/share/wallpapers: Plasma lists every package there, and each copy
    showed up as a second entry with the name of its wallpaper (two "Waterfall" in the Wallpaper page, 2026-10-27)."""
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "surface-overdrive", "wallpapers")


def legacy_wallpapers_dir():
    """Where the copies were made before; tidy() clears them, fit() makes new ones in wallpapers_dir()."""
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "wallpapers")


def source_of(location):
    """The wallpaper a copy of ours was made from (its metadata), or ""."""
    try:
        with open(os.path.join(location, "metadata.json")) as f:
            return json.load(f).get("X-Surface-Overdrive-Source", "")
    except (OSError, ValueError, AttributeError):
        return ""


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


def screen_size(drm="/sys/class/drm"):
    """(width, height) of the built-in screen in pixels: the native mode of the connected panel (eDP, the first of its modes),
    read from the kernel. Which way round does not matter here (the long and short sides are what count). This used to ask
    kscreen-doctor, which crashed once at the start of a session (2026-10-26) and costs a process at every check."""
    try:
        for name in sorted(os.listdir(drm)):
            if "-eDP-" not in name:
                continue
            path = os.path.join(drm, name)
            try:
                with open(os.path.join(path, "status")) as f:
                    if f.read().strip() != "connected":
                        continue
                with open(os.path.join(path, "modes")) as f:
                    first = f.readline().strip()
            except OSError:
                continue
            m = re.fullmatch(r"(\d+)x(\d+)\S*", first)
            if m:
                return int(m.group(1)), int(m.group(2))
    except OSError:
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
    if is_ours(location) and os.path.dirname(location.rstrip("/")) == legacy_wallpapers_dir():
        # a copy in the old place: made again from its wallpaper in the new place
        location = source_of(location)
        if not location:
            return None
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
        ours = []
    ours.sort(key=os.path.getmtime, reverse=True)
    for path in ours[KEEP:]:
        if path.rstrip("/") not in in_use:
            shutil.rmtree(path, ignore_errors=True)
    # copies in the old place go as soon as nothing uses them (fit() replaces the ones in use)
    try:
        legacy = [os.path.join(legacy_wallpapers_dir(), n) for n in os.listdir(legacy_wallpapers_dir()) if n.startswith(PREFIX)]
    except OSError:
        legacy = []
    for path in legacy:
        if path.rstrip("/") not in in_use:
            shutil.rmtree(path, ignore_errors=True)


def synced_file():
    state = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return os.path.join(state, "surface-overdrive", "wallpaper-synced")


def read_synced():
    try:
        with open(synced_file()) as f:
            return f.read().strip()
    except OSError:
        return None


def write_synced(value):
    os.makedirs(os.path.dirname(synced_file()), exist_ok=True)
    with open(synced_file(), "w") as f:
        f.write(value + "\n")


def plasma_theme_is_dark():
    """Whether the Plasma style is a dark one: Plasma then shows the dark variant of a wallpaper package (Fedora's look sets
    Breeze Dark, so F44 is blue on the desktop and green-white in its light variant)."""
    for name in ("plasmarc", os.path.join("kdedefaults", "plasmarc")):
        try:
            with open(os.path.join(config_dir(), name)) as f:
                text = f.read()
        except OSError:
            continue
        m = re.search(r"^\[Theme\][^\[]*?^name=(.+)$", text, re.M | re.S)
        if m:
            return "dark" in m.group(1).lower()
    return False


def screen_pictures(location, screen, dark=False):
    """(landscape, portrait) JPEG bytes of a wallpaper at the size of the screen, in the variant the desktop shows: the
    package's own when it has them (the fitted ones and Fedora's do), made from its biggest picture otherwise."""
    import tempfile
    long_side, short_side = max(screen), min(screen)
    sizes = ((long_side, short_side), (short_side, long_side))
    variant = "images_dark" if dark and os.path.isdir(os.path.join(location, "contents", "images_dark")) else "images"
    folder = os.path.join(location, "contents", variant)
    found = {}
    if os.path.isdir(folder):
        for name in os.listdir(folder):
            for size in sizes:
                if name.lower() in ("%dx%d.jpg" % size, "%dx%d.jpeg" % size):
                    found[size] = os.path.join(folder, name)
    if len(found) < 2:
        srcs = sources(location)
        src = srcs.get(variant) or srcs.get("images")
        if not src:
            raise OSError("no picture in " + location)
        with tempfile.TemporaryDirectory() as tmp:
            write_fitted(src, tmp, screen)
            return tuple(open(os.path.join(tmp, "%dx%d.jpg" % size), "rb").read() for size in sizes)
    return tuple(open(found[size], "rb").read() for size in sizes)


def sync_from_desktop(screen):
    """The lock screen and the login screen take the wallpaper of the desktop, once per change of it."""
    from .loginwallpaper import pack
    desktops = desktop_wallpapers()
    if not desktops:
        return
    value = desktops[sorted(desktops)[0]]
    if value == read_synced():
        return
    location = to_path(value) or default_package()
    url = value or "file://%s/" % location
    if lock_wallpaper() != url:
        set_lock_wallpaper(url)
        print("lock screen: %s (from the desktop)" % url, flush=True)
    try:
        landscape, portrait = screen_pictures(location, screen, plasma_theme_is_dark())
        run = subprocess.run(["pkexec", LOGIN_HELPER], input=pack(landscape, portrait), capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        print("login screen: could not copy %s: %s" % (location, exc), flush=True)
        return
    if run.returncode != 0:
        print("login screen: %s" % run.stderr.decode(errors="replace").strip(), flush=True)
        return
    write_synced(value)
    print("login screen: %s (from the desktop)" % location, flush=True)


def check_once():
    screen = screen_size()
    changed = False
    for desktop_id, value in desktop_wallpapers().items():
        new = fit(value, screen)
        if new:
            set_desktop_wallpaper(desktop_id, new)
            print("desktop %s: %s -> %s" % (desktop_id, value or "(default)", new), flush=True)
            changed = True
    sync_from_desktop(screen)
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
