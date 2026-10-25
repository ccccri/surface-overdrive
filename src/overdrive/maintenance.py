"""Looking after the installation: saving and restoring the settings, repairing a fix that stopped working, the system images
that can be booted, and a report of the state for a bug report.

Everything here answers with plain data; overdrivectl prints it as JSON for the Software Update page.
"""
import datetime
import json
import os
import re
import subprocess
import time

from . import health, userconfig

FORMAT = "surface-overdrive-settings"
VERSION = 1
MAX_FILE = 512 * 1024                      # no settings file of ours comes near this
# What a settings file may hold, as paths under ~/.config/surface-overdrive. Anything else in a file is refused, so a file
# from somewhere else can never write outside these.
ALLOWED = (r"audio\.json", r"ui\.json", r"camera/[A-Za-z0-9_-]+\.profile", r"presets/(front|rear)/[A-Za-z0-9._-]+\.json")
REPO = "ccccri/surface-overdrive"


PROFILE_LINE = re.compile(r"[a-z_]{1,32}( -?\d{1,9}(\.\d{1,9})?(e[-+]?\d{1,3})?){0,8}")


def _allowed(rel):
    return ".." not in rel and len(os.path.basename(rel)) <= 80 and any(re.fullmatch(p, rel) for p in ALLOWED)


def _well_formed(rel, text):
    """The content is what a file of this kind holds: a JSON object, or the lines of a camera profile (a name and numbers).
    The camera profile is read by the camera service itself, so nothing else may get into it."""
    if "\x00" in text:
        return False
    if rel.endswith(".json"):
        try:
            return isinstance(json.loads(text), dict)
        except ValueError:
            return False
    return all(not line.strip() or line.lstrip().startswith("#") or PROFILE_LINE.fullmatch(line.strip()) for line in text.splitlines())


def _state_dir():
    d = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "surface-overdrive")
    os.makedirs(d, exist_ok=True)
    return d


# ---- settings: one file out, one file in ----
def collect():
    """Every settings file of the user as {relative path: text}."""
    files = {}
    root = userconfig.CONFIG
    for folder, _dirs, names in os.walk(root):
        for name in sorted(names):
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, root)
            if not _allowed(rel) or os.path.getsize(path) > MAX_FILE:
                continue
            try:
                with open(path) as f:
                    files[rel] = f.read()
            except (OSError, UnicodeDecodeError):
                pass
    return files


def summary(files):
    """What a set of files holds, in words, for the confirmation before an import."""
    out = []
    try:
        audio = json.loads(files.get("audio.json", "{}"))
    except ValueError:
        audio = {}
    if isinstance(audio, dict) and audio:
        presets = audio.get("presets") if isinstance(audio.get("presets"), dict) else {}
        own = len(presets.get("eq") or {}) + len(presets.get("input") or {})
        out.append("Sound: equalizer, boost and microphone settings" + (", %d profile%s of yours" % (own, "" if own == 1 else "s") if own else ""))
    for cam, sensor in (("rear", "ov8865"), ("front", "ov5693")):
        parts = []
        if "camera/%s.profile" % sensor in files:
            parts.append("adjustments")
        n = sum(1 for rel in files if rel.startswith("presets/%s/" % cam))
        if n:
            parts.append("%d preset%s" % (n, "" if n == 1 else "s"))
        if parts:
            out.append("%s camera: %s" % (cam.capitalize(), ", ".join(parts)))
    return out


def export_settings(path):
    files = collect()
    data = {"format": FORMAT, "version": VERSION, "created": datetime.datetime.now().isoformat(timespec="seconds"), "files": files}
    try:
        if os.path.isdir(path):
            raise IsADirectoryError(path)
        userconfig.write_atomic(path, json.dumps(data, indent=1))
    except OSError as exc:
        return {"result": "failed", "error": "The file could not be written there (%s)." % (exc.strerror or "error")}
    return {"result": "ok", "path": path, "contents": summary(files)}


