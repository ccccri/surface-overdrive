"""Microphone improvement: noise suppression, then a small equaliser and gain, running inside the built-in microphone itself.

The filters are a PipeWire filter graph loaded into the microphone device (see graph.py), so the list of recording devices keeps one
entry for the built-in microphone and every app that records from it gets the improved sound. The noise suppression is the
overdrive_denoise LADSPA plugin of this project (ladspa/overdrive_denoise.c, the rnnoise library).
"""
import os

from . import graph, pw, store

SOURCE = "alsa_input.pci-0000_00_1f.3.analog-stereo"
VERSION = "mic-1"
# PipeWire files of earlier versions, which made two extra microphones ("noise filter" and "enhanced")
OLD_FILES = ("20-mic-filter.conf", "30-mic-enhance.conf")
DEFAULTS = {"denoise": 100.0, "gain": 0.0, "lowcut": 80.0, "bass": 0.0, "presence": 0.0, "treble": 0.0}
RANGES = {"denoise": (0, 100), "gain": (-12, 24), "lowcut": (20, 400), "bass": (-12, 12), "presence": (-12, 12), "treble": (-12, 12)}
BUILTIN = {
    "Flat": dict(DEFAULTS),
    "Clear voice": {"denoise": 100.0, "gain": 3.0, "lowcut": 110.0, "bass": -2.0, "presence": 3.0, "treble": -1.0},
    "Warm": {"denoise": 100.0, "gain": 2.0, "lowcut": 70.0, "bass": 3.0, "presence": 1.0, "treble": -3.0},
}


def conf_dir():
    return os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "pipewire", "pipewire.conf.d")


def enabled():
    return bool(store.load().get("mic_on", False))


def settings():
    return _clean(store.section(store.load(), "mic"))


def controls(v):
    c = {}
    for ch in "LR":
        c.update({f"ns{ch}:Strength": v["denoise"] / 100.0, f"hp{ch}:Freq": v["lowcut"], f"bass{ch}:Gain": v["bass"],
                  f"pres{ch}:Gain": v["presence"], f"treb{ch}:Gain": v["treble"], f"gain{ch}:Mult": 10 ** (v["gain"] / 20.0)})
    return c


def graph_text(v):
    """The filter graph with these values in it: the same chain for each of the two microphone capsules."""
    c = controls(v)
    nodes = []
    links = []
    for ch in "LR":
        chain = [("ns", 'type = ladspa name = ns%s plugin = overdrive_denoise label = overdrive_denoise control = { "Strength" = %.3f }'
                  % (ch, c[f"ns{ch}:Strength"])),
                 ("hp", 'type = builtin name = hp%s label = bq_highpass control = { "Freq" = %.2f "Q" = 0.707 }' % (ch, c[f"hp{ch}:Freq"])),
                 ("bass", 'type = builtin name = bass%s label = bq_lowshelf control = { "Freq" = 200.0 "Q" = 0.707 "Gain" = %.3f }' % (ch, c[f"bass{ch}:Gain"])),
                 ("pres", 'type = builtin name = pres%s label = bq_peaking control = { "Freq" = 3000.0 "Q" = 1.0 "Gain" = %.3f }' % (ch, c[f"pres{ch}:Gain"])),
                 ("treb", 'type = builtin name = treb%s label = bq_highshelf control = { "Freq" = 8000.0 "Q" = 0.707 "Gain" = %.3f }' % (ch, c[f"treb{ch}:Gain"])),
                 ("gain", 'type = builtin name = gain%s label = linear control = { "Mult" = %.5f "Add" = 0.0 }' % (ch, c[f"gain{ch}:Mult"]))]
        nodes += ["{ %s }" % text for _, text in chain]
        outs = ["ns%s:Output" % ch] + ["%s%s:Out" % (name, ch) for name, _ in chain[1:]]
        ins = ["%s%s:In" % (name, ch) for name, _ in chain[1:]]
        links += ['{ output = "%s" input = "%s" }' % (o, i) for o, i in zip(outs, ins)]
    return '{ nodes = [ %s ] links = [ %s ] inputs = [ "nsL:Input" "nsR:Input" ] outputs = [ "gainL:Out" "gainR:Out" ] }' % (
        " ".join(nodes), " ".join(links))


def _clean(v):
    """Every setting as a number in its range; what is missing or not a number becomes the default."""
    if not isinstance(v, dict):
        v = {}
    return {k: store.number(v.get(k, DEFAULTS[k]), DEFAULTS[k], RANGES[k][0], RANGES[k][1]) for k in DEFAULTS}


def _store(key, value):
    d = store.load()
    d[key] = value
    store.save(d)


def apply():
    """Put the microphone device in the state the settings ask for. False while the device is not there."""
    if not enabled():
        return graph.clear(SOURCE)
    v = settings()
    return graph.apply(SOURCE, VERSION, lambda: graph_text(v), controls(v))


def set_all(values):
    _store("mic", _clean(values))
    return apply()


def set_one(key, value):
    if key not in DEFAULTS:
        raise KeyError(key)
    v = settings()
    v[key] = float(value)                               # a text that is no number is an error of the caller: say so
    return set_all(v)


def enable():
    _store("mic_on", True)
    return apply()


def disable():
    _store("mic_on", False)
    return apply()


def migrate():
    """Earlier versions improved the microphone with two PipeWire files in the home directory, which showed up as two more
    microphones. Remove them, keep the improvement on, and restart the sound system once so the extra devices go away."""
    found = False
    for f in OLD_FILES:
        try:
            os.remove(os.path.join(conf_dir(), f))
            found = True
        except OSError:
            pass
    if found:
        _store("mic_on", True)
        pw.run(["systemctl", "--user", "restart", "pipewire.service", "pipewire-pulse.service", "wireplumber.service"], timeout=40)
    return found


MAX_NAME = 60


def _user_presets(data):
    return store.section(store.section(data, "presets"), "input")


def presets():
    custom = _user_presets(store.load())
    return [{"name": n, "builtin": True} for n in BUILTIN] + [{"name": n, "builtin": False} for n in sorted(custom, key=str.lower)]


def preset_values(name):
    values = BUILTIN.get(name) or _user_presets(store.load()).get(name)
    return values if isinstance(values, dict) else None


def apply_preset(name):
    vals = preset_values(name)
    return bool(vals) and set_all(vals)


def save_preset(name):
    name = " ".join(str(name).split())
    if not name or len(name) > MAX_NAME or name.lower() in [b.lower() for b in BUILTIN]:
        return "invalid"
    d = store.load()
    presets = dict(store.section(d, "presets"))
    presets["input"] = dict(_user_presets(d), **{name: settings()})
    d["presets"] = presets
    store.save(d)
    return "ok"


def delete_preset(name):
    if name in BUILTIN:
        return
    d = store.load()
    if name in _user_presets(d):
        del d["presets"]["input"][name]
        store.save(d)


def describe():
    return {"available": enabled(), "running": enabled() and graph.loaded(SOURCE, VERSION), "values": settings(), "ranges": RANGES,
            "defaults": DEFAULTS, "presets": presets()}
