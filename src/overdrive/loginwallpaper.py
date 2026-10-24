"""overdrive-login-wallpaper: puts the wallpaper of the desktop on the login screen too (run as root through pkexec).

The login screen runs as its own user, which cannot read the home folder: the picture has to be copied to a place of the
system. The user's wallpaper service (overdrive.wallpaper) sends the two screen-sized JPEGs of the wallpaper on standard
input; this program never opens a path given by the user. Each picture is decoded and written again as a plain JPEG (so only
pixels get through), into a wallpaper package in /var/lib/surface-overdrive/login-wallpaper, and the login screen is pointed at
it in /etc/plasmalogin.conf (the only file the login screen reads its wallpaper from; Plasma's Login Screen page writes there
too).

Standard input: MAGIC, then for each picture (landscape, then portrait) its length as 4 bytes big-endian and its bytes.
"""
import io
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

MAGIC = b"OVERDRIVE-WALLPAPER-1\n"
MAX_BYTES = 20 * 1024 * 1024              # per picture: a screen-sized JPEG is well under 2 MB
MAX_SIDE = 8192
DEST = Path("/var/lib/surface-overdrive/login-wallpaper")
CONF = Path("/etc/plasmalogin.conf")
GROUP = ["--group", "Greeter", "--group", "Wallpaper", "--group", "org.kde.image", "--group", "General"]


def pack(landscape, portrait):
    """What the user's side writes to standard input."""
    return MAGIC + b"".join(struct.pack(">I", len(p)) + p for p in (landscape, portrait))


def unpack(data):
    """The two pictures sent by pack(); ValueError when the data is not that."""
    if not data.startswith(MAGIC):
        raise ValueError("not a wallpaper")
    pos, out = len(MAGIC), []
    for _ in range(2):
        if pos + 4 > len(data):
            raise ValueError("truncated")
        (n,) = struct.unpack(">I", data[pos:pos + 4])
        pos += 4
        if n == 0 or n > MAX_BYTES or pos + n > len(data):
            raise ValueError("bad length")
        out.append(data[pos:pos + n])
        pos += n
    if pos != len(data):
        raise ValueError("trailing data")
    return out


def clean_jpeg(data, landscape):
    """The picture decoded and encoded again as a JPEG, with its size; ValueError when it is not a picture of the right shape."""
    from PIL import Image
    try:
        image = Image.open(io.BytesIO(data))
        if image.format not in ("JPEG", "PNG"):
            raise ValueError("not a JPEG or PNG picture")
        w, h = image.size
        if not (0 < w <= MAX_SIDE and 0 < h <= MAX_SIDE) or (w >= h) != landscape:
            raise ValueError("unexpected size %dx%d" % (w, h))
        image = image.convert("RGB")
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError("cannot read the picture: %s" % exc) from None
    out = io.BytesIO()
    image.save(out, "JPEG", quality=92)
    return out.getvalue(), (w, h)


def install(pictures, dest=DEST, conf=CONF):
    """Write the package (all at once: built aside, then swapped in) and the configuration of the login screen."""
    work = dest.with_name(dest.name + ".new")
    old = dest.with_name(dest.name + ".old")
    shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(old, ignore_errors=True)
    images = work / "contents" / "images"
    images.mkdir(parents=True)
    for jpeg, (w, h) in pictures:
        (images / ("%dx%d.jpg" % (w, h))).write_bytes(jpeg)
    (work / "metadata.json").write_text(json.dumps({"KPlugin": {"Id": "surface-overdrive-login", "Name": "Desktop wallpaper",
                                                               "Description": "Copied from the desktop by Surface Overdrive"}}))
    for path in [work] + list(work.rglob("*")):
        os.chmod(path, 0o755 if path.is_dir() else 0o644)
    if dest.exists():
        dest.rename(old)
    work.rename(dest)
    shutil.rmtree(old, ignore_errors=True)

    url = "file://%s/" % dest
    write = ["kwriteconfig6", "--file", str(conf)]
    for key in ("Image", "PreviewImage"):
        subprocess.run(write + GROUP + ["--key", key, url], check=True)


def main():
    data = sys.stdin.buffer.read(len(MAGIC) + 2 * (4 + MAX_BYTES) + 1)
    try:
        landscape, portrait = unpack(data)
        pictures = [clean_jpeg(landscape, True), clean_jpeg(portrait, False)]
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    install(pictures)
    return 0
