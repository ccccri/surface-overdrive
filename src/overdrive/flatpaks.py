"""The apps of the image that come as Flatpaks: removed once, then preinstalled.

The image declares the apps it wants in /usr/share/flatpak/preinstall.d (installed with `flatpak preinstall`, which leaves an
app alone once the user has removed it) and the apps it does not want in REMOVE_LIST: those were put there by Kinoite's
installer, and each is uninstalled once only, so that installing it again by hand sticks. Runs at boot (no network: it tries
again at the next one).

Camera apps get two more things, once each (a user's later change sticks): no raw device nodes, so that the camera reaches
them through PipeWire (with all devices, Chromium and OBS see the fourteen raw IPU3 nodes of the image processor and none
works), and, per user, Chromium's PipeWire camera turned on in its flags file.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

REMOVE_LIST = Path("/usr/share/surface-overdrive/flatpak-remove.list")
DONE = Path("/var/lib/surface-overdrive/flatpaks-removed")
OVERRIDDEN = Path("/var/lib/surface-overdrive/flatpaks-camera-overridden")
UNLISTED = Path("/var/lib/surface-overdrive/flatpaks-oci-unlisted")

# apps that open cameras: they keep the GPU and input devices (game pads), not the raw video nodes
CAMERA_APPS = [
    "io.github.ungoogled_software.ungoogled_chromium",
    "org.chromium.Chromium",
    "com.google.Chrome",
    "com.brave.Browser",
    "com.obsproject.Studio",
]
# Chromium-based apps and the flags file their Flatpak wrapper reads (in ~/.var/app/<app>/config)
CHROMIUM_FLAGS = {
    "io.github.ungoogled_software.ungoogled_chromium": "chromium-flags.conf",
    "org.chromium.Chromium": "chromium-flags.conf",
    "com.google.Chrome": "chrome-flags.conf",
    "com.brave.Browser": "brave-flags.conf",
}
FEATURE = "WebRtcPipeWireCamera"
FLAGS_DONE = "flatpak-chromium-flags"


def wanted_gone(text):
    """App IDs of the remove list: one per line, # comments."""
    return [line.split("#", 1)[0].strip() for line in text.splitlines() if line.split("#", 1)[0].strip()]


def installed():
    out = subprocess.run(["flatpak", "list", "--system", "--app", "--columns=application"],
                         capture_output=True, text=True, check=True).stdout
    return set(out.split())


def flatpak(*args):
    # flatpak wants a session bus for the authenticator of Fedora's OCI remote, which a system service has not. Fedora 45 no
    # longer ships dbus-run-session (dbus-daemon is gone, dbus-broker has no such tool): there flatpak runs without one,
    # which works for flathub and for an up to date installation (tried on the tablet, 2026-11-03); an install from Fedora's OCI
    # remote does not (preinstall_without_oci).
    prefix = ["dbus-run-session", "--"] if shutil.which("dbus-run-session") else []
    return subprocess.run(prefix + ["flatpak", *args], check=False).returncode


def camera_overrides():
    """No raw device nodes for the camera apps, once each (the override applies before an app is installed, too)."""
    done = set(OVERRIDDEN.read_text().split()) if OVERRIDDEN.exists() else set()
    for app in CAMERA_APPS:
        if app not in done and flatpak("override", "--system", "--nodevice=all", "--device=dri", "--device=input",
                                       app) == 0:
            done.add(app)
    OVERRIDDEN.parent.mkdir(parents=True, exist_ok=True)
    OVERRIDDEN.write_text("".join(app + "\n" for app in sorted(done)))


def with_feature(text):
    """The flags file with FEATURE enabled: added to its --enable-features line (Chromium reads only the last one)."""
    lines = text.splitlines()
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip().startswith("--enable-features="):
            if FEATURE not in lines[i].split("=", 1)[1].split(","):
                lines[i] = lines[i].rstrip() + "," + FEATURE
            return "".join(line + "\n" for line in lines)
    return "".join(line + "\n" for line in lines) + "--enable-features=" + FEATURE + "\n"


