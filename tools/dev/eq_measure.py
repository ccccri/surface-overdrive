#!/usr/bin/env python3
"""Measure the equalizer through the air: the tablet plays a row of tones through its speakers and records them with its own
microphone, once with a reference set and once with a test set; the difference at each tone is what the equalizer did (the
speakers and the microphone are the same both times, so they cancel out). Development tool, needs numpy (build/calib-venv).

usage: eq_measure.py tones OUT.wav                     write the test signal
       eq_measure.py compare REF.wav TEST.wav REF_SET.json TEST_SET.json
                                                       per tone: measured change, the change the sets should make, the error
"""
import json
import math
import os
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from overdrive.audio import eq  # noqa: E402

RATE = 48000
FREQS = [round(80 * (14000 / 80) ** (i / 27)) for i in range(28)]      # 80 Hz to 14 kHz, about a third of an octave apart
TONE = 0.30                                                            # seconds each
LEVEL = 0.2                                                            # -14 dBFS: room for +9 dB without the limiter


def tones(path):
    t = np.arange(int(TONE * RATE)) / RATE
    fade = np.minimum(1, np.minimum(t, TONE - t) / 0.02)
    sig = np.concatenate([np.zeros(int(0.3 * RATE))] + [LEVEL * fade * np.sin(2 * math.pi * f * t) for f in FREQS]
                         + [np.zeros(int(0.3 * RATE))])
    pcm = (np.clip(sig, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(np.repeat(pcm, 2).tobytes())


def read(path):
    with wave.open(path) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float).reshape(-1, w.getnchannels())
        return x.mean(axis=1), w.getframerate()


def levels(path):
    """dB of each tone in a recording: the strongest bin within 3% of its frequency, over the whole recording."""
    x, rate = read(path)
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    freq = np.fft.rfftfreq(len(x), 1 / rate)
    out = []
    for f in FREQS:
        band = (freq > f * 0.97) & (freq < f * 1.03)
        out.append(20 * math.log10(spec[band].max() + 1e-9))
    floor = 20 * math.log10(np.median(spec[(freq > 60) & (freq < 16000)]) + 1e-9)
    return out, floor


def response(s):
    pre = s["preamp"]
    return [pre + eq.magnitude_db(s["bands"], f) for f in FREQS]


def compare(ref_wav, test_wav, ref_set, test_set):
    ref, floor_r = levels(ref_wav)
    test, floor_t = levels(test_wav)
    want = [b - a for a, b in zip(response(json.load(open(ref_set))), response(json.load(open(test_set))))]
    print("%7s %9s %9s %7s %8s" % ("Hz", "measured", "expected", "error", "over noise"))
    errs = []
    for f, r, t, w in zip(FREQS, ref, test, want):
        got = t - r
        snr = r - floor_r
        ok = snr > 20
        if ok:
            errs.append(got - w)
        print("%7d %+8.1f %+8.1f %+7.1f %7.0f dB%s" % (f, got, w, got - w, snr, "" if ok else "  (too weak to count)"))
    if errs:
        e = np.array(errs)
        print("\n%d tones counted: mean error %+.1f dB, largest %.1f dB" % (len(e), e.mean(), np.abs(e).max()))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "tones":
        tones(sys.argv[2])
    elif len(sys.argv) == 6 and sys.argv[1] == "compare":
        compare(*sys.argv[2:])
    else:
        print(__doc__)
        sys.exit(2)
