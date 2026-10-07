"""Health checks: is every fix of the image working on this tablet?

Each check has a stable id, a group, a status (ok, warn, fail or na), a short detail, and three texts that the settings page shows:
what the fix does, how it works, and what to do when it is not green. The checks only read the system; they never change it.
`System` is the only thing that touches the machine, so the checks can be tested with a fake one.
"""
import glob
import json
import os
import subprocess
from dataclasses import asdict, dataclass

OK, WARN, FAIL, NA = "ok", "warn", "fail", "na"
MODULES = ("ov8865", "ov5693", "nxp_nci", "nxp_nci_i2c", "intel_hid")
KMODS_JSON = "/usr/share/surface-overdrive/kmods.json"
MOK_CERT = "/usr/share/surface-overdrive/mok.der"


class System:
    """Reads files and runs commands on the real machine."""

    def read(self, path):
        try:
            with open(path) as f:
                return f.read()
        except OSError:
            return None

    def exists(self, path):
        return os.path.exists(path)

    def readable(self, path):
        return os.access(path, os.R_OK)

    def glob(self, pattern):
        return sorted(glob.glob(pattern))

    def run(self, cmd, timeout=8):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return r.returncode, (r.stdout + r.stderr).strip()
        except (OSError, subprocess.SubprocessError) as exc:
            return 127, str(exc)

    def kernel(self):
        return os.uname().release


@dataclass
class Check:
    id: str
    group: str
    title: str
    status: str
    detail: str = ""
    what: str = ""
    how: str = ""
    fix: str = ""


# id -> (what it does, how it works, what to do when it is not green)
INFO = {
    "modules": (
        "Linux ships the camera, NFC and volume-button drivers without the Surface-specific changes. The image carries patched versions of four of them.",
        "They are built in CI against the exact kernel of the image, signed with the project key and installed in /usr/lib/modules/<kernel>/updates/, "
        "which the system prefers over the stock ones. A flag (O) in /proc/modules marks an out-of-tree module.",
        "A stock module means the patched one was not loaded: check that the signing key is enrolled (Secure Boot) and restart. If that does not help the "
        "image of this kernel is missing a module: wait for the next image or roll back."),
    "kernel-match": (
        "The patched modules are built for one exact kernel.",
        "/usr/share/surface-overdrive/kmods.json records the kernel they were built for.",
        "A mismatch should not happen with an image. If it does, the image is inconsistent: roll back to the previous deployment."),
    "libcamera": (
        "libcamera is the camera stack behind Kamoso, Firefox and video calls. The patches fix crashes, the mirrored rear camera, autofocus, exposure, "
        "black level, the picture at start-up and add the live settings.",
        "Fedora's libcamera package is rebuilt in CI with the patches in patches/libcamera/ and replaces the stock one in the image.",
        "A stock libcamera means the patch series did not apply to the version in this image and CI shipped the stock one: the cameras work, without the fixes."),
    "cameras": (
        "The rear and front cameras show up as PipeWire sources, which is how applications get them.",
        "WirePlumber runs libcamera and publishes one node per camera (LNK0 is the rear one, LNK1 the front one). Camera access exists only for "
        "the user with an active desktop session.",
        "Log in on the desktop first. If a camera is still missing, restart the camera service: systemctl --user restart wireplumber."),
    "tuning": (
        "Exposure and black-level tuning of both sensors.",
        "/usr/share/libcamera/ipa/ipu3/<sensor>.yaml, found by libcamera before its generic file.",
        "Missing files mean the image is incomplete."),
    "nfc": (
        "Reads NFC tags and shows a notification with their content.",
        "The kernel driver exposes /sys/class/nfc/nfc0; overdrive-nfcd (a system service) owns the reader and overdrive-nfc-notify (a user service) "
        "shows the notification.",
        "Without nfc0 the patched nxp_nci_i2c module is not loaded. If the adapter is there but the service is not active: systemctl restart overdrive-nfcd."),
    "pen-battery": (
        "Hides the fake pen battery that always reads 0%.",
        "A HID-BPF program rewrites the report descriptor of the digitizer when it is added; a udev rule loads it. "
        "An empty file /etc/udev/rules.d/80-overdrive-stylus.rules switches it off.",
        "If a battery named hid-...-battery is listed, the program did not load: restart the tablet."),
    "volume-hold": (
        "Holding a device volume button keeps changing the volume.",
        "The patched intel_hid module reports the real press and release of the buttons; module parameter volume_hold switches it.",
        "overdrivectl volume-hold on"),
    "audio": (
        "Louder speakers and a sane microphone level.",
        "A virtual sink applies a fixed gain to the speakers (the hardware has no headroom). The internal microphone path is limited to +18 dB "
        "with the boost off.",
        "If the default output is not 'boosted_speakers', restart PipeWire: systemctl --user restart pipewire wireplumber."),
    "secure-boot": (
        "With Secure Boot on, the kernel only loads signed modules.",
        "The project key signs the modules; its certificate was enrolled once in the firmware (MOK).",
        "If the key is not enrolled the patched modules are refused: enrol it again with mokutil --import /usr/share/surface-overdrive/mok.der and restart."),
    "image": (
        "Which system image is running.",
        "rpm-ostree reports the booted deployment: its origin, version and date.",
        "An old image means updates are not arriving: check the network and run rpm-ostree upgrade."),
}