def read_settings(path):
    """(files, error). The files of a settings file after every check, or the reason it is refused."""
    try:
        if not os.path.isfile(path):                     # not a folder, and not a device that never ends
            return None, "This is not a settings file: it could not be read."
        with open(path) as f:
            text = f.read(16 * MAX_FILE + 1)
        if len(text) > 16 * MAX_FILE:
            return None, "This file is too large to be a settings file."
        data = json.loads(text)
    except (OSError, ValueError, UnicodeDecodeError):
        return None, "This is not a settings file: it could not be read."
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        return None, "This is not a Surface settings file."
    if data.get("version") != VERSION:
        return None, "This settings file comes from a different version (%s) and cannot be read." % data.get("version")
    files = data.get("files")
    if not isinstance(files, dict) or not files:
        return None, "This settings file is empty."
    for rel, text in files.items():
        if not isinstance(rel, str) or not isinstance(text, str) or not _allowed(rel) or len(text) > MAX_FILE:
            return None, "This settings file holds something that does not belong in it (%s)." % str(rel)[:60]
        if not _well_formed(rel, text):
            return None, "A part of this settings file is damaged (%s)." % rel[:60]
    return files, ""


def inspect_settings(path):
    files, error = read_settings(path)
    return {"result": "ok", "contents": summary(files)} if files is not None else {"result": "refused", "error": error}


def _write_all(files):
    root = userconfig.CONFIG
    for rel in list(collect()):                         # what is there now and not in the file goes
        if rel not in files:
            try:
                os.remove(os.path.join(root, rel))
            except FileNotFoundError:
                pass
    for rel, text in files.items():
        userconfig.write_atomic(os.path.join(root, rel), text)


def backup_path():
    return os.path.join(_state_dir(), "settings-before-import.json")


def _apply_now():
    """Make the running system follow the files: the sound filters now; the cameras read their file by themselves."""
    try:
        from .audio import eq, mic
        mic.apply()
        eq.apply_active()
    except Exception:                                    # no sound server (a text console): the files are in place anyway
        pass


def import_settings(path):
    files, error = read_settings(path)
    if files is None:
        return {"result": "refused", "error": error}
    before = collect()
    if export_settings(backup_path())["result"] != "ok":     # no way back, no import
        return {"result": "failed", "error": "The settings of now could not be kept aside, so nothing was changed."}
    try:
        _write_all(files)
    except OSError as exc:
        try:
            _write_all(before)                               # half an import is worse than none
        except OSError:
            pass
        return {"result": "failed", "error": "The settings could not be written (%s). Nothing was changed." % (exc.strerror or "error")}
    _apply_now()
    return {"result": "ok", "contents": summary(files), "undo": True}


def undo_import():
    files, error = read_settings(backup_path())
    if files is None:
        return {"result": "refused", "error": "There is no earlier state to go back to."}
    _write_all(files)
    _apply_now()
    os.remove(backup_path())
    return {"result": "ok", "contents": summary(files)}


# ---- repairs ----
# check id -> (what the button does, command, needs the administrator). Only what is safe to try and often enough: restarting
# the service a check depends on. A fix that needs more than that keeps its explanation only.
REPAIRS = {
    "audio": ("restarts the service that loads the boost and equalizer", ["systemctl", "--user", "restart", "overdrive-audio-route.service"], False),
    "cameras": ("restarts the camera service of the desktop", ["systemctl", "--user", "restart", "wireplumber@video-capture.service"], False),
    "nfc": ("restarts the NFC reader service", ["systemctl", "restart", "overdrive-nfcd.service"], True),
}


def repairable(check_id):
    return check_id in REPAIRS


