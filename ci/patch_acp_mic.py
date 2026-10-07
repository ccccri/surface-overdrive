#!/usr/bin/env python3
"""Limit the gain of the internal microphone of the Surface Go in PipeWire's ALSA mixer path.

With the stock path the capture chain sits at +60 dB at 100% (ALSA Capture +30 dB and Internal Mic Boost +30 dB): an empty room reads -6.8 dBFS with
peaks at 0 dBFS. This changes the path file so that
  - Capture is limited to step 103 of 127, which is +18 dB, and
  - Internal Mic Boost is held at 0 dB instead of following the volume,
which keeps normal speech at 40 cm clear of clipping (measured on this tablet). The speakers and headphones are left to PipeWire.

The file belongs to Fedora's pipewire package, so it is edited in the image build and the build fails when its layout changes.

usage: patch_acp_mic.py [path]
"""
import re
import sys
from pathlib import Path

DEFAULT = "/usr/share/alsa-card-profile/mixer/paths/analog-input-internal-mic.conf"
MARK = "; Surface Overdrive:"


def patch(text):
    if MARK in text:
        return text                                   # already done
    capture = re.compile(r"(\[Element Capture\]\n(?:(?!\[).*\n)*?)(?=\n?\[|\Z)")
    m = capture.search(text)
    if not m or "volume = merge" not in m.group(1):
        raise SystemExit("[Element Capture] with 'volume = merge' not found: the layout of the path file changed")
    block = m.group(1)
    text = text.replace(block, block.rstrip("\n") + "\n" + MARK + " 103 of 127 is +18 dB\nvolume-limit = 103\n", 1)

    boost = re.compile(r"(\[Element Internal Mic Boost\]\n(?:(?!\[).*\n)*?)(?=\n?\[|\Z)")
    m = boost.search(text)
    if not m or "volume = merge" not in m.group(1):
        raise SystemExit("[Element Internal Mic Boost] with 'volume = merge' not found: the layout of the path file changed")
    block = m.group(1)
    new = block.replace("volume = merge", MARK + " the boost stays at 0 dB\nvolume = zero", 1)
    return text.replace(block, new, 1)


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
    original = path.read_text()
    patched = patch(original)
    if patched != original:
        path.write_text(patched)
        print("patched", path)
    else:
        print("already patched", path)


if __name__ == "__main__":
    main()
