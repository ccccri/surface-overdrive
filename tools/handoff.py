#!/usr/bin/env python3
"""Turn handoff helper for the agents working on Surface Overdrive (Claude Code and OpenCode).

  python3 tools/handoff.py start --agent claude    begin a turn: show context, take the lock
  python3 tools/handoff.py end --agent claude      end a turn: run checks, release the lock
  python3 tools/handoff.py status                  read-only summary

The lock file (team/.active, git-ignored) records which agent is working, so the other agent
can tell when a turn was left unfinished. See AGENTS.md sections 1-2.
"""

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAM = os.path.join(ROOT, "team")
LOCK = os.path.join(TEAM, ".active")
STATUS = os.path.join(TEAM, "STATUS.md")
LOG = os.path.join(TEAM, "LOG.md")
AGENTS = ("claude", "opencode")

TRAILERS = {
    "claude": "Co-Authored-By: Claude (<model>) <noreply@anthropic.com>",
    "opencode": "Co-Authored-By: OpenCode (<model>) <noreply@opencode.ai>",
}

# Patterns that must never be committed: this repository is PUBLIC. Placeholders like REPLACE_ME are fine, and a line that
# has to mention something of the kind on purpose carries the word team-allow-secret.
ALLOW = "team-allow-secret"
SECRET_PATTERNS = [
    ("a password piped to sudo", re.compile(r"echo\s+['\"][^'\"\s]+['\"]\s*\|\s*sudo\s+-S")),
    ("a credential-looking assignment", re.compile(
        r"(?i)\b(pass(?:word|wd)?|pin|pattern|token|secret|api[_-]?key)\b\s*[:=]\s*['\"]?(?=[A-Za-z0-9_\-./+=]*\d)(?!REPLACE_ME)[A-Za-z0-9_\-./+=]{6,}")),
    ("a GitHub token", re.compile(r"\b(?:ghp|gho|ghs|github_pat)_[A-Za-z0-9_]{20,}")),
    ("a private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("a bearer token", re.compile(r"(?i)authorization:\s*bearer\s+\S{10,}")),
]
SKIP_SCAN = {"tools/handoff.py", "tests/test_handoff.py"}  # contain the patterns themselves
SKIP_SCAN_DIRS = ("patches/", "build/", "old-project-chat-archive/")

BOLD, RED, YELLOW, GREEN, RESET = "\033[1m", "\033[31m", "\033[33m", "\033[32m", "\033[0m"
if not sys.stdout.isatty():
    BOLD = RED = YELLOW = GREEN = RESET = ""


def git(*args):
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return out.stdout.rstrip()


def today():
    return dt.date.today().isoformat()


def title(text):
    print(f"\n{BOLD}== {text} =={RESET}")


def warn(text):
    print(f"{YELLOW}WARNING:{RESET} {text}")


def fail(text):
    print(f"{RED}FAIL:{RESET} {text}")


def ok(text):
    print(f"{GREEN}OK:{RESET} {text}")


# --- Reading the team files ---------------------------------------------------

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def top_log_entry():
    """Return (header_line, full_text) of the newest LOG.md entry, or (None, None)."""
    text = read(LOG).split("<!-- entries below -->", 1)[-1]
    parts = re.split(r"(?m)^(?=## \d{4}-\d{2}-\d{2} )", text)
    entries = [p.strip() for p in parts if p.startswith("## ")]
    if not entries:
        return None, None
    return entries[0].splitlines()[0], entries[0]


def parse_entry_header(header):
    m = re.match(r"## (\d{4}-\d{2}-\d{2}) — (\w+) — (.+)", header or "")
    return (m.group(1), m.group(2).lower(), m.group(3)) if m else (None, None, None)


def status_section(name):
    m = re.search(rf"(?ms)^## {re.escape(name)}\s*\n(.*?)(?=^## |\Z)", read(STATUS))
    return m.group(1).strip() if m else ""


def status_header():
    head = read(STATUS).split("## ", 1)[0]
    return "\n".join(line for line in head.splitlines() if line.startswith("**"))


def last_updated():
    m = re.search(r"\*\*Last updated:\*\*\s*(\d{4}-\d{2}-\d{2})\s+by\s+(\w+)", read(STATUS))
    return (m.group(1), m.group(2).lower()) if m else (None, None)


def read_lock():
    try:
        with open(LOCK, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# --- Git helpers ----------------------------------------------------------------

def last_handoff_commit():
    return git("log", "-1", "--format=%H", "--", "team/LOG.md")


def uncommitted():
    lines = git("status", "--porcelain").splitlines()
    return [ln for ln in lines if not ln.endswith("team/.active")]


def changed_files():
    files = set(git("diff", "--name-only", "HEAD").splitlines())
    files |= set(git("ls-files", "--others", "--exclude-standard").splitlines())
    return sorted(f for f in files if f and os.path.isfile(os.path.join(ROOT, f)))


# --- Commands -----------------------------------------------------------------

def show_summary():
    title("Status (team/STATUS.md)")
    print(status_header())
    print("\nNext step:\n" + status_section("Next step"))
    open_tasks = [ln for ln in read(STATUS).splitlines()
                  if re.match(r"\s*- \[( |~|!)\] T-\d+", ln)]
    print("\nOpen tasks:")
    print("\n".join(open_tasks) if open_tasks else "(none)")

    title("Last handoff (top of team/LOG.md)")
    _, entry = top_log_entry()
    print(entry or "(no entries yet)")

    title("Git")
    h = last_handoff_commit()
    if h:
        print("Last commit touching the log: " + git("log", "-1", "--format=%h %ad %s", "--date=short", h))
        since = git("log", "--format=%h %ad %an: %s", "--date=short", f"{h}..HEAD")
        print("Commits since then:\n" + (since or "(none)"))
    print("Recent commits:\n" + git("log", "-5", "--format=%h %ad %s", "--date=short"))
    dirty = uncommitted()
    if dirty:
        warn("uncommitted changes in the working tree:")
        print("\n".join(dirty))
        print("Diff summary:\n" + (git("diff", "--stat", "HEAD") or "(only untracked files)"))
    else:
        ok("working tree clean")

    lock = read_lock()
    title("Active agent")
    print(f"{lock['agent']} since {lock['since']}" if lock else "nobody")


def cmd_status(args):
    show_summary()
    return 0


def cmd_start(args):
    lock = read_lock()
    show_summary()
    title("Start checks")
    code = 0
    if lock and lock["agent"] != args.agent:
        fail(f"{lock['agent']} started a turn at {lock['since']} and did not run 'end'. "
             "Ask the user before continuing (use --force to take over).")
        code = 2
    if uncommitted() and not (lock and lock["agent"] == args.agent):
        warn("there are uncommitted changes you did not make. Read them before editing; "
             "tell the user if they look unfinished.")
    if code and not args.force:
        return code
    with open(LOCK, "w", encoding="utf-8") as f:
        json.dump({"agent": args.agent, "since": dt.datetime.now().isoformat(timespec="seconds"),
                   "head": git("rev-parse", "--short", "HEAD")}, f)
    ok(f"lock taken by {args.agent}. Read team/STATUS.md, the log entry above, team/DECISIONS.md and "
       "team/CONTEXT.md before working; team/KNOWLEDGE.md before touching anything on the tablet or in the image.")
    return 0


def opaque_strings(line):
    """Long strings that mix capitals, small letters and digits: what a key or a token looks like (a git hash or a file name does not)."""
    return [w for w in re.findall(r"[A-Za-z0-9_\-]{32,}", line)
            if len(re.findall(r"[A-Z]", w)) >= 3 and len(re.findall(r"[a-z]", w)) >= 3 and len(re.findall(r"\d", w)) >= 3]


def scan_text(rel, text):
    hits = []
    for number, line in enumerate(text.splitlines(), 1):
        if ALLOW in line:
            continue
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                hits.append(f"{rel}:{number}: {label}")
        if opaque_strings(line):
            hits.append(f"{rel}:{number}: an opaque string that may be a key or a token")
    return hits


def scan_secrets(files):
    hits = []
    for rel in files:
        if rel in SKIP_SCAN or rel.startswith(SKIP_SCAN_DIRS) or rel.endswith((".png", ".jpg", ".ico", ".der", ".patch", ".svg", ".so", ".gz", ".xz", ".tar")):
            continue
        try:
            text = read(os.path.join(ROOT, rel))
        except (OSError, UnicodeDecodeError):
            continue
        hits += scan_text(rel, text)
    return hits


def cmd_end(args):
    errors = 0
    title("End checks")

    lock = read_lock()
    if not lock:
        warn("no lock found: did you run 'start'?")
    elif lock["agent"] != args.agent:
        fail(f"the lock belongs to {lock['agent']}, not {args.agent}")
        errors += 1

    if args.skip_tests:
        warn("tests skipped (--skip-tests)")
    else:
        res = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                             cwd=ROOT, capture_output=True, text=True,
                             env=dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src")))
        summary = [ln for ln in res.stderr.splitlines() if ln.startswith(("Ran ", "OK", "FAILED"))]
        if res.returncode == 0:
            ok("tests: " + " ".join(summary))
        else:
            fail("tests failed:\n" + res.stderr[-3000:])
            errors += 1

    header, _ = top_log_entry()
    date, agent, _ = parse_entry_header(header)
    if date == today() and agent == args.agent:
        ok(f"log entry: {header}")
    else:
        fail(f"add a new entry for today by {args.agent} at the top of team/LOG.md "
             f"(top entry is: {header})")
        errors += 1

    s_date, s_agent = last_updated()
    if s_date == today() and s_agent == args.agent:
        ok("team/STATUS.md 'Last updated' is current")
    else:
        fail(f"update '**Last updated:** {today()} by {args.agent}' and the task list in team/STATUS.md")
        errors += 1

    notes = ["AGENTS.md", "CLAUDE.md"] + sorted("team/" + n for n in os.listdir(TEAM) if n.endswith(".md"))
    hits = scan_secrets(sorted(set(changed_files()) | set(notes)))
    if hits:
        fail("possible secrets in changed files:\n  " + "\n  ".join(hits))
        errors += 1
    else:
        ok("no secrets found in changed files")

    if errors:
        print(f"\n{RED}{errors} problem(s): fix them and run 'end' again. Lock kept.{RESET}")
        return 1

    if os.path.exists(LOCK):
        os.remove(LOCK)
    ok("lock released")
    print("\nNow commit your turn, for example:\n"
          f"  git add -A && git commit -m \"<summary> (T-NN)\" -m \"{TRAILERS[args.agent]}\"\n"
          "Push to main when the work is meant to reach the tablet (CI builds the image from main); never cancel a CI run.")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start", help="begin a turn")
    s.add_argument("--agent", required=True, choices=AGENTS)
    s.add_argument("--force", action="store_true", help="take over another agent's lock")
    e = sub.add_parser("end", help="end a turn")
    e.add_argument("--agent", required=True, choices=AGENTS)
    e.add_argument("--skip-tests", action="store_true")
    sub.add_parser("status", help="read-only summary")
    args = p.parse_args(argv)
    return {"start": cmd_start, "end": cmd_end, "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
