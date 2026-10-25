"""Camera settings: the live profile read by the patched libcamera, and presets built on it.

A profile is a text file ~/.config/surface-overdrive/camera/<sensor>.profile with one "key value ..." per line. The patched
libcamera polls it, so a change shows up in every running application within a fraction of a second. A key that is absent
means "the tuning default". Presets are whole profiles stored under a name in ~/.config/surface-overdrive/presets/<camera>/.
"""
import glob
import json
import os
import re
import subprocess
import time

from . import userconfig

CONFIG = userconfig.CONFIG
PROFILE_DIR = os.environ.get("LIBCAMERA_SURFACE_PROFILE_DIR") or os.path.join(CONFIG, "camera")
PRESET_DIR = os.path.join(CONFIG, "presets")
UI_FILE = os.path.join(CONFIG, "ui.json")
TUNING_DIR = "/usr/share/libcamera/ipa/ipu3"
STATE_DIR = "/dev/shm"
SENSORS = {"front": "ov5693", "rear": "ov8865"}

# Picture sizes offered to applications ("min_width": the smallest width offered, apps take the first size) and what each costs.
SIZES = {
    "front": [(0, "1152x864", "1 MP, 28 fps"), (1536, "1536x1152", "1.8 MP, 28 fps"), (2048, "2048x1536", "3.1 MP, 23 fps"),
              (2560, "2560x1920", "4.9 MP, 20 fps, maximum")],
    "rear": [(0, "1536x1152", "1.8 MP, 30 fps"), (2048, "2048x1536", "3.1 MP, 15 fps"), (2560, "2560x1920", "4.9 MP, 13 fps"),
             (3200, "3200x2400", "7.7 MP, 11 fps, maximum")],
}
# Temporal denoise levels: (minimum weight in 1/256, threshold). Lower weight = stronger. Level 0 is off.
TNR_LEVELS = [(0, 0), (128, 5), (96, 5), (64, 5), (40, 5), (24, 6)]
TNR_NAMES = ["off", "low", "medium", "high", "stronger", "maximum"]
# The level libcamera uses when the profile has no "tnr" (patch 0028): the front sensor is noisier and gets "stronger".
TNR_DEFAULTS = {"rear": 3, "front": 4}
TNR_DEFAULT = TNR_DEFAULTS["rear"]
SIMPLE_KEYS = ("exposure", "gamma", "contrast", "shadows", "highlights", "saturation", "temperature", "tint", "hue", "hue_spin",
               "sharpness")
MAX_FOCUS = 1023


def profile_path(cam):
    return os.path.join(PROFILE_DIR, SENSORS[cam] + ".profile")


def read_profile(cam):
    out = {}
    try:
        with open(profile_path(cam)) as f:
            for line in f:
                words = line.split("#")[0].split()
                if words:
                    try:
                        out[words[0]] = [float(x) for x in words[1:]]
                    except ValueError:
                        pass
    except OSError:
        pass
    return out