def _check(cid, group, title, status, detail=""):
    what, how, fix = INFO.get(cid, ("", "", ""))
    return Check(cid, group, title, status, detail, what, how, fix)


def check_modules(system):
    text = system.read("/proc/modules") or ""
    lines = {line.split()[0]: line for line in text.splitlines() if line}
    problems, stock, ours = [], [], []
    for name in MODULES:
        line = lines.get(name)
        if line is None:
            problems.append(name)
        elif "(O)" in line:
            ours.append(name)
        else:
            stock.append(name)
    if problems or stock:
        parts = []
        if stock:
            parts.append("stock module loaded: " + ", ".join(stock))
        if problems:
            parts.append("not loaded: " + ", ".join(problems))
        return _check("modules", "Kernel", "Patched kernel modules", FAIL if stock else WARN, "; ".join(parts))
    return _check("modules", "Kernel", "Patched kernel modules", OK, "%d modules, our build" % len(ours))


def check_kernel_match(system):
    raw = system.read(KMODS_JSON)
    if raw is None:
        return _check("kernel-match", "Kernel", "Modules built for this kernel", NA, "no build record (not running an Overdrive image)")
    try:
        built = json.loads(raw)["kernel"]
    except (ValueError, KeyError):
        return _check("kernel-match", "Kernel", "Modules built for this kernel", WARN, "unreadable build record")
    running = system.kernel()
    if built == running:
        return _check("kernel-match", "Kernel", "Modules built for this kernel", OK, running)
    return _check("kernel-match", "Kernel", "Modules built for this kernel", FAIL, "built for %s, running %s" % (built, running))


def check_libcamera(system):
    rc, out = system.run(["rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}", "libcamera"])
    if rc != 0:
        return _check("libcamera", "Cameras", "Patched libcamera", FAIL, "libcamera is not installed")
    if "overdrive" in out:
        return _check("libcamera", "Cameras", "Patched libcamera", OK, out)
    return _check("libcamera", "Cameras", "Patched libcamera", WARN, "%s: the stock package, without the fixes" % out)


def check_cameras(system):
    rc, out = system.run(["pw-cli", "ls", "Node"])
    if rc != 0:
        return _check("cameras", "Cameras", "Cameras visible to applications", NA, "PipeWire is not running (no desktop session?)")
    missing = [label for lnk, label in (("LNK0", "rear"), ("LNK1", "front")) if "libcamera_input.__SB_.PCI0." + lnk not in out]
    if not missing:
        return _check("cameras", "Cameras", "Cameras visible to applications", OK, "rear and front")
    return _check("cameras", "Cameras", "Cameras visible to applications", FAIL, "missing: " + ", ".join(missing))


def check_tuning(system):
    missing = [s for s in ("ov5693", "ov8865") if not system.exists("/usr/share/libcamera/ipa/ipu3/%s.yaml" % s)]
    if missing:
        return _check("tuning", "Cameras", "Sensor tuning", FAIL, "missing: " + ", ".join(missing))
    return _check("tuning", "Cameras", "Sensor tuning", OK, "front and rear")


