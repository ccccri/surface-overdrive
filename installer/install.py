#!/usr/bin/env python3
"""The Surface Overdrive installer's screen: a full-terminal show while Kinoite switches to the image.

bootstrap.sh downloads this file, root-step.sh and the module signing certificate, then runs it. It shows the machine
(neofetch style), asks for the administrator password ONCE in a window (pkexec; sudo in the terminal when there is no
desktop), asks the one-time password of the certificate in a window too when the certificate is not enrolled yet, and
while root-step.sh switches the system to the image (rpm-ostree rebase) it plays a scene that follows the progress:
Tux sends an old window logo away, then builds a house brick by brick as the image comes down, puts the roof on as it is
written to disk, and the day ends in fireworks. Under it: percentage, step, layer, amounts, speed, time left, the last
line of rpm-ostree. Everything rpm-ostree prints is kept in ~/surface-overdrive-install.log.

usage: install.py --cert <file.der> --helper <root-step.sh> --image <reference> [--demo]
       install.py --demo           (the show with a pretend install: nothing is changed)
"""
import argparse
import curses
import locale
import math
import os
import queue
import random
import re
import shutil
import subprocess
import sys
import threading
import time

LOG = os.path.expanduser("~/surface-overdrive-install.log")
# the picture, inside its frame: at least MIN (a smaller window is asked to grow to it), at most MAX (a larger one has it
# centred); in between it fills the window. Konsole opens maximized in tablet mode: asked to shrink, it only shrank its
# text area, into the top left corner, so it is never asked to shrink.
MIN_W, MIN_H = 88, 26
MAX_W, MAX_H = 124, 34
FALLBACK_TOTAL = 3.0e9                 # bytes, when rpm-ostree does not say how much it needs
UNITS = {"B": 1, "kB": 1e3, "KB": 1e3, "KiB": 1024, "MB": 1e6, "MiB": 1024 ** 2, "GB": 1e9, "GiB": 1024 ** 3}
SIZE = r"([\d.]+)\s*(B|[kKMG]i?B)"


def size(num, unit):
    return float(num) * UNITS.get(unit, 1)


def human(n):
    for unit, div in (("GB", 1e9), ("MB", 1e6), ("kB", 1e3)):
        if n >= div:
            return "%.1f %s" % (n / div, unit) if div > 1e3 else "%.0f %s" % (n / div, unit)
    return "%d B" % n


