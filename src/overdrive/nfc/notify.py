"""overdrive-nfc-notify: the desktop side of the NFC reader (a systemd user service).

It connects to overdrive-nfcd and, for every tag, plays a sound and shows a desktop notification with what is on it, like a phone.
A link is opened only when "Open" is clicked in the notification.

Needs notify-send and pw-play (both present on Kinoite).
"""
import html
import json
import math
import os
import shutil
import socket
import struct
import subprocess
import threading
import time
import wave

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


def beep_file():
    """Our own beep: two short rising tones that start at full level, so that the tap is heard at once (desktop notification
    sounds fade in and add a tenth of a second). Written once per session."""
    path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "overdrive-nfc-beep.wav")
    if not os.path.exists(path):
        rate, frames = 48000, []
        for start, length, freq in ((0.0, 0.07, 1320.0), (0.07, 0.11, 1760.0)):
            count = int(length * rate)
            for i in range(count):
                fade = min(1.0, (count - i) / (0.02 * rate))            # no click at the end
                value = int(9000 * fade * math.sin(2 * math.pi * freq * i / rate))
                frames.append(struct.pack("<hh", value, value))
        with wave.open(path + ".tmp", "wb") as out:
            out.setnchannels(2)
            out.setsampwidth(2)
            out.setframerate(rate)
            out.writeframes(b"".join(frames))
        os.replace(path + ".tmp", path)
    return path


def play_sound():
    if not shutil.which("pw-play"):
        return
    try:
        sound = beep_file()
    except OSError:
        sound = SOUND
    # waited for in a thread, so that no finished player is left behind as a zombie
    threading.Thread(target=lambda: subprocess.run(["pw-play", "--latency=20ms", sound], stdout=subprocess.DEVNULL,
                                                   stderr=subprocess.DEVNULL, timeout=10, check=False), daemon=True).start()


def copy_text(text):
    """Put text on the clipboard (on a touch screen the text of a notification cannot be selected)."""
    if shutil.which("wl-copy"):
        subprocess.run(["wl-copy", "--", text], timeout=5, check=False)


def notify(title, body, url, content):
    """Show the notification. Its buttons: "Open" for a link, "Copy" for what the tag holds (its first record, or its UID)."""
    command = ["notify-send", "--app-name=NFC", "--icon=nfc", "--urgency=normal", "--expire-time=10000", "--wait"]
    if url and url.startswith(OPENABLE):
        command.append("--action=open=Open")
    command.append("--action=copy=Copy")
    command += [title, html.escape(body)]

    def run():
        try:
            out = subprocess.run(command, capture_output=True, text=True, timeout=60).stdout.strip()
        except Exception as exc:                     # no notification daemon, timeout...
            log("notify-send failed: %s" % exc)
            return
        if out == "open" and url:
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif out == "copy":
            copy_text(content)

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
        records = flatten(event.get("records") or [])
        content = url or (records[0][0].split(": ", 1)[-1] if records else event.get("uid", ""))
        notify("NFC tag detected", "\n".join(text), url, content)


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