def user_main(home=None):
    """Per user, at login: Chromium's PipeWire camera on, once per app (its own flags file, left alone afterwards)."""
    from . import userconfig
    home = Path(home or os.path.expanduser("~"))
    state = Path(userconfig.CONFIG, FLAGS_DONE)
    done = set(state.read_text().split()) if state.exists() else set()
    out = subprocess.run(["flatpak", "list", "--app", "--columns=application"], capture_output=True, text=True,
                         check=False).stdout.split()
    for app, name in CHROMIUM_FLAGS.items():
        if app in done or app not in out:
            continue
        path = home / ".var" / "app" / app / "config" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(with_feature(path.read_text() if path.exists() else ""))
        done.add(app)
    userconfig.write_atomic(str(state), "".join(app + "\n" for app in sorted(done)))
    unlist_oci_remotes("--user", Path(userconfig.CONFIG, "flatpak-oci-unlisted"))
    return 0


def output(*args):
    """What a command prints, or nothing when it cannot run (no flatpak where the tests run)."""
    try:
        return subprocess.run(args, capture_output=True, text=True, check=False).stdout
    except OSError:
        return ""


def os_version():
    try:
        for line in open("/etc/os-release"):
            if line.startswith("VERSION_ID="):
                return int(line.split("=", 1)[1].strip().strip('"'))
    except (OSError, ValueError):
        pass
    return None


def old_fedora_pins(pins, version):
    """The pinned Fedora runtimes of an older release than the system's ("runtime/org.fedoraproject.X/arch/f44" with the
    system on 45)."""
    old = []
    for pin in pins:
        parts = pin.strip().split("/")
        if len(parts) == 4 and parts[0] == "runtime" and parts[1].startswith("org.fedoraproject.") \
                and parts[3][:1] == "f" and parts[3][1:].isdigit() and version and int(parts[3][1:]) < version:
            old.append(pin.strip())
    return old


def unpin_old_fedora_runtimes():
    """Kinoite's installer pins the Fedora runtimes it came with, so that "uninstall --unused" never removes them: after the
    image moved to a newer Fedora the old ones stayed, used by nothing (3.2 GB on the tablet, 2026-11-10). Unpinned here,
    they go with the other unused ones; one an app still uses stays."""
    pins = output("flatpak", "pin", "--system").splitlines()
    for pin in old_fedora_pins(pins, os_version()):
        flatpak("pin", "--system", "--remove", pin)


def oci_remotes(scope="--system", listed_only=False):
    """The enabled remotes of a scope that are OCI registries (Fedora's): flatpak asks their authenticator for a token over
    the session bus, which a system service has not. listed_only: those whose apps Discover still lists."""
    out = output("flatpak", "remotes", scope, "--columns=name,url,options")
    names = []
    for line in out.splitlines():
        cols = line.split("\t")
        options = cols[2] if len(cols) > 2 else ""
        if len(cols) >= 2 and cols[1].startswith("oci+") and "disabled" not in options:
            if listed_only and "no-enumerate" in options:
                continue
            names.append(cols[0])
    return names


def unlist_oci_remotes(scope, state):
    """Fedora's OCI remote no longer listed in Discover, once per installation (a later change stays).

    Kinoite has it with Flathub, in the system installation and again in the user's, and Discover showed most apps twice,
    Fedora's without an icon (seen on the tablet, 2026-11-10). With --no-enumerate its apps are no longer offered (Flathub
    has them, unfiltered on Kinoite 45) while what is installed from it keeps its updates."""
    if state.exists():
        return
    for name in oci_remotes(scope, listed_only=True):
        flatpak("remote-modify", scope, "--no-enumerate", name)
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text("1\n")


def preinstall_without_oci():
    """preinstall again with the OCI remotes disabled for the time it takes, put back in any case.

    An app of the image missing on the tablet was installed from the first remote that has it, Fedora's: that needs a
    token from its authenticator over the session bus ("Cannot autolaunch D-Bus without X11 $DISPLAY") and the whole
    preinstall failed at every boot (seen 2026-11-10, kcalc). Without them it comes from Flathub; apps already installed
    from Fedora stay as they are."""
    remotes = oci_remotes()
    if not remotes:
        return 1
    disabled = [r for r in remotes if flatpak("remote-modify", "--system", "--disable", r) == 0]
    try:
        return flatpak("preinstall", "--system", "-y", "--noninteractive")
    finally:
        for r in disabled:
            flatpak("remote-modify", "--system", "--enable", r)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--user" in argv:
        return user_main()
    camera_overrides()
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
    unlist_oci_remotes("--system", UNLISTED)
    status = flatpak("preinstall", "--system", "-y", "--noninteractive")
    if status != 0:
        status = preinstall_without_oci()
    if status == 0:
        unpin_old_fedora_runtimes()
        flatpak("uninstall", "--system", "-y", "--noninteractive", "--unused")
    return status


if __name__ == "__main__":
    sys.exit(main())
