"""overdrive-health-watch: tells the user, once, when a fix stops working.

Runs from a systemd user timer. It reads the health checks and shows a desktop notification when the overall state got worse than
the last one it announced (and when it is green again). The notification only points to Settings > Surface Control > Overview, where
the explanation and the remedy are.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from . import health

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


def notify(note):
    cmd = ["notify-send", "--app-name=Surface Control", "--icon=preferences-desktop-tablet", "--action=open=Open Surface Control",
           "--urgency=%s" % ("critical" if note["urgent"] else "normal"), "--wait", note["title"], note["body"]]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=120).stdout.strip()
    if out == "open":
        subprocess.Popen(["systemsettings", "kcm_overdrive"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    path = state_file()
    try:
        previous = json.loads(path.read_text())
    except (OSError, ValueError):
        previous = {}
    note, state = decide(previous, health.run_all())
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
