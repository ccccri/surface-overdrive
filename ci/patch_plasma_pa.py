#!/usr/bin/env python3
"""Take "Raise maximum volume" out of Plasma's sound controls (plasma-pa), in its source tree.

The image raises the loudness of the speakers in its own way, inside the sound device: the volume boost of "Sound and EQ", with a
limiter after it. Plasma's switch lets the volume go to 150% on top of that, which only adds distortion and wear to the small
speakers. Its switch goes away from the volume popup of the panel (the strip at its bottom holds only that switch and its warning)
and from "Configure Volume Controls" of the Sound page, and every place that reads the setting reads "off", so that a switch
turned on before cannot keep the 150% out of sight. The QML of plasma-pa is compiled into its plugins, so the change is made in
the source tree and the package is rebuilt (ci/build_plasma_pa.sh).

When a file has a layout this was not written for, nothing is changed and the build goes on with Fedora's package.

usage: patch_plasma_pa.py <source tree>
"""
import sys
from pathlib import Path

MARK = "Surface Overdrive:"

CHANGES = {
    "applet/main.qml": [
        ("""            id: footerToolbar

            visible: !micTestActive""",
         """            id: footerToolbar

            // Surface Overdrive: no "Raise maximum volume" (the image has its own volume boost), and this strip holds nothing else
            visible: false"""),
        ("""                    checked: config.raiseMaximumVolume
""", """                    checked: false
"""),
    ],
    "applet/MicrophoneTestView.qml": [
        ("to: config.raiseMaximumVolume ? PulseAudio.MaximalVolume : PulseAudio.NormalVolume",
         "to: PulseAudio.NormalVolume // Surface Overdrive: no raised maximum"),
    ],
    "src/kcm/ui/VolumeControlsConfig.qml": [
        ("""            QQC2.CheckBox {
                checked: config.raiseMaximumVolume
                text: i18n("Raise maximum volume")""",
         """            QQC2.CheckBox {
                // Surface Overdrive: no "Raise maximum volume" (the image has its own volume boost)
                visible: false
                checked: false
                text: i18n("Raise maximum volume")"""),
    ],
    "src/kcm/ui/VolumeSlider.qml": [
        ("to: config.raiseMaximumVolume ? PulseAudio.MaximalVolume /* 150 */ : PulseAudio.NormalVolume /* 100 */",
         "to: PulseAudio.NormalVolume // Surface Overdrive: no raised maximum"),
    ],
    "src/kcm/ui/main.qml": [
        ("to: config.raiseMaximumVolume ? PulseAudio.MaximalVolume : PulseAudio.NormalVolume",
         "to: PulseAudio.NormalVolume // Surface Overdrive: no raised maximum"),
    ],
    "src/kded/audioshortcutsservice.cpp": [
        ("const int maxVolume = PulseAudioQt::normalVolume() * (m_globalConfig->raiseMaximumVolume() ? 150 : 100) / 100.0;",
         "const int maxVolume = PulseAudioQt::normalVolume(); // Surface Overdrive: no raised maximum"),
        ("m_osdDBusInterface->volumeChanged(percent, m_globalConfig->raiseMaximumVolume() ? 150 : 100);",
         "m_osdDBusInterface->volumeChanged(percent, 100); // Surface Overdrive: no raised maximum"),
    ],
}


def patch_text(text, changes):
    """The changed text, or None when one of the changes does not fit (a counted replacement: each must be found)."""
    for old, new in changes:
        n = text.count(old)
        if n == 0:
            return None
        text = text.replace(old, new)
    return text


def main(argv):
    root = Path(argv[1])
    out = {}
    for rel, changes in CHANGES.items():
        path = root / rel
        if not path.is_file():
            print("WARNING: %s is missing: plasma-pa is left as Fedora has it" % rel)
            return 0
        text = path.read_text()
        if MARK in text:
            print("already patched", rel)
            continue
        new = patch_text(text, changes)
        if new is None:
            print("WARNING: the layout of %s changed: plasma-pa is left as Fedora has it" % rel)
            return 0
        out[path] = new
    for path, text in out.items():
        path.write_text(text)
        print("patched", path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
