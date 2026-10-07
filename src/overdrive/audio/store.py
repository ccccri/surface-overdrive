"""audio.json of the user: equaliser sets, microphone settings, presets."""
import os

from .. import userconfig


def path():
    return os.path.join(userconfig.CONFIG, "audio.json")


def load():
    return userconfig.load_json(path())


def save(data):
    userconfig.save_json(path(), data)
