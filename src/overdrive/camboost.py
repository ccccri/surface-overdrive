"""overdrive-camera-boost: the "performance" power profile while a built-in camera streams.

On battery the system runs the "balanced" profile, which keeps the processor in power saving (energy preference
balance_power), and the camera pipeline does part of its work on the processor (the temporal denoiser): the front
camera at 2560x1920 gave 24.6 frames a second there and 28.7 with "performance" (measured 2026-10-27), the filter took
twice as long. While a camera node of PipeWire runs, this service holds the "performance" profile through
power-profiles-daemon's HoldProfile (tuned-ppd on Fedora), the way games do; the hold ends when the camera stops (or
when this service ends: the daemon drops the holds of a connection that goes away). The profile the user chose comes
back by itself.
"""
import json
import subprocess
import sys

BUS_NAME = "net.hadess.PowerProfiles"
OBJECT = "/net/hadess/PowerProfiles"
APP_ID = "org.surfaceoverdrive.CameraBoost"


class CameraWatch:
    """Which built-in camera nodes (libcamera) run, from the stream of pw-dump --monitor: arrays of objects, each one
    complete the first time and then only what changed, with "info": null when the object goes away."""

    def __init__(self):
        self.cameras = set()        # ids of camera nodes
        self.running = set()        # ids of camera nodes that stream
        self._decoder = json.JSONDecoder()
        self._buffer = ""

    def feed(self, text):
        """Add output of pw-dump (a line or more); returns True when a camera streams. The text is decoded only when a
        line closes a top-level array ("]" alone, as pw-dump writes it): the first dump is large."""
        self._buffer += text
        if not any(line.rstrip() == "]" for line in text.splitlines()):
            return bool(self.running)
        while True:
            start = self._buffer.find("[")
            if start < 0:
                self._buffer = ""
                break
            try:
                objs, end = self._decoder.raw_decode(self._buffer, start)
            except ValueError:
                self._buffer = self._buffer[start:]
                break
            self._buffer = self._buffer[end:]
            for obj in objs if isinstance(objs, list) else []:
                self._update(obj)
        return bool(self.running)

    def _update(self, obj):
        oid = obj.get("id")
        info = obj.get("info")
        if info is None:
            self.cameras.discard(oid)
            self.running.discard(oid)
            return
        if not str(obj.get("type", "")).endswith("Node"):
            return
        name = (info.get("props") or {}).get("node.name")
        if name is not None:
            if str(name).startswith("libcamera_input"):
                self.cameras.add(oid)
            else:
                self.cameras.discard(oid)
        if oid in self.cameras and "state" in info:
            if info["state"] == "running":
                self.running.add(oid)
            else:
                self.running.discard(oid)


def main():
    from gi.repository import Gio, GLib

    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    state = {"cookie": None}

    def hold():
        try:
            res = bus.call_sync(BUS_NAME, OBJECT, BUS_NAME, "HoldProfile",
                                GLib.Variant("(sss)", ("performance", "A camera is in use", APP_ID)),
                                GLib.VariantType("(u)"), Gio.DBusCallFlags.NONE, 5000, None)
            state["cookie"] = res.unpack()[0]
            print("camera in use: performance profile held", flush=True)
        except GLib.Error as exc:
            print("cannot hold the performance profile: %s" % exc.message, flush=True)
            state["cookie"] = 0          # do not ask again until the camera stops

    def release():
        cookie, state["cookie"] = state["cookie"], None
        if not cookie:
            return
        try:
            bus.call_sync(BUS_NAME, OBJECT, BUS_NAME, "ReleaseProfile", GLib.Variant("(u)", (cookie,)),
                          None, Gio.DBusCallFlags.NONE, 5000, None)
            print("camera stopped: profile released", flush=True)
        except GLib.Error as exc:
            print("cannot release the profile: %s" % exc.message, flush=True)

    def on_released(_conn, _sender, _path, _iface, _signal, params):
        # the daemon dropped the hold (the user picked another profile): do not hold again until the camera stops
        if state["cookie"] and params.unpack()[0] == state["cookie"]:
            state["cookie"] = 0

    bus.signal_subscribe(BUS_NAME, BUS_NAME, "ProfileReleased", OBJECT, None, Gio.DBusSignalFlags.NONE, on_released)

    watch = CameraWatch()
    proc = subprocess.Popen(["pw-dump", "--monitor", "--no-colors"], stdout=subprocess.PIPE, text=True, bufsize=1)

    def on_output(_source, _condition):
        line = proc.stdout.readline()
        if not line:
            loop.quit()                  # PipeWire went away: systemd starts the service again
            return False
        running = watch.feed(line)
        if running and state["cookie"] is None:
            hold()
        elif not running and state["cookie"] is not None:
            release()
        return True

    loop = GLib.MainLoop()
    GLib.io_add_watch(proc.stdout, GLib.PRIORITY_DEFAULT, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, on_output)
    try:
        loop.run()
    finally:
        release()
        proc.terminate()
    return 1                             # ended only when PipeWire went away


if __name__ == "__main__":
    sys.exit(main())
