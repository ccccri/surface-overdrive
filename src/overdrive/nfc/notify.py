"""overdrive-nfc-notify: the desktop side of the NFC reader (a systemd user service).

It connects to overdrive-nfcd and, for every tag, plays a sound and shows a desktop notification with what is on it, like a phone.
A link is opened only when "Open" is clicked in the notification.

Needs notify-send and pw-play (both present on Kinoite).
"""
import html
import json
import os
import shutil
import socket
import subprocess
import threading
import time

SOCKET_PATH = os.environ.get("OVERDRIVE_NFC_SOCK", "/run/overdrive-nfc/events.sock")
SOUND = "/usr/share/sounds/freedesktop/stereo/message-new-instant.oga"
OPENABLE = ("http://", "https://", "mailto:", "tel:")


def log(message):
    print(message, flush=True)


def flatten(records):
    """[(line, openable url or None)] for a list of NDEF records."""
    out = []
    for record in records:
        kind, value = record.get("kind"), record.get("value")
        if kind == "uri":
            out.append(("Link: " + value, value))
        elif kind == "text":
            out.append(("Text: " + value, None))
        elif kind == "smartposter":
            out.extend(flatten(value))
        elif kind == "mime":
            out.append(("Data: " + value, None))
        elif kind == "external":
            out.append(("Record: " + value, None))
        else:
            out.append((str(value), None))
    return out


def describe(event):
    """(notification lines, url to offer or None) for a tag event."""
    records = event.get("records")
    lines = flatten(records or [])
    url = next((u for _, u in lines if u), None)
    text = [line for line, _ in lines]
    if records is None:
        text.append("Card or device, no readable data")
    elif not lines:
        text.append("Empty or non-NDEF tag")
    text.append("%s, UID %s" % (event.get("type", "tag"), event.get("uid", "?")))
    return text, url


def play_sound():
    if shutil.which("pw-play") and os.path.exists(SOUND):
        subprocess.Popen(["pw-play", SOUND], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def notify(title, body, url):
    command = ["notify-send", "--app-name=NFC", "--icon=nfc", "--urgency=normal", "--expire-time=10000"]
    if url and url.startswith(OPENABLE):
        command += ["--action=open=Open", "--wait"]
    command += [title, html.escape(body)]

    def run():
        try:
            out = subprocess.run(command, capture_output=True, text=True, timeout=60).stdout.strip()
        except Exception as exc:                     # no notification daemon, timeout...
            log("notify-send failed: %s" % exc)
            return
        if out == "open" and url:
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    threading.Thread(target=run, daemon=True).start()


def window_open():
    """The NFC settings page shows the tags itself while it is open (it writes its pid here): no desktop notification then."""
    runtime = os.environ.get("XDG_RUNTIME_DIR", "/run/user/%d" % os.getuid())
    try:
        with open(os.path.join(runtime, "overdrive-nfc-window")) as f:
            return os.path.exists("/proc/%d" % int(f.read().strip()))
    except (OSError, ValueError):
        return False


def handle(event):
    text, url = describe(event)
    latency = time.time() - event.get("time", time.time())
    log("event %s: %s (delivered in %.0f ms)" % (event.get("uid"), " | ".join(text), latency * 1000))
    play_sound()
    if not window_open():
        notify("NFC tag detected", "\n".join(text), url)


def main():
    log("overdrive-nfc-notify running")
    while True:
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(SOCKET_PATH)
        except OSError as exc:
            log("waiting for overdrive-nfcd (%s)" % exc.strerror)
            time.sleep(3)
            continue
        log("connected to overdrive-nfcd")
        buffer = b""
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    try:
                        handle(json.loads(line))
                    except (ValueError, KeyError) as exc:
                        log("bad event: %s" % exc)
        except OSError:
            pass
        finally:
            sock.close()
        log("lost the connection to overdrive-nfcd, retrying")
        time.sleep(2)


if __name__ == "__main__":
    main()
