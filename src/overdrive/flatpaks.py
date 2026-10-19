"""The apps of the image that come as Flatpaks: removed once, then preinstalled.

The image declares the apps it wants in /usr/share/flatpak/preinstall.d (installed with `flatpak preinstall`, which leaves an
app alone once the user has removed it) and the apps it does not want in REMOVE_LIST: those were put there by Kinoite's
installer, and each is uninstalled once only, so that installing it again by hand sticks. Runs at boot (no network: it tries
again at the next one).
"""
import subprocess
import sys
from pathlib import Path

REMOVE_LIST = Path("/usr/share/surface-overdrive/flatpak-remove.list")
DONE = Path("/var/lib/surface-overdrive/flatpaks-removed")


def wanted_gone(text):
    """App IDs of the remove list: one per line, # comments."""
    return [line.split("#", 1)[0].strip() for line in text.splitlines() if line.split("#", 1)[0].strip()]


def installed():
    out = subprocess.run(["flatpak", "list", "--system", "--app", "--columns=application"],
                         capture_output=True, text=True, check=True).stdout
    return set(out.split())


def flatpak(*args):
    # flatpak wants a session bus (for the authenticator of the OCI remote of Fedora), which a system service has not
    return subprocess.run(["dbus-run-session", "--", "flatpak", *args], check=False).returncode


def main():
    done = set(DONE.read_text().split()) if DONE.exists() else set()
    if REMOVE_LIST.exists():
        present = installed()
        for app in wanted_gone(REMOVE_LIST.read_text()):
            if app in done:
                continue
            if app in present and flatpak("uninstall", "--system", "-y", "--noninteractive", app) != 0:
                continue
            done.add(app)
        DONE.parent.mkdir(parents=True, exist_ok=True)
        DONE.write_text("".join(app + "\n" for app in sorted(done)))
    status = flatpak("preinstall", "--system", "-y", "--noninteractive")
    if status == 0:
        flatpak("uninstall", "--system", "-y", "--noninteractive", "--unused")
    return status


if __name__ == "__main__":
    sys.exit(main())
