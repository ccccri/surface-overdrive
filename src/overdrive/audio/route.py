"""User service: keeps the equaliser of the sound output in step with the headphone jack.

The speakers and the headphone jack are two ports of one sound card. This applies the saved equaliser set of the port in use at
login and every time the jack is plugged or unplugged (it watches the card with `pactl subscribe`).
"""
import subprocess
import sys
import time

from . import eq, pw


def apply_now(last):
    out = pw.active_output()
    state = eq.load()
    key = (out, state["sync"], repr(eq.effective(state, out)))
    if key != last:
        if eq.apply(eq.effective(state, out)):
            print("applied the %s settings%s" % (out, " (synced)" if state["sync"] else ""), flush=True)
        else:
            return None          # the chain is not up yet: try again at the next event
    return key


def main():
    last = None
    while True:
        try:
            last = apply_now(last)
            p = subprocess.Popen(["pactl", "subscribe"], stdout=subprocess.PIPE, text=True)
            for line in p.stdout:
                # card and sink changes cover plugging the jack; wait a moment for the port to settle, then look
                if "'change' on sink" in line or "'change' on card" in line or "'new' on sink" in line:
                    time.sleep(0.4)
                    last = apply_now(last)
            p.wait()
        except OSError as e:
            print("waiting for the sound server:", e, flush=True)
        time.sleep(3)


if __name__ == "__main__":
    sys.exit(main())