def clock(s):
    s = int(max(0, s))
    return "%d:%02d" % (s // 60, s % 60) if s < 3600 else "%d:%02d:%02d" % (s // 3600, s % 3600 // 60, s % 60)


# ---------------------------------------------------------------------------------------------------------------------
# What rpm-ostree says, turned into a percentage


class Progress:
    """Fed with root-step.sh's lines; knows the step, the layers and the share of the work done."""
    STEPS = [  # (pattern in rpm-ostree's output, step name, percentage at least)
        (r"Pulling manifest", "Asking GitHub for the image", 2),
        (r"Importing", "Comparing with this system", 3),
        (r"[Ff]etching|layers needed", "Downloading the image", 4),
        (r"Checking out|Writing OSTree commit|Committing|Resolving|Merging|Importing.*done", "Writing the image to disk", 86),
        (r"Staging deployment", "Getting it ready for the next start", 94),
        (r"Freed|Changes queued|systemctl reboot|Run \"systemctl", "Finishing", 98),
    ]

    def __init__(self):
        self.step = "Starting"
        self.floor = 0.0
        self.needed_layers = 0
        self.present_layers = 0
        self.total = 0.0              # bytes to download, from "layers needed: N (size)"
        self.fetched = 0.0            # bytes of the layers already done
        self.items = {}               # layer name -> bytes
        self.done_items = set()
        self.current = ""
        self.fetch_started = None
        self.last = ""
        self.mok = None               # enrolled, need, queued, off, failed
        self.mok_why = ""
        self.index = 0                # rpm-ostree's own "[n/N]" in front of each layer
        self.count = 0
        self.write_started = None
        self.finished = False
        self.failed = None

    def feed(self, raw):
        if raw.startswith("MOK "):
            word, _, why = raw[4:].partition(" ")
            self.mok, self.mok_why = word, why
            return
        if raw == "DONE":
            self.finished = True
            self.step, self.floor = "Done", 100.0
            return
        if raw.startswith("FAIL"):
            self.failed = raw[4:].strip() or "the install stopped"
            return
        text = raw[4:] if raw.startswith("LOG ") else raw
        for part in text.split("\r"):
            part = part.strip()
            if part:
                self._line(part)

    def _line(self, line):
        self.last = line
        m = re.search(r"layers already present:\s*(\d+)", line)
        if m:
            self.present_layers += int(m.group(1))
        m = re.search(r"layers needed:\s*(\d+)\s*\(" + SIZE + r"\)", line)
        if m:
            self.needed_layers += int(m.group(1))
            self.total += size(m.group(2), m.group(3))
        b = re.search(r"\[(\d+)/(\d+)\]\s*[Ff]etching", line)
        if b:
            self.index, self.count = int(b.group(1)), int(b.group(2))
        m = re.search(r"[Ff]etching\s+(.+?)\s*\(" + SIZE + r"\)", line)
        if m:
            name = m.group(1)
            self.items.setdefault(name, size(m.group(2), m.group(3)))
            self.current = "%s (%s)" % (name, human(self.items[name]))
            if self.fetch_started is None:
                self.fetch_started = time.monotonic()
            if re.search(r"\bdone\b", line[m.end():]) and name not in self.done_items:
                self.done_items.add(name)
                self.fetched += self.items[name]
        for pattern, step, floor in self.STEPS:
            if re.search(pattern, line):
                if floor >= self.floor:
                    self.step, self.floor = step, float(floor)
        # the last layer is in: rpm-ostree then writes the image to disk, saying nothing until it stages it
        if self.count and self.index >= self.count and re.search(r"\bdone\b", line) and self.floor < 86:
            self.step, self.floor = "Writing the image to disk", 86.0
        if self.floor >= 86 and self.write_started is None:
            self.write_started = time.monotonic()

    def percent(self, downloaded):
        """downloaded: bytes the network brought since the download started (an estimate between finished layers)."""
        if self.finished:
            return 100.0
        p = self.floor
        if 3 <= self.floor < 86:   # from the comparison on: the image comes down (rpm-ostree may not print each layer)
            total = self.total or FALLBACK_TOTAL
            got = max(self.fetched, min(downloaded, total * 0.995))
            p = max(p, 4 + 82 * min(got / total, 1.0))
        elif 86 <= self.floor < 94 and self.write_started is not None:
            # no output while it writes: it creeps towards 94% (half the way in a minute) so the roof keeps growing
            p = 86 + 8 * (1 - math.exp(-(time.monotonic() - self.write_started) / 85))
        return min(p, 99.5)

    def layer_text(self):
        if self.floor >= 86:
            return "%d layers downloaded, %s" % (self.count or len(self.done_items), human(self.total or self.fetched))
        if self.count and self.current:
            return "layer %d of %d: %s" % (self.index, self.count, self.current)
        if self.needed_layers:
            n = min(len(self.done_items) + (1 if self.current else 0), self.needed_layers)
            return "layer %d of %d: %s" % (max(n, 1), self.needed_layers, self.current) if self.current else \
                "%d layers to download, %d already here" % (self.needed_layers, self.present_layers)
        return self.current


class Net:
    """Bytes received by the machine (all interfaces but loopback), and a smoothed speed."""

    def __init__(self, path="/proc/net/dev"):
        self.path = path
        self.start = self.read()
        self.prev = (time.monotonic(), self.start)
        self.speed = 0.0

    def read(self):
        total = 0
        try:
            with open(self.path) as f:
                for line in f.readlines()[2:]:
                    name, data = line.split(":", 1)
                    if name.strip() != "lo":
                        total += int(data.split()[0])
        except (OSError, ValueError, IndexError):
            pass
        return total

    def tick(self):
        now, rx = time.monotonic(), self.read()
        dt = now - self.prev[0]
        if dt >= 0.5:
            inst = (rx - self.prev[1]) / dt
            self.speed = inst if self.speed == 0 else self.speed * 0.7 + inst * 0.3
            self.prev = (now, rx)
        return rx - self.start


# ---------------------------------------------------------------------------------------------------------------------
# The scene


TUX = [[" (o> ", " //\\ ", " V_/_"], [" (o> ", " //\\ ", " _\\_V"]]
TUX_LEFT = [[" <o) ", " /\\\\ ", " _\\_V"], [" <o) ", " /\\\\ ", " V_/_"]]
WINDOWS = ["▄▄▄ ▄▄▄", "███ ███", "▄▄▄ ▄▄▄", "███ ███"]
CLOUD = ["   .--.    ", " .(    ).  ", "(___.__)__)"]
LOGO = [
    "╭──────────────────────╮",
    "│ ╭──────────────────╮ │",
    "│ │  ▄▄▄ ▄  ▄ ▄▄▄    │ │",
    "│ │  █▄▄ █  █ █▄▀    │ │",
    "│ │  ▄▄█ ▀▄▄▀ █ █    │ │",
    "│ │   O V E R ▸▸     │ │",
    "│ │   D R I V E      │ │",
    "│ ╰──────────────────╯ │",
    "╰──────────┬┬──────────╯",
    "          ╱  ╲          ",
]


class Screen:
    PAIRS = {"sun": curses.COLOR_YELLOW, "sky": curses.COLOR_CYAN, "brick": curses.COLOR_RED,
             "ground": curses.COLOR_GREEN, "title": curses.COLOR_BLUE, "fire": curses.COLOR_MAGENTA,
             "win": curses.COLOR_BLUE, "text": curses.COLOR_WHITE}

    def __init__(self, win):
        self.win = win
        self.colors = {}
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        if curses.has_colors():
            curses.start_color()
            try:
                curses.use_default_colors()
                bg = -1
            except curses.error:
                bg = curses.COLOR_BLACK
            for i, (name, fg) in enumerate(self.PAIRS.items(), 1):
                curses.init_pair(i, fg, bg)
                self.colors[name] = curses.color_pair(i)
        self.fireworks = []
        self.birds = random.random() * 100
        self.clip = None              # (first column, one past the last): the scene stays inside its frame

    def c(self, name, bold=False):
        return self.colors.get(name, 0) | (curses.A_BOLD if bold else 0)

    def put(self, y, x, text, attr=0):
        h, w = self.win.getmaxyx()
        if y < 0 or y >= h or x >= w:
            return
        if self.clip:
            x0, x1 = self.clip
            if x < x0:
                text, x = text[x0 - x:], x0
            text = text[: max(0, x1 - x)]
        if x < 0:
            text, x = text[-x:], 0
        text = text[: max(0, w - x)]
        if not text:
            return
        try:
            if y == h - 1 and x + len(text) >= w:
                # the bottom right cell: addstr there moves the cursor off the screen, insstr does not
                if len(text) > 1:
                    self.win.addstr(y, x, text[:-1], attr)
                self.win.insstr(y, w - 1, text[-1], attr)
            else:
                self.win.addstr(y, x, text, attr)
        except curses.error:
            pass

    # -- the parts of the picture -----------------------------------------------------------------------------------

    def splash(self, top, left, info, t):
        for i, line in enumerate(LOGO):
            self.put(top + i, left, line, self.c("title", True) if 2 <= i <= 6 else self.c("text"))
        x = left + len(LOGO[0]) + 4
        for i, (key, value) in enumerate(info):
            if key is None:
                self.put(top + i, x, value, self.c("sun", True))
            else:
                self.put(top + i, x, "%-12s" % key, self.c("sky", True))
                self.put(top + i, x + 12, value)
        dots = "." * (int(t * 2) % 4)
        return x, dots

    def scene(self, top, left, width, height, pct, t, stage):
        """stage: intro | build | done. The house grows with pct; the sun crosses the sky and sets near the end."""
        ground = top + height - 1
        night = pct >= 97 or stage == "done"
        # sky: stars at night, the sun on an arc otherwise
        if night:
            rnd = random.Random(7)
            for _ in range(width // 4):
                sx, sy = rnd.randrange(width), rnd.randrange(height - 6)
                twinkle = "·" if (int(t * 3) + sx) % 7 else "*"
                self.put(top + sy, left + sx, twinkle, self.c("text"))
        else:
            sx = int((width - 6) * min(pct, 96) / 96)
            sy = int((height - 7) * (1 - math.sin(math.pi * min(pct, 96) / 96))) + 1
            self.put(top + sy - 1, left + sx, "\\ | /", self.c("sun", True))
            self.put(top + sy, left + sx, "- O -", self.c("sun", True))
            self.put(top + sy + 1, left + sx, "/ | \\", self.c("sun", True))
        # clouds drifting at their own speeds
        for i, (speed, row) in enumerate(((1.6, 1), (1.0, 4))):
            cx = int((t * speed * 2 + i * width / 2) % (width + 12)) - 12
            for j, line in enumerate(CLOUD):
                self.put(top + row + j, left + cx, line, self.c("text"))
        # a few birds now and then
        bx = int((t * 6 + self.birds) % (width * 3)) - 4
        if 0 <= bx < width and not night:
            self.put(top + 2, left + bx, "v  v" if int(t * 4) % 2 else "^  ^", self.c("text"))
        # ground
        self.put(ground, left, "▔" * width, self.c("ground", True))

        # the house grows with the terminal: wider walls on wide screens, more rows on tall ones
        house_w = max(24, min(40, (width // 3) // 4 * 4 + 2))
        wall_h = max(5, min(9, (height - 10) // 2))
        hx = left + max(14, (width - house_w) // 2 + 6)
        pile_x = left + 2
        build = min(max((pct - 4) / 82, 0), 1)
        bricks_per_row = (house_w - 2) // 4            # the rows set off by half a brick fit too
        laid = int(build * bricks_per_row * wall_h) if stage != "intro" else 0
        # the brick pile shrinks as the house grows
        pile = max(0, 3 - int(build * 3))
        for i in range(pile):
            self.put(ground - 1 - i, pile_x + i * 2, "[__]" * (pile - i), self.c("brick"))
        # the walls, row by row from the ground
        for r in range(wall_h):
            y = ground - 1 - r
            offset = 2 if r % 2 else 0
            row = ("  " if offset else "") + "[__]" * bricks_per_row
            n = min(max(laid - r * bricks_per_row, 0), bricks_per_row)
            if n:
                self.put(y, hx, row[: offset + n * 4][:house_w], self.c("brick", True))
        # roof, door and windows while the image is written; the sign and the flag at the end
        roof_full = (house_w + 2) // 4
        if pct >= 86 or stage == "done":
            roof_rows = roof_full if stage == "done" else min(roof_full, 1 + int((pct - 86) / 9 * roof_full))
            for i in range(roof_rows):
                y = ground - 1 - wall_h - i
                w = house_w + 2 - i * 4
                if w > 2:
                    self.put(y, hx - 1 + i * 2, "/" + "▒" * (w - 2) + "\\", self.c("sun"))
        if pct >= 92 or stage == "done":
            door = hx + house_w // 2 - 2
            self.put(ground - 1, door, "|▓▓|", self.c("text", True))
            self.put(ground - 2, door, "|▓▓|", self.c("text", True))
            self.put(ground - 3, door, " __ ", self.c("text", True))
            light = "▒" if night else "░"
            wy = ground - wall_h + 2
            offset = 2 if (ground - 1 - wy) % 2 else 0      # on the bricks of that row, in place of one
            for k in (1, bricks_per_row - 2):
                self.put(wy, hx + offset + 4 * k, "[" + light * 2 + "]", self.c("sun", True))
        if pct >= 96 or stage == "done":
            self.put(ground - 1 - wall_h - 1, hx + house_w // 2 - 5, " OVERDRIVE ", self.c("title", True) | curses.A_REVERSE)
            fy = ground - 1 - wall_h - roof_full
            self.put(fy - 1, hx + house_w // 2, "|>~", self.c("fire", True))
            self.put(fy, hx + house_w // 2, "|", self.c("text"))
        # Tux: the intro sends the old window logo away; then he carries bricks; at the end he jumps
        if stage == "intro":
            self._intro(ground, left, width, t)
        elif stage == "done":
            jump = 1 if int(t * 3) % 2 else 0
            frame = TUX[int(t * 3) % 2]
            for j, line in enumerate(frame):
                self.put(ground - 3 + j - jump, hx - 8, line, self.c("text", True))
            self.put(ground - 4 - jump, hx - 9, "\\o/" if jump else "", self.c("sun", True))
            # in the sky above the roof and its flag only
            self._fireworks(top, left, width, max(3, ground - 1 - wall_h - roof_full - 2 - top), t)
        else:
            self._worker(ground, pile_x + 8, hx - 6, t, build)

    def _intro(self, ground, left, width, t):
        lx = left + width - 14
        kick = 3.2
        if t < kick:
            for j, line in enumerate(WINDOWS):
                self.put(ground - 4 + j, lx, line, self.c("win", True))
            x = left + 2 + int((lx - left - 8) * t / kick)
            frame = TUX[int(t * 4) % 2]
            for j, line in enumerate(frame):
                self.put(ground - 3 + j, x, line, self.c("text", True))
        else:
            dt = t - kick
            if dt < 1.6:
                fx, fy = lx + int(dt * 18), ground - 4 - int(dt * dt * 6)
                for j, line in enumerate(WINDOWS):
                    self.put(fy + j, fx, line, self.c("win", True))
                self.put(ground - 5, lx - 6, "bye!", self.c("sun", True))
            elif dt < 3:
                self.put(fy_safe(ground), lx + 2, "*poof*", self.c("fire", True))
            frame = TUX[0]
            for j, line in enumerate(frame):
                self.put(ground - 3 + j, lx - 7, line, self.c("text", True))

    def _worker(self, ground, x_from, x_to, t, build):
        """Back and forth between the pile and the wall; a brick on his head on the way there."""
        span = max(x_to - x_from, 1)
        period = 2.0 * span / 9.0          # about 9 columns a second
        phase = (t % period) / period
        going = phase < 0.5
        frac = phase * 2 if going else (1 - phase) * 2
        x = x_from + int(span * frac)
        frames = TUX if going else TUX_LEFT
        frame = frames[int(t * 6) % 2]
        for j, line in enumerate(frame):
            self.put(ground - 3 + j, x, line, self.c("text", True))
        if going and build < 1:
            self.put(ground - 4, x + 1, "[__]", self.c("brick", True))

    def _fireworks(self, top, left, width, height, t):
        if not self.fireworks or self.fireworks[-1][0] < t - 0.7:
            self.fireworks.append((t, left + random.randrange(6, max(7, width - 6)), top + random.randrange(1, max(2, height - 1))))
        self.fireworks = [f for f in self.fireworks if t - f[0] < 2.2]
        for born, x, y in self.fireworks:
            age = t - born
            r = int(age * 3)
            if r == 0:
                self.put(y, x, "*", self.c("sun", True))
                continue
            for a in range(0, 360, 45):
                dx, dy = int(round(math.cos(math.radians(a)) * r * 2)), int(round(math.sin(math.radians(a)) * r))
                if not top <= y + dy < top + height:
                    continue
                self.put(y + dy, x + dx, "*" if age < 1.4 else "·", self.c("fire" if a % 90 else "sun", True))

    def frame(self, y, x, height, width):
        attr = self.c("sky")
        self.put(y, x, "╭" + "─" * (width - 2) + "╮", attr)
        for i in range(1, height - 1):
            self.put(y + i, x, "│", attr)
            self.put(y + i, x + width - 1, "│", attr)
        self.put(y + height - 1, x, "╰" + "─" * (width - 2) + "╯", attr)

    def bar(self, y, x, width, pct, attr):
        fill = int(width * pct / 100)
        part = "▏▎▍▌▋▊▉"[int((width * pct / 100 - fill) * 7)] if fill < width else ""
        self.put(y, x, "█" * fill + part, attr)
        self.put(y, x + fill + len(part), "░" * (width - fill - len(part)), self.c("text"))


def fy_safe(ground):
    return ground - 6


# ---------------------------------------------------------------------------------------------------------------------
# The run


def graphical():
    return bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))


def ask_mok_password():
    """The one-time password of the certificate, in a window (twice, at least 8 characters). None when cancelled."""
    text = ("Choose a one-time password for the Surface's signing key (at least 8 characters).\n\n"
            "You will type it once, at the next start, on a blue screen \"Perform MOK management\":\n"
            "Enroll MOK, Continue, Yes, this password, Reboot.")
    while True:
        r = subprocess.run(["kdialog", "--title", "Surface Overdrive", "--password", text], capture_output=True, text=True)
        if r.returncode != 0:
            return None
        pw = r.stdout.rstrip("\n")
        if len(pw) < 8:
            subprocess.run(["kdialog", "--title", "Surface Overdrive", "--sorry", "At least 8 characters, please."])
            continue
        r = subprocess.run(["kdialog", "--title", "Surface Overdrive", "--password", "The same password again, to check it."],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return None
        if r.stdout.rstrip("\n") == pw:
            return pw
        subprocess.run(["kdialog", "--title", "Surface Overdrive", "--sorry", "The two passwords differ. Once more, please."])


def machine_info(image):
    def read(path, default=""):
        try:
            with open(path) as f:
                return f.read().strip()
        except OSError:
            return default
    osr = dict(line.split("=", 1) for line in read("/etc/os-release").splitlines() if "=" in line)
    name = osr.get("PRETTY_NAME", "Linux").strip('"')
    mem = 0
    for line in read("/proc/meminfo").splitlines():
        if line.startswith("MemTotal:"):
            mem = int(line.split()[1]) * 1024
    cpu = ""
    for line in read("/proc/cpuinfo").splitlines():
        if line.startswith("model name"):
            cpu = re.sub(r"\(R\)|\(TM\)|CPU|@.*", "", line.split(":", 1)[1]).split()
            cpu = " ".join(cpu)
            break
    sb = subprocess.run(["mokutil", "--sb-state"], capture_output=True, text=True).stdout if shutil.which("mokutil") else ""
    user = "%s@%s" % (os.environ.get("USER", "you"), os.uname().nodename)
    return [
        (None, user),
        (None, "─" * len(user)),
        ("Device", read("/sys/class/dmi/id/product_name", "unknown")),
        ("System", name),
        ("Kernel", os.uname().release),
        ("Processor", cpu or "unknown"),
        ("Memory", human(mem)),
        ("Secure Boot", "on" if "enabled" in sb.lower() else "off"),
        ("Installing", image.split(":", 1)[-1] if image else "Surface Overdrive"),
    ]


class Run:
    def __init__(self, args):
        self.args = args
        self.p = Progress()
        self.lines = queue.Queue()
        self.proc = None
        self.mok_answered = False
        self.status = "A window asks for your password, to install Surface Overdrive"
        self.log = open(LOG, "a")
        self.log.write("\n==== %s install of %s\n" % (time.strftime("%F %T"), args.image or "demo"))

    # -- the administrator part -------------------------------------------------------------------------------------

    def start(self):
        if self.args.demo:
            threading.Thread(target=self._demo, daemon=True).start()
            return
        # run directly (not through /bin/bash): the administrator window names it, "install-surface-overdrive"
        cmd = [self.args.helper_cmd, self.args.helper, self.args.cert, self.args.image]
        if self.args.helper_cmd == "sudo":
            cmd.insert(1, "-n")
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, bufsize=1)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            self.lines.put(line.rstrip("\n"))
        code = self.proc.wait()
        if code in (126, 127) and self.args.helper_cmd == "pkexec":
            self.lines.put("FAIL the administrator password was not given (the window was closed)")
        else:
            self.lines.put("EXIT %d" % code)

    def answer_mok(self, pw):
        if self.args.demo:
            return
        try:
            self.proc.stdin.write((pw or "") + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    def _demo(self):
        """A pretend install with rpm-ostree's kinds of lines, a little faster than the real one."""
        say = self.lines.put
        time.sleep(2.5)
        say("MOK enrolled")
        say("LOG Pulling manifest: ostree-unverified-registry:ghcr.io/ccccri/surface-overdrive:45")
        time.sleep(1)
        say("LOG Importing: ostree-unverified-registry:ghcr.io/ccccri/surface-overdrive:45 (digest: sha256:9a1f)")
        say("LOG ostree chunk layers already present: 0")
        say("LOG ostree chunk layers needed: 40 (1.6 GB)")
        say("LOG custom layers needed: 12 (1.1 GB)")
        rnd = random.Random(3)
        sizes = [rnd.uniform(20, 90) for _ in range(40)] + [rnd.uniform(40, 160) for _ in range(12)]
        scale = 2700 / sum(sizes)
        for i, mb in enumerate(sizes):
            kind = "ostree chunk" if i < 40 else "layer"
            name = "%s %s" % (kind, "%07x" % rnd.getrandbits(28))
            mb *= scale
            time.sleep(mb / self.args.demo_speed)
            self.demo_rx += mb * 1e6
            say("LOG [%d/%d] Fetching %s (%.1f MB)...done" % (i + 1, len(sizes), name, mb))
        time.sleep(8)                              # rpm-ostree writes the image, saying nothing
        for line, wait in (("Staging deployment...done", 3), ("Upgraded:", 0.2), ("Added:", 0.2),
                           ('Changes queued for next boot. Run "systemctl reboot" to start a reboot', 0.5)):
            say("LOG " + line)
            time.sleep(wait)
        say("DONE")

    # -- the screen -------------------------------------------------------------------------------------------------

    def __call__(self, win):
        self.demo_rx = 0.0
        h0, w0 = win.getmaxyx()
        if h0 < MIN_H + 2 or w0 < MIN_W + 2:
            sys.stdout.write("\x1b[8;%d;%dt" % (max(h0, MIN_H + 2), max(w0, MIN_W + 2)))
            sys.stdout.flush()
            time.sleep(0.3)
            curses.update_lines_cols()
        scr = Screen(win)
        win.nodelay(True)
        net = Net()
        info = machine_info(self.args.image)
        t0 = time.monotonic()
        build_t0 = None
        ended_t = None
        downloaded0 = None
        self.start()
        while True:
            # what root-step.sh said
            while True:
                try:
                    line = self.lines.get_nowait()
                except queue.Empty:
                    break
                if line.startswith("EXIT "):
                    if not self.p.finished and not self.p.failed:
                        self.p.failed = "the install ended with status %s (see %s)" % (line[5:], LOG)
                    continue
                self.log.write(line + "\n")
                self.log.flush()
                self.p.feed(line)
                if self.p.mok == "need" and not self.mok_answered:
                    self.mok_answered = True
                    self.status = "Choose the one-time password of the signing key (a window)"
                    threading.Thread(target=lambda: self.answer_mok(ask_mok_password()), daemon=True).start()
                elif self.p.mok in ("enrolled", "queued", "off") and self.status:
                    self.status = ""
            if self.p.failed:
                return "failed"
            now = time.monotonic()
            t = now - t0
            rx = self.demo_rx if self.args.demo else net.tick()
            if self.args.demo:
                net.speed = self.args.demo_speed * 1e6
            if (self.p.fetch_started or self.p.floor >= 3) and downloaded0 is None:
                downloaded0 = rx
            pct = self.p.percent(rx - downloaded0 if downloaded0 is not None else 0)
            if self.p.mok is not None and build_t0 is None and self.p.step != "Starting":
                build_t0 = now
            stage = "done" if self.p.finished else ("intro" if build_t0 is None or now - build_t0 < 5.5 else "build")
            if self.p.finished and ended_t is None:
                ended_t = now

            win.erase()
            h, w = win.getmaxyx()
            # one fixed picture, framed and centred: the same show whatever the window; a smaller window gets the
            # numbers only, with a word on the size it needs
            fits = w >= MIN_W + 2 and h >= MIN_H + 2
            canvas_h = min(h - 2, MAX_H) if fits else 0
            width = min(w - 2, MAX_W)
            left = (w - width) // 2
            oy = (h - canvas_h) // 2 if fits else -1
            if fits:
                scr.frame(oy - 1, left - 1, canvas_h + 2, width + 2)
            title = " S U R F A C E   O V E R D R I V E "
            scr.put(oy + 1 if fits else 0, left + (width - len(title)) // 2, title, scr.c("title", True) | curses.A_REVERSE)
            panel_h = 7
            scene_h = canvas_h - panel_h - 2 if fits else 0
            if not fits:
                note = "Make this window at least %d x %d to see the show (now %d x %d)" % (MIN_W + 2, MIN_H + 2, w, h)
                scr.put(2, max(0, (w - len(note)) // 2), note[:w], scr.c("sky"))
            elif build_t0 is None:
                # the splash, neofetch style, while the administrator password is asked
                top = oy + 2 + max(0, (scene_h - len(LOGO)) // 2)
                lx = left + max(0, (width - len(LOGO[0]) - 4 - 46) // 2)
                scr.splash(top, lx, info, t)
            else:
                scr.clip = (left, left + width)
                scr.scene(oy + 2, left, width, scene_h, pct, now - build_t0, stage)
                scr.clip = None
            # the panel: what is going on, in numbers
            y = oy + canvas_h - panel_h if fits else h - panel_h
            scr.put(y, left, "─" * width, scr.c("sky"))
            bar_w = width - 8
            scr.bar(y + 1, left, bar_w, pct, scr.c("brick" if pct < 100 else "ground", True))
            scr.put(y + 1, left + bar_w + 2, "%5.1f%%" % pct, scr.c("text", True))
            step = self.status or self.p.step
            if self.p.mok == "queued" and not self.status:
                step += "   ·   signing key: to confirm at the next start"
            scr.put(y + 2, left, step[:width], scr.c("sun", True))
            scr.put(y + 3, left, self.p.layer_text()[:width])
            if downloaded0 is not None and self.p.floor < 86:
                total = self.p.total or FALLBACK_TOTAL
                got = min(max(self.p.fetched, rx - (downloaded0 or 0)), total)
                left_s = (total - got) / net.speed if net.speed > 1e4 else None
                nums = "%s of %s   %s/s   %s   elapsed %s" % (
                    human(got), human(total), human(net.speed), ("about %s left" % clock(left_s)) if left_s else "",
                    clock(t))
                scr.put(y + 4, left, nums[:width], scr.c("sky", True))
            else:
                scr.put(y + 4, left, "elapsed %s" % clock(t), scr.c("sky", True))
            scr.put(y + 5, left, ("› " + self.p.last)[:width], scr.c("text"))
            if self.p.finished:
                msg = "Done! Press R to restart now, Q to restart later."
                if self.p.mok == "queued":
                    msg = "Done! At the restart: blue screen → Enroll MOK, Continue, Yes, your one-time password, Reboot.   R = restart now, Q = later"
                scr.put(y + 2, left, msg[:width], scr.c("ground", True))
            win.refresh()

            try:
                key = win.getch()
            except curses.error:
                key = -1
            if self.p.finished and key in (ord("r"), ord("R")):
                return "reboot"
            if self.p.finished and key in (ord("q"), ord("Q"), 27):
                return "done"
            time.sleep(0.1)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cert")
    ap.add_argument("--helper")
    ap.add_argument("--image")
    ap.add_argument("--demo", action="store_true", help="the show only: nothing is installed")
    ap.add_argument("--demo-speed", type=float, default=60.0, help="MB/s of the pretend download")
    args = ap.parse_args(argv)
    if not args.demo and not (args.cert and args.helper and args.image):
        ap.error("--cert, --helper and --image are needed (or --demo)")
    locale.setlocale(locale.LC_ALL, "")
    args.helper_cmd = "pkexec" if graphical() and shutil.which("pkexec") else "sudo"
    if not args.demo and args.helper_cmd == "sudo":
        print("Administrator password (no desktop here, so in the terminal):")
        if subprocess.run(["sudo", "-v"]).returncode != 0:
            return 1
    run = Run(args)
    try:
        result = curses.wrapper(run)
    except KeyboardInterrupt:
        print("\nThe screen was closed. The install goes on only if it had started: see %s" % LOG)
        return 130
    p = run.p
    if result == "failed":
        print("\nThe install stopped: %s" % p.failed)
        print("Nothing was changed on the next start unless the log says otherwise. The whole output: %s" % LOG)
        if p.last:
            print("Last line: %s" % p.last)
        return 1
    print("\nSurface Overdrive is ready for the next start.")
    if p.mok == "queued":
        print("At the restart a blue screen \"Perform MOK management\" appears:\n"
              "  Enroll MOK  ->  Continue  ->  Yes  ->  the one-time password  ->  Reboot")
    if result == "reboot" and not args.demo:
        subprocess.run(["systemctl", "reboot"])
    else:
        print("Restart when you like:  systemctl reboot")
    return 0


if __name__ == "__main__":
    sys.exit(main())
