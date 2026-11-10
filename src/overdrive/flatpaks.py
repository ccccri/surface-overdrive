"""The apps of the image that come as Flatpaks: removed once, then preinstalled.

The image declares the apps it wants in /usr/share/flatpak/preinstall.d (installed with `flatpak preinstall`, which leaves an
app alone once the user has removed it) and the apps it does not want in REMOVE_LIST: those were put there by Kinoite's
installer, and each is uninstalled once only, so that installing it again by hand sticks. Runs at boot (no network: it tries
again at the next one).

Camera apps get two more things, once each (a user's later change sticks): no raw device nodes, so that the camera reaches
them through PipeWire (with all devices, Chromium and OBS see the fourteen raw IPU3 nodes of the image processor and none
works), and, per user, Chromium's PipeWire camera turned on in its flags file.

Moonlight gets, per user, the image's touch-cancel library preloaded (src/moonlight-touch): when KWin takes a three-finger
gesture its fingers are canceled, which the Flatpak's sdl2-compat drops, and the PC kept them pressed. The library is
copied into the app's own directory (the sandbox does not see /usr) at every login, so a new image brings a new one; the
override is set once. Its "Optimize mouse for remote desktop" is turned on once too: Moonlight sends the Surface pen as
a mouse, which otherwise moves relative to where the pointer was.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

REMOVE_LIST = Path("/usr/share/surface-overdrive/flatpak-remove.list")
DONE = Path("/var/lib/surface-overdrive/flatpaks-removed")
OVERRIDDEN = Path("/var/lib/surface-overdrive/flatpaks-camera-overridden")

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
MOONLIGHT = "com.moonlight_stream.Moonlight"
TOUCH_LIB = Path("/usr/lib64/surface-overdrive/moonlight-touch-cancel.so")
TOUCH_DONE = "flatpak-moonlight-touch"
MOUSE_DONE = "flatpak-moonlight-absolute-mouse"
MOONLIGHT_CONF = Path(".var/app", MOONLIGHT, "config/Moonlight Game Streaming Project/Moonlight.conf")


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
    # which works for flathub and for an up to date installation (tried on the tablet, 2026-11-03).
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
    if MOONLIGHT in out:
        moonlight_touch(home, Path(userconfig.CONFIG, TOUCH_DONE))
        moonlight_absolute_mouse(home, Path(userconfig.CONFIG, MOUSE_DONE))
    return 0


def with_absolute_mouse(text):
    """Moonlight's settings with absolutemousemode=true in [General] (added, or an existing value changed)."""
    lines = text.splitlines()
    general = next((i for i, line in enumerate(lines) if line.strip() == "[General]"), None)
    if general is None:
        return "[General]\nabsolutemousemode=true\n" + "".join(line + "\n" for line in lines)
    end = next((i for i in range(general + 1, len(lines)) if lines[i].startswith("[")), len(lines))
    for i in range(general + 1, end):
        if lines[i].split("=", 1)[0].strip() == "absolutemousemode":
            lines[i] = "absolutemousemode=true"
            break
    else:
        lines.insert(general + 1, "absolutemousemode=true")
    return "".join(line + "\n" for line in lines)


def moonlight_absolute_mouse(home, state):
    """Once per user (a later change in Moonlight's settings stays), and not while Moonlight runs: it writes its settings
    back when it closes."""
    if state.exists() or subprocess.run(["pgrep", "-x", "moonlight"], capture_output=True, check=False).returncode == 0:
        return
    path = Path(home) / MOONLIGHT_CONF
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(with_absolute_mouse(path.read_text() if path.exists() else ""))
    state.write_text("1\n")


def moonlight_touch(home, state, lib=TOUCH_LIB):
    """The touch-cancel library in Moonlight's directory (refreshed when it differs) and preloaded (once)."""
    if not lib.exists():
        return
    dest = Path(home) / ".var" / "app" / MOONLIGHT / "lib" / lib.name
    data = lib.read_bytes()
    if not dest.exists() or dest.read_bytes() != data:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, dest)
    if not state.exists() and subprocess.run(["flatpak", "override", "--user", "--env=LD_PRELOAD=" + str(dest), MOONLIGHT],
                                             check=False).returncode == 0:
        state.write_text("1\n")


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
    status = flatpak("preinstall", "--system", "-y", "--noninteractive")
    if status == 0:
        flatpak("uninstall", "--system", "-y", "--noninteractive", "--unused")
    return status


if __name__ == "__main__":
    sys.exit(main())
