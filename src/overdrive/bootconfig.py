"""Installs the GRUB overrides of the image into /boot/grub2/user.cfg.

/boot is not part of the ostree image, so a boot-time service keeps a marked block in user.cfg up to date (grub.cfg sources that
file after its own defaults). Anything else the user wrote in the file is left alone.
"""
import sys
from pathlib import Path

BEGIN = "# BEGIN surface-overdrive (managed by overdrive-bootconfig, do not edit between the markers)"
END = "# END surface-overdrive"
SOURCE = Path("/usr/share/overdrive/grub-user.cfg")
TARGET = Path("/boot/grub2/user.cfg")


def merge(existing, block):
    """The text of user.cfg with our block present exactly once and up to date."""
    managed = "%s\n%s\n%s\n" % (BEGIN, block.strip("\n"), END)
    if BEGIN in existing and END in existing:
        head, rest = existing.split(BEGIN, 1)
        _, tail = rest.split(END, 1)
        return head + managed + tail.lstrip("\n")
    return existing + ("" if not existing or existing.endswith("\n") else "\n") + managed


def install(source=SOURCE, target=TARGET):
    """True when the file was changed."""
    block = source.read_text()
    existing = target.read_text() if target.exists() else ""
    merged = merge(existing, block)
    if merged == existing:
        return False
    target.write_text(merged)
    return True


def main():
    try:
        changed = install()
    except OSError as e:
        print("could not install the GRUB overrides: %s" % e, file=sys.stderr)
        return 1
    print("GRUB overrides %s" % ("installed" if changed else "already up to date"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
