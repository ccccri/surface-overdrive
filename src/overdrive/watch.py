"""overdrive-health-watch: tells the user, once, when a fix stops working.

Runs from a systemd user timer. It reads the health checks and shows a desktop notification when the overall state got worse than
the last one it announced (and when it is green again). The notification only points to Settings > Software Update, which lists the Surface fixes, where
the explanation and the remedy are.

Update guard: the image in use is remembered with the problems it had. On the first check after an update, a fix that
worked on the image before and does not on the new one brings a notification that offers to start the previous image
again (rpm-ostree rollback, with the administrator password; the restart stays the user's). Never done by itself, asked
once per image.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import health, maintenance

RECHECK_S = 25
RANK = {health.OK: 0, health.NA: 0, health.WARN: 1, health.FAIL: 2}


def state_file():
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(base) / "surface-overdrive" / "health.json"


def problems(checks):
    return [c for c in checks if c.status in (health.WARN, health.FAIL)]


def decide(previous, checks):
    """(notification or None, new state). A notification is due when the set of problems changed to something new, or all cleared."""
    now = sorted(c.title for c in problems(checks))
    old = previous.get("problems", [])
    new_state = {"problems": now, "overall": health.overall(checks)}
    if not now:
        return ({"title": "Surface Control", "body": "Everything works again.", "urgent": False} if old else None), new_state
    if set(now) <= set(old):
        return None, new_state
    worst = max((c for c in problems(checks)), key=lambda c: RANK[c.status])
    body = "; ".join("%s: %s" % (c.title, c.detail) for c in problems(checks))
    return {"title": "Something on this Surface needs attention" if worst.status == health.WARN else "Something on this Surface does not work",
            "body": body, "urgent": worst.status == health.FAIL}, new_state


def booted_image(run=subprocess.run):
    """(id, version) of the image in use: its digest (or ostree checksum), from rpm-ostree."""
    try:
        data = json.loads(run(["rpm-ostree", "status", "--json"], capture_output=True, text=True, timeout=20).stdout)
        d = next(d for d in data.get("deployments", []) if d.get("booted"))
    except (OSError, ValueError, StopIteration, subprocess.SubprocessError, AttributeError):
        return None, None
    return str(d.get("container-image-reference-digest") or d.get("checksum") or ""), str(d.get("version") or "")


def decide_update(previous, image, version, checks, can_go_back):
    """(notification or None, update-guard state) after an update.

    previous holds "image" (the one of the last check) and "problems_on_image" (the problems it had then). When the image
    changed, the problems the old one did not have at its last check are the update's: a notification offers to go back,
    if there is an image to go back to. The state then holds the new image, so each update is judged once."""
    now = sorted(c.title for c in problems(checks))
    old_image = previous.get("image")
    state = {"image": image, "problems_on_image": now}
    if not image or not old_image or old_image == image:
        return None, state
    broken = [c for c in problems(checks) if c.title not in previous.get("problems_on_image", [])]
    if not broken or not can_go_back:
        return None, state
    body = "; ".join("%s: %s" % (c.title, c.detail) for c in broken)
    return {"title": "The update to %s broke something" % (version or "a new image"),
            "body": body + ". The image before it worked: it can start again at the next restart.",
            "urgent": True, "go_back": True}, state


def notify(note):
    actions = ["--action=back=Go back"] if note.get("go_back") else []
    cmd = ["notify-send", "--app-name=Surface Control", "--icon=preferences-desktop-tablet", *actions,
           "--action=open=Show fixes",
           "--urgency=%s" % ("critical" if note["urgent"] else "normal"), "--wait", note["title"], note["body"]]
    # waits for as long as the notification can be clicked (it stays in the history), not two minutes
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=12 * 3600).stdout.strip()
    if out == "back":
        done = maintenance.go_back()
        if done.get("result") == "ok":
            subprocess.run(["notify-send", "--app-name=Surface Control", "--icon=preferences-desktop-tablet",
                            "The previous image starts at the next restart",
                            "Restart when it suits you. Settings > Software Update can undo it."], timeout=30)
        else:
            subprocess.run(["notify-send", "--app-name=Surface Control", "--icon=dialog-error", "--urgency=critical",
                            "Could not go back", done.get("error") or "rpm-ostree rollback failed."], timeout=30)
        return
    if out == "open":
        # in a unit of its own: this check runs as a oneshot service, and systemd stops whatever is left in its group when it
        # ends, which closed System Settings as soon as it opened
        subprocess.run(["systemd-run", "--user", "--quiet", "--collect", "--unit=overdrive-show-fixes-%d" % os.getpid(),
                        "systemsettings", "kcm_overdrive_updates"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)


def main():
    path = state_file()
    try:
        previous = json.loads(path.read_text())
    except (OSError, ValueError):
        previous = {}
    checks = health.run_all()
    if not set(c.title for c in problems(checks)) <= set(previous.get("problems", [])):
        # Something new looks broken. It may be a service that is just restarting (the camera service does when the picture size
        # changes): look again in a while and only speak up when it is still broken.
        time.sleep(RECHECK_S)
        checks = health.run_all()
    note, state = decide(previous, checks)
    image, version = booted_image()
    can_go_back = maintenance.images().get("can_go_back", False) if image and image != previous.get("guard", {}).get("image") else False
    update_note, state["guard"] = decide_update(previous.get("guard", {}), image, version, checks, can_go_back)
    if update_note:
        note = update_note            # it says more than the plain one: what the update broke, and the way back
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state))
    if note:
        try:
            notify(note)
        except (OSError, subprocess.SubprocessError) as e:
            print("notification failed: %s" % e, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