def check_nfc(system):
    if not system.exists("/sys/bus/acpi/devices/NXP3001:00"):
        return _check("nfc", "Devices", "NFC reader", NA, "no NXP3001 controller on this tablet")
    if not system.exists("/sys/class/nfc/nfc0"):
        return _check("nfc", "Devices", "NFC reader", FAIL, "/sys/class/nfc/nfc0 is missing")
    rc, out = system.run(["systemctl", "is-active", "overdrive-nfcd"])
    if out.strip() == "active":
        return _check("nfc", "Devices", "NFC reader", OK, "adapter nfc0, service active")
    return _check("nfc", "Devices", "NFC reader", WARN, "adapter nfc0 present, service %s" % (out.strip() or "unknown"))


def check_pen_battery(system):
    fake = [p for p in system.glob("/sys/class/power_supply/hid-*-battery-*")]
    masked = system.exists("/etc/udev/rules.d/80-overdrive-stylus.rules")
    if masked:
        return _check("pen-battery", "Devices", "Pen battery filter", NA, "switched off by the user")
    if fake:
        return _check("pen-battery", "Devices", "Pen battery filter", FAIL, "the fake battery %s is present" % os.path.basename(fake[0]))
    return _check("pen-battery", "Devices", "Pen battery filter", OK, "no fake battery")


def check_volume_hold(system):
    value = (system.read("/sys/module/intel_hid/parameters/volume_hold") or "").strip()
    if not value:
        return _check("volume-hold", "Devices", "Volume buttons hold to repeat", FAIL, "the patched intel_hid module is not loaded")
    return _check("volume-hold", "Devices", "Volume buttons hold to repeat", OK, "on" if value in ("Y", "1") else "off (by choice)")


def check_audio(system):
    rc, sink = system.run(["pactl", "get-default-sink"])
    path = system.read("/usr/share/alsa-card-profile/mixer/paths/analog-input-internal-mic.conf") or ""
    problems = []
    if rc == 0 and sink.strip() != "boosted_speakers":
        problems.append("default output is %s" % sink.strip())
    if "Surface Overdrive" not in path:
        problems.append("microphone path not limited")
    if problems:
        return _check("audio", "Audio", "Speakers and microphone", WARN, "; ".join(problems))
    return _check("audio", "Audio", "Speakers and microphone", OK if rc == 0 else NA, "boosted speakers, microphone limited" if rc == 0 else "no sound server")


def check_secure_boot(system):
    rc, state = system.run(["mokutil", "--sb-state"])
    first = state.splitlines()[0] if state else "unknown"
    if "disabled" in first.lower():
        return _check("secure-boot", "System", "Secure Boot and the signing key", OK, "Secure Boot is off: unsigned modules are accepted")
    if not system.exists(MOK_CERT):
        return _check("secure-boot", "System", "Secure Boot and the signing key", NA, first)
    if not system.readable(MOK_CERT):
        return _check("secure-boot", "System", "Secure Boot and the signing key", WARN, "cannot read the certificate to check whether the key is enrolled")
    rc, out = system.run(["mokutil", "--test-key", MOK_CERT])
    if "already enrolled" in out:
        return _check("secure-boot", "System", "Secure Boot and the signing key", OK, "key enrolled")
    return _check("secure-boot", "System", "Secure Boot and the signing key", FAIL, "the signing key is not enrolled")


def check_image(system):
    rc, out = system.run(["rpm-ostree", "status", "--json"], timeout=15)
    if rc != 0:
        return _check("image", "System", "System image", NA, "rpm-ostree is not available")
    try:
        booted = next(d for d in json.loads(out)["deployments"] if d.get("booted"))
    except (ValueError, KeyError, StopIteration):
        return _check("image", "System", "System image", WARN, "cannot read the booted deployment")
    origin = booted.get("container-image-reference") or booted.get("origin", "")
    return _check("image", "System", "System image", OK, "%s (%s)" % (booted.get("version", "?"), origin))


CHECKS = (check_modules, check_kernel_match, check_libcamera, check_cameras, check_tuning, check_nfc,
          check_pen_battery, check_volume_hold, check_audio, check_secure_boot, check_image)


def run_all(system=None):
    system = system or System()
    return [fn(system) for fn in CHECKS]


def overall(checks):
    statuses = {c.status for c in checks}
    return FAIL if FAIL in statuses else WARN if WARN in statuses else OK


def as_json(checks):
    return json.dumps({"overall": overall(checks), "checks": [asdict(c) for c in checks]}, indent=2)
