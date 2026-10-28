"""User service: puts the sound filters into the built-in devices and keeps them in step with the headphone jack.

The speakers and the headphone jack are two ports of one sound card. This loads the boost and equaliser into the output and the
microphone improvement into the input at login and whenever the sound server makes those devices again, and applies the saved
equaliser set of the port in use every time the jack is plugged or unplugged (it watches the card with `pactl subscribe`).

The sound server reports a "change" on the output many times a second while something plays (state, latency, volume). Events
are therefore gathered for a moment and handled once, and only a new device (made again: its filters are gone) costs a full
look at the graph (pw-dump); a change costs one `pactl list sinks` to read the port in use.
"""
import select
import subprocess
import sys
import time

from . import mic, eq, pw

SETTLE = 0.4          # seconds: the port settles after a plug, and a burst of events becomes one look


def serials():
    found = pw.node_serials({eq.SINK, mic.SOURCE})
    return (found.get(eq.SINK), found.get(mic.SOURCE))


def apply_now(last, devices):
    out = pw.active_output()
    state = eq.load()
    # the serials of the devices are part of the key: a device made again (sound server restart, profile change) has lost its filters
    key = (out, state["sync"], repr(eq.effective(state, out)), state["swap"][out]) + devices
    if key != last:
        mic.apply()
        if eq.apply_state(state, out):
            print("applied the %s settings%s" % (out, " (synced)" if state["sync"] else ""), flush=True)
        else:
            return None          # the chain is not up yet: try again at the next event
    return key


def relevant(line):
    """(matters, a device was made): card and sink changes cover plugging the jack and choosing a port."""
    # "on sink #" and not "on sink-input #": the streams of the programs change all the time while they play
    made = "'new' on sink #" in line or "'new' on source #" in line
    return made or "'change' on sink #" in line or "'change' on card #" in line, made


def main():
    last = None
    try:
        if mic.migrate():
            print("removed the separate microphone devices of earlier versions", flush=True)
    except OSError as e:
        print("could not remove the old microphone files:", e, flush=True)
    while True:
        try:
            devices = serials()
            last = apply_now(last, devices)
            p = subprocess.Popen(["pactl", "subscribe"], stdout=subprocess.PIPE, text=True, bufsize=1)
            while True:
                line = p.stdout.readline()
                if not line:
                    break
                matters, made = relevant(line)
                if not matters:
                    continue
                # gather the rest of the burst
                end = time.monotonic() + SETTLE
                while (left := end - time.monotonic()) > 0 and select.select([p.stdout], [], [], left)[0]:
                    more = p.stdout.readline()
                    if not more:
                        break
                    made = relevant(more)[1] or made
                if made or last is None:
                    devices = serials()
                last = apply_now(last, devices)
            p.wait()
        except OSError as e:
            print("waiting for the sound server:", e, flush=True)
        time.sleep(3)


if __name__ == "__main__":
    sys.exit(main())
