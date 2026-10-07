"""overdrive-nfcd: always-on NFC tag reader for the kernel NFC subsystem (no neard).

It runs as root and owns the reader: it polls for tags, reads the NDEF data of Type 2 tags, releases the tag in the kernel after
every read and re-arms polling at once. Results are broadcast as JSON lines on a unix socket that the desktop notifier reads.

neard is not used because it crashes when a tag disappears mid-read and, under fast tag swapping, leaves the kernel with an
"active target" so that polling silently stops (nci_start_poll: there is an active target).
"""
import errno
import json
import os
import socket
import subprocess
import sys
import threading
import time

from .netlink import Adapter, NfcNetlink, proto_label
from .tag import read_tag

SOCKET_PATH = os.environ.get("OVERDRIVE_NFC_SOCK", "/run/overdrive-nfc/events.sock")
SOCKET_GROUP = os.environ.get("OVERDRIVE_NFC_GROUP", "wheel")
ABSENCE_S = 1.0          # the same tag not seen for this long counts as removed: notify again
RESTING_REPOLL_S = 0.3   # pause between polls while the same tag keeps resting on the reader
REARM_S = 10.0           # restart polling at least this often (resume from suspend, adapter reset)
# Power saver profile: the reader is on for a short window, then off for a few seconds (about 8 times fewer radio pulses; a tag can
# take up to ~4 s to be noticed). Any other profile polls continuously.
SAVER_WINDOW_S = 0.6
SAVER_SLEEP_S = 3.4


def log(message):
    print(message, flush=True)


class EventServer:
    """Unix socket that broadcasts one JSON line per tag to every connected notifier."""

    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path):
            os.unlink(path)
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(path)
        try:
            import grp
            os.chown(path, 0, grp.getgrnam(SOCKET_GROUP).gr_gid)
        except (KeyError, ImportError):
            pass
        os.chmod(path, 0o660)
        self.server.listen(4)
        self.clients = []
        self.lock = threading.Lock()
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while True:
            client, _ = self.server.accept()
            client.settimeout(1.0)
            with self.lock:
                self.clients.append(client)
            log("notifier connected (%d)" % len(self.clients))

    def publish(self, event):
        line = (json.dumps(event) + "\n").encode()
        with self.lock:
            for client in list(self.clients):
                try:
                    client.sendall(line)
                except OSError:
                    self.clients.remove(client)
                    client.close()


class PowerProfile:
    """True while the desktop power profile is "power-saver" (power-profiles-daemon or tuned-ppd). Cached for one second."""

    def __init__(self):
        self._at = 0.0
        self._saver = False

    def saver(self):
        now = time.monotonic()
        if now - self._at > 1.0:
            self._at = now
            try:
                out = subprocess.run(
                    ["busctl", "--system", "get-property", "net.hadess.PowerProfiles", "/net/hadess/PowerProfiles",
                     "net.hadess.PowerProfiles", "ActiveProfile"], capture_output=True, text=True, timeout=3).stdout
                self._saver = "power-saver" in out
            except (OSError, subprocess.SubprocessError):
                self._saver = False
        return self._saver


def wait_for_adapter(index=0):
    while not os.path.isdir("/sys/class/nfc/nfc%d" % index):
        time.sleep(2)


def uid_text(raw):
    return ":".join("%02x" % b for b in raw)


def run():
    wait_for_adapter()
    adapter = Adapter(NfcNetlink(log))
    server = EventServer(SOCKET_PATH)
    profile = PowerProfile()
    last_uid, last_seen = None, 0.0
    errors = 0
    log("overdrive-nfcd running")

    err = adapter.up()
    if err not in (0, errno.EALREADY):
        log("dev_up: %s" % errno.errorcode.get(err, err))

    polling, poll_started = False, 0.0
    while True:
        # (Re)start polling when it is not running, and re-arm it every REARM_S as a safety net. EBUSY then only means "already polling".
        if not polling or time.monotonic() - poll_started > REARM_S:
            err = adapter.start_poll()
            if err == errno.EBUSY and not polling:
                adapter.release_stale_targets()       # an old active target blocks polling
                err = adapter.start_poll()
            if err not in (0, errno.EBUSY):
                errors += 1
                log("start_poll: %s" % errno.errorcode.get(err, err))
                if errors >= 5:                       # power-cycle the adapter as a last resort
                    adapter.down()
                    adapter.up()
                    errors = 0
                polling = False
                time.sleep(1)
                continue
            errors = 0
            polling, poll_started = True, time.monotonic()

        saver = profile.saver()
        if not adapter.nl.wait_targets(SAVER_WINDOW_S if saver else 2.0):
            if saver:                                 # window over and no tag: switch the reader off for a while
                adapter.stop_poll()
                polling = False
                end = time.monotonic() + SAVER_SLEEP_S
                while time.monotonic() < end and profile.saver():
                    time.sleep(0.25)
            continue

        polling = False                               # the kernel stops polling once it reports targets
        started = time.monotonic()
        targets = adapter.targets()
        if not targets:
            continue
        target = targets[0]
        uid = uid_text(target["uid"])
        now = time.monotonic()
        repeat = bool(uid) and uid == last_uid and now - last_seen < ABSENCE_S
        last_uid, last_seen = uid, now

        if repeat:                                    # the same tag is still resting: no read, no event
            time.sleep(RESTING_REPOLL_S)              # it was never activated, so polling can simply restart
            continue

        records = read_tag(adapter, target, log)
        read_ms = (time.monotonic() - started) * 1000
        event = {"time": time.time(), "uid": uid, "type": proto_label(target["protos"]), "records": records,
                 "read_ms": round(read_ms)}
        log("tag %s %s %s (%.0f ms)" % (uid, event["type"], json.dumps(records), read_ms))
        server.publish(event)
        last_seen = time.monotonic()


def main():
    try:
        run()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
