"""User service: puts the sound filters into the built-in devices and keeps them in step with the headphone jack.

The speakers and the headphone jack are two ports of one sound card. This loads the boost and equaliser into the output and the
microphone improvement into the input at login and whenever the sound server makes those devices again, and applies the saved
equaliser set of the port in use every time the jack is plugged or unplugged (it watches the card with `pactl subscribe`).
"""
import subprocess
import sys
import time

from . import mic, eq, pw


def apply_now(last):
    out = pw.active_output()
    state = eq.load()
    # the serial of the device is part of the key: a device made again (sound server restart, profile change) has lost its filters
    key = (out, state["sync"], repr(eq.effective(state, out)), state["swap"][out], pw.node_serial(eq.SINK), pw.node_serial(mic.SOURCE))
    if key != last:
        mic.apply()
        if eq.apply_state(state, out):
            print("applied the %s settings%s" % (out, " (synced)" if state["sync"] else ""), flush=True)
        else:
            return None          # the chain is not up yet: try again at the next event
    return key


def main():
    last = None
    try:
        if mic.migrate():
            print("removed the separate microphone devices of earlier versions", flush=True)
    except OSError as e:
        print("could not remove the old microphone files:", e, flush=True)
    while True:
        try:
            last = apply_now(last)
            p = subprocess.Popen(["pactl", "subscribe"], stdout=subprocess.PIPE, text=True)
            for line in p.stdout:
                # card and sink changes cover plugging the jack; wait a moment for the port to settle, then look
                if "'change' on sink" in line or "'change' on card" in line or "'new' on sink" in line or "'new' on source" in line:
                    time.sleep(0.4)
                    last = apply_now(last)
            p.wait()
        except OSError as e:
            print("waiting for the sound server:", e, flush=True)
        time.sleep(3)


if __name__ == "__main__":
    sys.exit(main())