def _write_atomic(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def write_profile(cam, values):
    """Atomic: the pipeline polls the file and must never see a half-written one. An empty profile removes the file."""
    path = profile_path(cam)
    if not values:
        try:
            os.remove(path)
        except OSError:
            pass
        return
    lines = ["# Written by Surface Control. Read live by the patched libcamera; delete the file to go back to the tuning defaults."]
    lines += [k + " " + " ".join("%g" % x for x in v) for k, v in values.items()]
    _write_atomic(path, "\n".join(lines) + "\n")


def tuning_black(cam):
    """The black level of the tuning file (Gr, R, B, Gb), the base of the "black point" control."""
    try:
        text = open(os.path.join(TUNING_DIR, SENSORS[cam] + ".yaml")).read()
        m = re.search(r"black:\s*\[([^\]]*)\]", text)
        values = [int(x) for x in m.group(1).split(",")]
        if len(values) == 4:
            return values
    except (OSError, AttributeError, ValueError):
        pass
    return [64, 64, 64, 64]


def tnr_level(tnr, cam="rear"):
    if len(tnr) != 2:
        return TNR_DEFAULTS.get(cam, TNR_DEFAULT)
    return min(range(len(TNR_LEVELS)), key=lambda i: abs(TNR_LEVELS[i][0] - tnr[0]) + abs(TNR_LEVELS[i][1] - tnr[1]))


def controls(cam):
    """The sliders, grouped like a photo editor. 'default' is what the tuning gives when the profile says nothing."""
    return [
        {"group": "Light", "items": [
            {"key": "exposure", "label": "Exposure", "min": -2, "max": 2, "step": 0.1, "default": 0, "unit": "EV",
             "desc": "Brightens or darkens the whole picture by changing the brightness the auto exposure aims for. "
                     "It works on the light the sensor really collects, so it adds less noise than brightening afterwards."},
            {"key": "gamma", "adv": True, "label": "Brightness curve", "min": 1.0, "max": 2.4, "step": 0.05, "default": 1.1,
             "unit": "", "desc": "Higher values lift the dark and middle tones. The picture looks brighter and flatter."},
            {"key": "contrast", "label": "Contrast", "min": 0, "max": 1, "step": 0.05, "default": 0, "unit": "",
             "desc": "Darkens the shadows and brightens the highlights without moving the middle tones."},
            {"key": "shadows", "label": "Shadows", "min": -1, "max": 1, "step": 0.05, "default": 0, "unit": "",
             "desc": "Raises (positive) or lowers (negative) only the dark part of the picture."},
            {"key": "highlights", "label": "Highlights", "min": -1, "max": 1, "step": 0.05, "default": 0, "unit": "",
             "desc": "Lowers (negative) or raises (positive) only the bright part, to recover a bright window or sky."},
            {"key": "blackShift", "adv": True, "label": "Black point", "min": -8, "max": 24, "step": 1, "default": 0, "unit": "",
             "desc": "The level the sensor calls black. Higher gives deeper blacks and a slightly darker picture; too high crushes the shadows."},
        ]},
        {"group": "Color", "items": [
            {"key": "saturation", "label": "Saturation", "min": 0, "max": 2, "step": 0.05, "default": 1, "unit": "",
             "desc": "How vivid the colors are. 0 is black and white, 1 is the natural picture."},
            {"key": "temperature", "label": "Temperature", "min": -1, "max": 1, "step": 0.05, "default": 0, "unit": "",
             "desc": "Moves the colors towards blue (negative, cooler) or orange (positive, warmer)."},
            {"key": "tint", "label": "Tint", "min": -1, "max": 1, "step": 0.05, "default": 0, "unit": "",
             "desc": "Moves the colors towards green (negative) or magenta (positive). Corrects fluorescent light or a cast on skin."},
            {"key": "hue", "label": "Hue shift", "min": -180, "max": 180, "step": 1, "default": 0, "unit": "°",
             "desc": "Rotates all the colors around the color wheel. A creative effect."},
            {"key": "hue_spin", "label": "Rainbow", "min": -360, "max": 360, "step": 5, "default": 0, "unit": "°/s",
             "desc": "Keeps turning the color wheel: the number is the speed in degrees per second, negative turns the other way, 0 is off."},
        ]},
        {"group": "Detail", "items": [
            {"key": "sharpness", "label": "Sharpness", "min": 0, "max": 3, "step": 0.1, "default": 0, "unit": "",
             "desc": "Makes edges crisper. Small differences are ignored so the noise is not sharpened. Uses some CPU at large sizes."},
            {"key": "temporal", "label": "Grain removal", "min": 0, "max": 5, "step": 1, "default": TNR_DEFAULTS.get(cam, TNR_DEFAULT),
             "unit": "level", "names": TNR_NAMES,
             "desc": "Averages with the previous frame: removes the crawling grain on flat areas. Strong levels leave faint trails behind fast movement."},
        ]},
    ]


def _default(cam, key):
    for group in controls(cam):
        for item in group["items"]:
            if item["key"] == key:
                return item["default"]
    raise KeyError(key)


def focus_state(cam):
    """Lens position and sharpness the autofocus last reported (the patched libcamera writes them while a camera is open)."""
    import time
    path = os.path.join(STATE_DIR, "surface-camera-%s.state" % SENSORS[cam])
    out = {}
    try:
        if time.time() - os.path.getmtime(path) > 4:
            return out      # no camera open: the file is old
        for line in open(path):
            k, _, v = line.partition(" ")
            out[k] = float(v)
    except (OSError, ValueError):
        pass
    return out


def settings(cam):
    """Values as the UI shows them: the profile value when present, else the default. 'dirty': anything customised."""
    p = read_profile(cam)
    out = {it["key"]: it["default"] for g in controls(cam) for it in g["items"]}
    for k in SIMPLE_KEYS:
        if p.get(k):
            out[k] = p[k][0]
    if len(p.get("black", [])) == 4:
        out["blackShift"] = round(p["black"][0] - tuning_black(cam)[0])
    if "tnr" in p:
        out["temporal"] = tnr_level(p["tnr"], cam)
    out["minWidth"] = int(p.get("min_width", [0])[0])
    out["mirror"] = bool(p.get("mirror", [0])[0])
    out["flip"] = bool(p.get("flip", [0])[0])
    out["focusManual"] = "focus" in p
    out["focus"] = int(p["focus"][0]) if p.get("focus") else int(focus_state(cam).get("focus", 0))
    out["dirty"] = any(k != "min_width" for k in p)
    return out


# The WirePlumber instance that makes the camera nodes (the image runs a separate one for the cameras, see
# /usr/share/wireplumber/wireplumber.conf.d/90-surface-overdrive-cameras.conf), or the main one where there is no such split.
CAMERA_SERVICE = "wireplumber@video-capture.service"


def camera_service():
    run = subprocess.run(["systemctl", "--user", "is-enabled", CAMERA_SERVICE], capture_output=True, text=True, timeout=10, check=False)
    return CAMERA_SERVICE if run.stdout.strip() in ("enabled", "static", "linked", "alias", "indirect", "generated") else "wireplumber.service"


def camera_nodes():
    """Names of the camera nodes PipeWire has now."""
    try:
        out = subprocess.run(["pw-dump"], capture_output=True, text=True, timeout=10, check=False).stdout
        return {o["info"]["props"].get("node.name", "") for o in json.loads(out or "[]")
                if o.get("type", "").endswith("Node") and "libcamera" in str(o.get("info", {}).get("props", {}).get("node.name", ""))}
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return set()


def restart_camera_service(wait=6.0):
    """Restart what makes the camera nodes (the picture sizes are read then) and wait until the cameras are back, so that a
    preview started right after finds them."""
    before = camera_nodes()
    subprocess.run(["systemctl", "--user", "restart", camera_service()], timeout=30, check=False)
    end = time.time() + wait
    while time.time() < end:
        time.sleep(0.2)
        if before and before <= camera_nodes():
            break


def set_setting(cam, key, value):
    """Change one setting, the others stay. Returns True when the picture size changed (the camera service restarts)."""
    p = read_profile(cam)
    restart = False
    if key in SIMPLE_KEYS:
        if abs(float(value) - _default(cam, key)) < 1e-9:
            p.pop(key, None)
        else:
            p[key] = [round(float(value), 3)]
    elif key == "blackShift":
        base = tuning_black(cam)
        if int(value) == 0:
            p.pop("black", None)
        else:
            p["black"] = [max(0, b + int(value)) for b in base]
    elif key == "temporal":
        if int(value) == TNR_DEFAULTS.get(cam, TNR_DEFAULT):
            p.pop("tnr", None)
        else:
            p["tnr"] = list(TNR_LEVELS[max(0, min(len(TNR_LEVELS) - 1, int(value)))])
    elif key in ("mirror", "flip"):
        if value:
            p[key] = [1]
        else:
            p.pop(key, None)
    elif key == "focus":
        p["focus"] = [max(0, min(MAX_FOCUS, int(value)))]
    elif key == "focusManual":
        if value:
            p["focus"] = [int(focus_state(cam).get("focus", 400))]
        else:
            p.pop("focus", None)
    elif key == "minWidth":
        if int(value):
            p["min_width"] = [int(value)]
        else:
            p.pop("min_width", None)
        restart = True
    else:
        raise KeyError(key)
    write_profile(cam, p)
    if restart:
        restart_camera_service()
    return restart


def reset_setting(cam, key):
    set_setting(cam, key, _default(cam, key))


def reset_all(cam, keep_size=True):
    p = read_profile(cam)
    write_profile(cam, {k: v for k, v in p.items() if k == "min_width" and keep_size})


# ---- UI memory (which switches the user left on) ----
def _ui():
    """The file as a dictionary; a damaged one counts as empty."""
    try:
        with open(UI_FILE) as f:
            d = json.load(f)
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def ui_setting(key, default):
    return _ui().get(key, default)


def set_ui_setting(key, value):
    d = _ui()
    d[key] = value
    _write_atomic(UI_FILE, json.dumps(d))


# ---- presets ----
MAX_NAME = 60


def _name(name):
    """A preset name as it is shown: one line, single spaces. '' when it is empty or too long."""
    name = " ".join(str(name).split())
    return name if len(name) <= MAX_NAME else ""


def _slug(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", _name(name)).strip("._")[:60]


def _preset_path(cam, pid):
    """The file of a preset. The id comes from the command line: only what _slug makes is taken, so that an id can never
    point outside the preset folder."""
    if not pid or pid != _slug(pid):
        raise ValueError("not a preset id: %r" % pid)
    return os.path.join(PRESET_DIR, cam, pid + ".json")


def _load_preset(cam, pid):
    try:
        with open(_preset_path(cam, pid)) as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def _preset_profile(cam, pid):
    d = _load_preset(cam, pid)
    try:
        return {k: [float(x) for x in v] for k, v in d["profile"].items()}
    except (TypeError, KeyError, ValueError, AttributeError):
        return None


def matching_preset(cam):
    """Id of the preset whose settings equal the current ones (the size counts too), or ''."""
    cur = read_profile(cam)
    ids = [os.path.basename(p)[:-5] for p in sorted(glob.glob(os.path.join(PRESET_DIR, cam, "*.json")))]
    matches = [i for i in ids if _preset_profile(cam, i) == cur]
    last = ui_setting("lastPreset_" + cam, "")
    return last if last in matches else (matches[0] if matches else "")


def list_presets(cam):
    out = []
    for p in sorted(glob.glob(os.path.join(PRESET_DIR, cam, "*.json"))):
        pid = os.path.basename(p)[:-5]
        d = _load_preset(cam, pid)
        if d is not None:
            out.append({"id": pid, "name": str(d.get("name") or pid)})
    out.sort(key=lambda x: x["name"].lower())
    cur = matching_preset(cam)
    for o in out:
        o["current"] = o["id"] == cur
    return out


def save_preset(cam, name, overwrite=False):
    """Returns 'ok', 'invalid' (empty or unusable name) or 'exists'."""
    pid = _slug(name)
    if not pid:
        return "invalid"
    if os.path.exists(_preset_path(cam, pid)) and not overwrite:
        return "exists"
    _write_atomic(_preset_path(cam, pid), json.dumps({"name": _name(name), "profile": read_profile(cam)}, indent=1))
    set_ui_setting("lastPreset_" + cam, pid)
    return "ok"


def apply_preset(cam, pid):
    """Make the preset the current profile. Returns True when the picture size changed (the camera service restarts)."""
    try:
        prof = _preset_profile(cam, pid)
    except ValueError:
        prof = None
    if prof is None:
        return False
    old = read_profile(cam).get("min_width")
    write_profile(cam, prof)
    set_ui_setting("lastPreset_" + cam, pid)
    changed = prof.get("min_width") != old
    if changed:
        restart_camera_service()
    return changed


def rename_preset(cam, pid, new_name):
    nid = _slug(new_name)
    if not nid:
        return "invalid"
    if nid != pid and os.path.exists(_preset_path(cam, nid)):
        return "exists"
    d = _load_preset(cam, pid)
    if d is None:
        return "invalid"
    d["name"] = _name(new_name)
    _write_atomic(_preset_path(cam, nid), json.dumps(d, indent=1))
    if nid != pid:
        os.remove(_preset_path(cam, pid))
    return "ok"


def delete_preset(cam, pid):
    try:
        os.remove(_preset_path(cam, pid))
    except (OSError, ValueError):
        return
    d = _ui()
    if d.get("lastPreset_" + cam) == pid:               # do not keep pointing at a preset that is gone
        del d["lastPreset_" + cam]
        _write_atomic(UI_FILE, json.dumps(d))


def duplicate_preset(cam, pid, new_name):
    nid = _slug(new_name)
    if not nid:
        return "invalid"
    if os.path.exists(_preset_path(cam, nid)):
        return "exists"
    d = _load_preset(cam, pid)
    if d is None:
        return "invalid"
    d["name"] = _name(new_name)
    _write_atomic(_preset_path(cam, nid), json.dumps(d, indent=1))
    return "ok"


def describe(cam):
    """Everything the Cameras page needs in one JSON object."""
    return {"camera": cam, "settings": settings(cam), "controls": controls(cam), "presets": list_presets(cam),
            "focus": focus_state(cam), "sizes": [{"minWidth": w, "text": "%s  (%s)" % (s, fps)} for w, s, fps in SIZES[cam]],
            "advanced": bool(ui_setting("camAdvanced", False)),
            "node": "libcamera_input.__SB_.PCI0.LNK%d" % (0 if cam == "rear" else 1)}
