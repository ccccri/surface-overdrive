"""Small helpers around the PipeWire command line tools: filter chain controls of running nodes, the default devices."""
import json
import re
import subprocess


def run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout + r.stderr
    except (OSError, subprocess.SubprocessError) as e:
        return 127, str(e)


# A long-running caller (overdrivectl audio serve, fed by a slider being dragged) keeps what it learnt about the nodes here
# instead of reading the whole graph for every value; None: no memory, every call looks again.
_known = None


def remember_nodes():
    global _known
    _known = {}


def forget_nodes():
    if _known is not None:
        _known.clear()


def node_id(name):
    """Id of the PipeWire node with this node.name, or None."""
    if _known is not None:
        found = node_serial(name)
        return found[0] if found else None
    rc, out = run(["pw-dump"], timeout=10)
    try:
        for o in json.loads(out):
            if o.get("type", "").endswith("Node") and o.get("info", {}).get("props", {}).get("node.name") == name:
                return o["id"]
    except ValueError:
        pass
    return None


def node_serial(name):
    """(id, serial) of the node with this node.name, or None. The serial is new every time the node is made again."""
    if _known is not None and name in _known:
        return _known[name]
    found = _node_serial(name)
    if _known is not None and found is not None:
        _known[name] = found
    return found


def _node_serial(name):
    rc, out = run(["pw-dump"], timeout=10)
    try:
        for o in json.loads(out):
            props = o.get("info", {}).get("props", {}) if o.get("type", "").endswith("Node") else {}
            if props.get("node.name") == name:
                return o["id"], str(props.get("object.serial", o["id"]))
    except ValueError:
        pass
    return None


def node_serials(names):
    """{name: (id, serial)} of the nodes with these node.name values, from one pw-dump (a missing node is left out)."""
    rc, out = run(["pw-dump"], timeout=10)
    found = {}
    try:
        for o in json.loads(out):
            props = o.get("info", {}).get("props", {}) if o.get("type", "").endswith("Node") else {}
            if props.get("node.name") in names:
                found[props["node.name"]] = (o["id"], str(props.get("object.serial", o["id"])))
    except ValueError:
        pass
    return found


def _quote(value):
    return json.dumps(value) if isinstance(value, str) else "%g" % value


def set_params(name, params):
    """Change filter chain controls of a running node, for example {"gainL:Mult": 1.5}. True when PipeWire took them."""
    nid = node_id(name)
    if nid is None:
        return False
    items = " ".join('"%s" %s' % (k, _quote(v)) for k, v in params.items())
    if run(["pw-cli", "set-param", str(nid), "Props", "{ params = [ %s ] }" % items])[0] == 0:
        return True
    if _known:                                          # what was remembered may be out of date: look again once
        forget_nodes()
        nid = node_id(name)
        return nid is not None and run(["pw-cli", "set-param", str(nid), "Props", "{ params = [ %s ] }" % items])[0] == 0
    return False


def get_params(name):
    """The controls a running filter chain node reports now, as {"node:Control": value}."""
    nid = node_id(name)
    if nid is None:
        return {}
    rc, out = run(["pw-dump", str(nid)])
    try:
        for p in json.loads(out)[0]["info"]["params"]["Props"]:
            if "params" in p and any(":" in str(x) for x in p["params"][::2]):
                return dict(zip(p["params"][::2], p["params"][1::2]))
    except (ValueError, KeyError, IndexError):
        pass
    return {}


def default_volume(target):
    """(volume 0..1.5, muted) of @DEFAULT_AUDIO_SINK@ or @DEFAULT_AUDIO_SOURCE@."""
    rc, out = run(["wpctl", "get-volume", target])
    m = re.search(r"Volume:\s*([0-9.]+)", out)
    return (float(m.group(1)) if m else 0.0), "MUTED" in out


def active_output():
    """'headphones' while the jack is in use, else 'speaker' (the active port of the sound card)."""
    rc, out = run(["pactl", "list", "sinks"], timeout=6)
    m = re.search(r"Name: alsa_output[^\n]*\n(?:.*\n)*?\s*Active Port: ([^\n]+)", out)
    return "headphones" if m and "headphone" in m.group(1).lower() else "speaker"