def repair(check_id, run=subprocess.run, settle=4.0):
    """Try the repair of one check, then run the check again. {"result": ok|failed|refused, "status", "detail"}."""
    if check_id not in REPAIRS:
        return {"result": "refused", "error": "There is no automatic repair for this."}
    _what, command, root = REPAIRS[check_id]
    try:
        done = run((["pkexec"] if root else []) + command, capture_output=True, text=True, timeout=60)
        code, message = done.returncode, (done.stderr or "").strip()
    except (OSError, subprocess.SubprocessError) as exc:
        code, message = 127, str(exc)
    if code != 0:
        return {"result": "failed", "error": message or "The repair could not be run."}
    time.sleep(settle)                                   # a restarted service needs a moment before the check is fair
    for check in health.run_all():
        if check.id == check_id:
            return {"result": "ok" if check.status in (health.OK, health.NA) else "failed", "status": check.status, "detail": check.detail}
    return {"result": "failed", "error": "The check is gone."}


# ---- system images ----
def _when(timestamp):
    try:
        return datetime.datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OSError):
        return ""


def images(run=subprocess.run):
    """The system images on the disk, newest first as rpm-ostree lists them: {"images": [{version, built, state}], "can_go_back"}.
    state: "in use", "next" (starts at the next restart) or "previous"."""
    try:
        data = json.loads(run(["rpm-ostree", "status", "--json"], capture_output=True, text=True, timeout=20).stdout)
        deployments = data.get("deployments", [])
    except (OSError, ValueError, subprocess.SubprocessError, AttributeError):
        return {"images": [], "can_go_back": False, "error": "The system images could not be read."}
    booted_built = next((int(d.get("timestamp") or 0) for d in deployments if d.get("booted")), 0)
    out = []
    booted_seen = False
    for d in deployments:
        if d.get("booted"):
            state, booted_seen = "in use", True
        else:
            state = "previous" if booted_seen else "next"
        out.append({"version": str(d.get("version") or "?"), "built": _when(d.get("timestamp")), "state": state,
                    # an image that starts next and is older than the one in use is there because of "go back": that can be undone
                    "went_back": state == "next" and 0 < int(d.get("timestamp") or 0) < booted_built,
                    "digest": str(d.get("container-image-reference-digest") or d.get("checksum") or "")[:19]})
    booted = next((d for d in deployments if d.get("booted")), {})
    return {"images": out, "can_go_back": any(i["state"] == "previous" for i in out) and not any(i["state"] == "next" for i in out),
            "source": source(str(booted.get("container-image-reference") or booted.get("origin") or ""))}


def source(reference):
    """Where updates come from, in words: the reference names the registry the image is pulled from."""
    if "ghcr.io/" in reference:
        return "the images built on GitHub"
    if "localhost" in reference or "127.0.0.1" in reference:
        return "a development computer (test images, not the ones built on GitHub)"
    if "fedoraproject.org" in reference or "fedora" in reference and "overdrive" not in reference:
        return "Fedora (stock Kinoite, without the Surface fixes)"
    return reference or "unknown"


