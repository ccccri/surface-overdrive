"""audio.json of the user: equaliser sets, microphone settings, presets."""
import os

from .. import userconfig


def path():
    return os.path.join(userconfig.CONFIG, "audio.json")


def load():
    """The file as a dictionary. A file that holds something else (damaged, or edited by hand) counts as empty: every reader
    then falls back to its defaults instead of failing, and the next change writes a good file again."""
    try:
        data = userconfig.load_json(path())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def section(data, key):
    """data[key] when it is a dictionary, else an empty one."""
    value = data.get(key) if isinstance(data, dict) else None
    return value if isinstance(value, dict) else {}


def number(value, default, low, high):
    """value as a number between low and high; default when it is not a number at all."""
    try:
        x = float(value)
    except (TypeError, ValueError):
        return float(default)
    if x != x:                                          # NaN
        return float(default)
    return float(max(low, min(high, x)))


def save(data):
    userconfig.save_json(path(), data)
