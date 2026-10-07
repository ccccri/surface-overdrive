"""Microphone improvement: WebRTC noise suppression, then a small equaliser and gain stage whose controls are set live.

The two PipeWire config files ship in the image (/usr/share/overdrive/audio); "enable" copies them to the user's
~/.config/pipewire/pipewire.conf.d and restarts the sound server, so the chain is loaded by PipeWire itself (a module loaded from
outside would vanish with its loader).
"""
import os
import re
import shutil
import time

from . import pw, store

SHARE = "/usr/share/overdrive/audio"
FILES = ("20-mic-filter.conf", "30-mic-enhance.conf")
NODE = "mic_enhanced"
DEFAULTS = {"gain": 0.0, "lowcut": 80.0, "bass": 0.0, "presence": 0.0, "treble": 0.0}
RANGES = {"gain": (-12, 24), "lowcut": (20, 400), "bass": (-12, 12), "presence": (-12, 12), "treble": (-12, 12)}
BUILTIN = {
    "Flat": dict(DEFAULTS),
    "Clear voice": {"gain": 3.0, "lowcut": 110.0, "bass": -2.0, "presence": 3.0, "treble": -1.0},
    "Warm": {"gain": 2.0, "lowcut": 70.0, "bass": 3.0, "presence": 1.0, "treble": -3.0},
}


def conf_dir():
    return os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "pipewire", "pipewire.conf.d")


def installed():
    return os.path.exists(os.path.join(conf_dir(), FILES[1]))


def settings():
    out = dict(DEFAULTS)
    saved = store.load().get("mic", {})
    out.update({k: float(saved[k]) for k in DEFAULTS if k in saved})
    return out


def controls(v):
    return {"hp:Freq": v["lowcut"], "bass:Gain": v["bass"], "pres:Gain": v["presence"], "treb:Gain": v["treble"],
            "gain:Mult": 10 ** (v["gain"] / 20.0)}


def _clean(v):
    return {k: float(max(RANGES[k][0], min(RANGES[k][1], float(v.get(k, DEFAULTS[k]))))) for k in DEFAULTS}


def _store(v):
    d = store.load()
    d["mic"] = v
    store.save(d)


def set_all(values):
    v = _clean(values)
    _store(v)
    return pw.set_params(NODE, controls(v))


def set_one(key, value):
    if key not in DEFAULTS:
        raise KeyError(key)
    v = settings()
    v[key] = float(value)
    return set_all(v)


def _restart_sound():
    return pw.run(["systemctl", "--user", "restart", "pipewire.service", "pipewire-pulse.service", "wireplumber.service"], timeout=40)[0] == 0


def _make_default_source(name):
    """WirePlumber remembers the default source, so a new virtual one has to be made default explicitly."""
    for _ in range(15):
        nid = pw.node_id(name)
        if nid is not None:
            pw.run(["wpctl", "set-default", str(nid)])
            return True
        time.sleep(0.5)
    return False


def enable():
    os.makedirs(conf_dir(), exist_ok=True)
    for f in FILES:
        shutil.copyfile(os.path.join(SHARE, f), os.path.join(conf_dir(), f))
    ok = _restart_sound()
    if ok:
        _make_default_source(NODE)
        set_all(settings())            # the file starts neutral: put the saved values on top
    return ok


def disable():
    for f in FILES:
        try:
            os.remove(os.path.join(conf_dir(), f))
        except OSError:
            pass
    return _restart_sound()


def presets():
    custom = store.load().get("presets", {}).get("input", {})
    return [{"name": n, "builtin": True} for n in BUILTIN] + [{"name": n, "builtin": False} for n in sorted(custom, key=str.lower)]


def preset_values(name):
    return BUILTIN.get(name) or store.load().get("presets", {}).get("input", {}).get(name)


def apply_preset(name):
    vals = preset_values(name)
    return bool(vals) and set_all(vals)


def save_preset(name):
    name = name.strip()
    if not name or name in BUILTIN:
        return "invalid"
    d = store.load()
    d.setdefault("presets", {}).setdefault("input", {})[name] = settings()
    store.save(d)
    return "ok"


def delete_preset(name):
    if name in BUILTIN:
        return
    d = store.load()
    d.get("presets", {}).get("input", {}).pop(name, None)
    store.save(d)


def describe():
    return {"available": installed(), "running": pw.node_id(NODE) is not None, "values": settings(), "ranges": RANGES,
            "presets": presets()}