def changes(run=subprocess.run):
    """Packages that differ between the image in use and the other one on the disk, as lines of text (at most 40)."""
    try:
        text = run(["rpm-ostree", "db", "diff"], capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return {"lines": [], "error": "The difference could not be read."}
    lines = [line.strip() for line in text.splitlines() if line.startswith("  ")]
    return {"lines": lines[:40], "more": max(0, len(lines) - 40)}


def go_back(run=subprocess.run):
    """Make the previous image the one that starts next. rpm-ostree asks for the administrator password itself."""
    try:
        done = run(["rpm-ostree", "rollback"], capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"result": "failed", "error": str(exc)}
    if done.returncode != 0:
        return {"result": "failed", "error": (done.stderr or done.stdout or "").strip()[-300:]}
    return {"result": "ok"}


def cancel_next(run=subprocess.run):
    """Undo "go back": the image in use is again the one that starts next. Done by swapping the two once more; an update that
    waits for the restart is never touched here (dropping it would throw the download away)."""
    if not any(i["went_back"] for i in images(run)["images"]):
        return {"result": "refused", "error": "There is nothing to undo."}
    return go_back(run)


# ---- report for a bug report ----
def _scrub(text):
    """Take out what identifies the person or the network: the user name, the host name, addresses, serial-like numbers."""
    user = os.environ.get("USER") or ""
    host = os.uname().nodename
    for word, mark in ((user, "<user>"), (host, "<host>")):
        if len(word) >= 3:
            text = re.sub(re.escape(word), mark, text)
    text = re.sub(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b", "<mac>", text)
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<ip>", text)
    text = re.sub(r"\b(?:[0-9A-Fa-f]{1,4}:){4,7}[0-9A-Fa-f]{1,4}\b", "<ip6>", text)
    return text


def _out(command, timeout=25):
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        return (done.stdout + done.stderr).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return "(could not run: %s)" % exc


def report_text():
    checks = health.run_all()
    parts = ["Surface Overdrive report, %s" % datetime.datetime.now().isoformat(timespec="seconds"), ""]
    parts.append("== State of the fixes: %s" % health.overall(checks))
    parts += ["[%s] %s: %s" % (c.status, c.title, c.detail) for c in checks]
    info = images()
    parts += ["", "== System images"] + ["%s  %s  %s  %s" % (i["state"], i["version"], i["built"], i["digest"]) for i in info["images"]]
    parts += ["", "== Kernel", os.uname().release]
    sections = (
        ("Our services", ["systemctl", "--no-pager", "--plain", "list-units", "overdrive-*"]),
        ("Our user services", ["systemctl", "--user", "--no-pager", "--plain", "list-units", "overdrive-*"]),
        ("Log of our services, this start", ["journalctl", "-b", "--no-pager", "-o", "short", "-n", "150", "-u", "overdrive-nfcd", "-u", "overdrive-bootconfig"]),
        ("Log of our user services, this start", ["journalctl", "--user", "-b", "--no-pager", "-o", "short", "-n", "150", "-u", "overdrive-audio-route",
                                                  "-u", "overdrive-nfc-notify", "-u", "overdrive-osk-guard", "-u", "overdrive-health-watch"]),
        ("Sound and camera services, warnings of this start", ["journalctl", "--user", "-b", "--no-pager", "-o", "short", "-p", "warning", "-n", "120",
                                                              "-u", "pipewire", "-u", "wireplumber", "-u", "wireplumber@video-capture"]),
        ("System Settings and the desktop, errors of this start", ["journalctl", "--user", "-b", "--no-pager", "-o", "short", "-p", "err", "-n", "80"]),
        ("Kernel messages of our modules", ["sh", "-c", "journalctl -k -b --no-pager -o short 2>/dev/null | grep -i -E 'ov8865|ov5693|nxp|nci|intel_hid|intel-hid|ipu3|dw9719|module verification' | tail -80"]),
        ("Crashes of the last week", ["coredumpctl", "list", "--no-pager", "--since", "-7days"]),
    )
    for title, command in sections:
        parts += ["", "== " + title, _out(command) or "(nothing)"]
    return _scrub("\n".join(parts)) + "\n"


def write_report(folder=None):
    """Write the report next to the user's documents and say where, with the address of a new issue that names it."""
    folder = folder or os.path.expanduser("~/Documents")
    if not os.path.isdir(folder):
        folder = os.path.expanduser("~")
    path = os.path.join(folder, "surface-report-%s.txt" % datetime.datetime.now().strftime("%Y-%m-%d-%H%M"))
    text = report_text()
    userconfig.write_atomic(path, text)
    checks = health.run_all()
    bad = [c.title for c in checks if c.status in (health.WARN, health.FAIL)]
    body = ("**What happened**\n\n(describe it here)\n\n**State of the fixes:** %s%s\n\n"
            "**Report file:** drag `%s` from the Documents folder into this box to attach it.\n"
            % (health.overall(checks), (" (" + ", ".join(bad) + ")") if bad else "", os.path.basename(path)))
    from urllib.parse import quote
    url = "https://github.com/%s/issues/new?title=%s&body=%s" % (REPO, quote("Problem on the Surface: "), quote(body))
    return {"result": "ok", "path": path, "url": url, "lines": text.count("\n")}
