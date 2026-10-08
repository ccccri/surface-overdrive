"""Filters that run inside a sound device.

PipeWire can load a filter graph into the device node itself (the audioconvert.filter-graph property). Used here for the speaker
boost and equaliser and for the microphone improvement, so the list of devices keeps one entry per real device: no extra
"boosted" or "enhanced" device to choose, and nothing to choose wrongly.

PipeWire does not tell which graph a node runs, so this remembers it: a small file in the runtime folder holds the serial of the node
the graph was loaded into (a node made again after a restart or a profile change has a new serial and no graph).
"""
import os

from . import pw

PROP = "audioconvert.filter-graph.0"


def _marker(node_name):
    d = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "surface-overdrive")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "graph-" + node_name.replace("/", "_"))


def _read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""


def loaded(node_name, version):
    """True when the running node carries the graph of this version."""
    found = pw.node_serial(node_name)
    return found is not None and _read(_marker(node_name)) == "%s %s" % (found[1], version)


def apply(node_name, version, text, controls):
    """Make the node run the graph with these control values. text() gives the whole graph with the values in it and is only used
    when the node does not carry the graph yet; otherwise just the controls are set, which is inaudible. False without the node."""
    found = pw.node_serial(node_name)
    if found is None:
        return False
    want = "%s %s" % (found[1], version)
    if _read(_marker(node_name)) == want:
        return pw.set_params(node_name, controls)
    if not pw.set_params(node_name, {PROP: text()}):
        return False
    with open(_marker(node_name), "w") as f:
        f.write(want)
    return True


def clear(node_name):
    """Take the graph out of the node. True when there is nothing left to remove."""
    try:
        os.remove(_marker(node_name))
    except OSError:
        return True                                     # none was loaded into this node
    return pw.node_serial(node_name) is None or pw.set_params(node_name, {PROP: ""})
