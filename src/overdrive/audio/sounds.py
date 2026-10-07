"""Test sounds for the speakers and the microphone, played through PipeWire."""
import math
import os
import signal
import struct
import subprocess
import time
import wave

SOUNDS = "/usr/share/sounds/freedesktop/stereo/"
# (file, channel map): the voices of the desktop sound theme announce the channel ("Front left", "Front right"), the chime plays on both
TEST_SOUNDS = {"left": ("audio-channel-front-left.oga", "FL"), "right": ("audio-channel-front-right.oga", "FR"), "both": ("stereo", None)}


def sweep_file():
    """A slow logarithmic sweep from 40 Hz to 16 kHz (8 s, faded in and out, a little below full level), made once into the runtime folder."""
    d = runtime_dir()
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "sweep-40-16k.wav")
    if os.path.exists(path):
        return path
    rate, secs = 44100, 8.0
    w = wave.open(path, "wb")
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(rate)
    phase = 0.0
    buf = bytearray()
    k = math.log(16000 / 40.0)
    for n in range(int(rate * secs)):
        t = n / rate
        phase += 2 * math.pi * 40.0 * math.exp(k * t / secs) / rate
        v = 0.3 * min(1.0, t * 8, (secs - t) * 8) * math.sin(phase)
        s = int(v * 32767)
        buf += struct.pack("<hh", s, s)
    w.writeframes(bytes(buf))
    w.close()
    return path


def stereo_file():
    """A short stereo piece made once into the runtime folder: a soft pad with slightly detuned voices (wide), a centred bass, and a bell melody whose echoes ping-pong between the speakers."""
    d = runtime_dir()
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "stereo-demo-3.wav")
    if os.path.exists(path):
        return path
    rate, secs = 44100, 3.4
    n = int(rate * secs)
    L = [0.0] * n
    R = [0.0] * n
    tau = 2 * math.pi

    def voice(buf, freq, start, dur, amp, kind):
        a0 = int(start * rate)
        for i in range(min(int(dur * rate), n - a0)):
            t = i / rate
            if kind == "pad":
                env = min(1.0, t / 0.6) * min(1.0, (dur - t) / 0.8)
                v = math.sin(tau * freq * t) + 0.4 * math.sin(tau * 2 * freq * t)
            elif kind == "bass":
                env = min(1.0, t * 60) * math.exp(-1.6 * t / dur)
                v = math.sin(tau * freq * t)
            else:                                                  # bell
                env = min(1.0, t * 300) * math.exp(-4.0 * t / dur)
                v = math.sin(tau * freq * t) + 0.5 * math.sin(tau * 2.01 * freq * t) + 0.2 * math.sin(tau * 3.99 * freq * t)
            buf[a0 + i] += amp * env * v

    chords = [([261.6, 329.6, 392.0], 65.4), ([220.0, 261.6, 329.6], 55.0), ([174.6, 220.0, 261.6], 43.65), ([196.0, 246.9, 293.7], 49.0)]
    for k, (notes, bass) in enumerate(chords[:1]):
        t0 = k * 2.25
        for j, f in enumerate(notes):                              # detuned copies: one a little flat on the left, a little sharp on the right
            voice(L, f * 0.997, t0, 3.2, 0.07, "pad")
            voice(R, f * 1.003, t0, 3.2, 0.07, "pad")
        voice(L, bass, t0, 2.2, 0.12, "bass")
        voice(R, bass, t0, 2.2, 0.12, "bass")
    tune = [(0, 784.0), (0.5, 659.3), (1.0, 523.3), (1.5, 659.3)]
    dry = [0.0] * n
    for t0, f in tune:
        voice(dry, f, t0 + 0.1, 0.9, 0.22, "bell")
    delay = int(0.3 * rate)
    for i in range(n):                                              # dry on the left, then echoes right, left, right, each quieter
        L[i] += dry[i]
        for k in range(1, 5):
            if i >= k * delay:
                (R if k % 2 else L)[i] += dry[i - k * delay] * 0.55 ** k
    w = wave.open(path, "wb")
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(rate)
    peak = max(max(map(abs, L)), max(map(abs, R)), 1e-9)
    g = 28000 / max(peak, 1.0)
    w.writeframes(b"".join(struct.pack("<hh", int(L[i] * g), int(R[i] * g)) for i in range(n)))
    w.close()
    return path


def sound_for(kind):
    """(path, channel map or None) of the short sound for the speaker test."""
    if kind == "sweep":
        return sweep_file(), None
    if kind == "both":
        return stereo_file(), None
    name, cmap = TEST_SOUNDS[kind]
    path = SOUNDS + name
    if not os.path.exists(path):
        raise OSError("the desktop sound " + name + " is not installed")
    return path, cmap


def runtime_dir():
    d = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "surface-control")
    os.makedirs(d, exist_ok=True)
    return d


PID_FILE = "surface-control-play.pid"


def play(kind):
    """Play a test sound and wait for it to end. kind: left, right, both, sweep. Returns 0 on success."""
    path, cmap = sound_for(kind)
    cmd = ["pw-play"] + (["--channel-map", cmap] if cmap else []) + [path]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    with open(os.path.join(runtime_dir(), PID_FILE), "w") as f:
        f.write(str(p.pid))
    return p.wait()


def record_and_play(seconds=5):
    """Record the default microphone for a few seconds, then play it back: the way to hear what the microphone settings do."""
    path = os.path.join(runtime_dir(), "mic-test.wav")
    rec = subprocess.Popen(["pw-record", "--rate", "48000", "--channels", "1", path], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, start_new_session=True)
    with open(os.path.join(runtime_dir(), PID_FILE), "w") as f:
        f.write(str(rec.pid))
    time.sleep(seconds)
    rec.send_signal(signal.SIGINT)
    rec.wait(timeout=5)
    return subprocess.run(["pw-play", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode


def stop():
    """Stop a test sound or recording that is running."""
    try:
        pid = int(open(os.path.join(runtime_dir(), PID_FILE)).read())
        os.kill(pid, signal.SIGTERM)
    except (OSError, ValueError):
        pass
