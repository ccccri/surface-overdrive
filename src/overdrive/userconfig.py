"""Where the per-user settings of Surface Control live (~/.config/surface-overdrive) and how they are written."""
import json
import os

CONFIG = os.environ.get("OVERDRIVE_CONFIG_DIR") or os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "surface-overdrive")


def write_atomic(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_json(path, data):
    write_atomic(path, json.dumps(data, indent=1))
