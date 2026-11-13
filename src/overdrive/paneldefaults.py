"""The owner's panel on panels that already exist, written into Plasma's files before plasmashell starts.

The image's default panel template (ci/patch_plasma_defaults.py) gives a NEW panel the owner's settings: dodge windows,
translucent, floating, no virtual desktop pager. A fresh install makes its panel at the first login, on stock Kinoite
before the switch to the image, so that panel kept Fedora's. A Plasma update script did it first (2026-11-13), but
removing the pager from a script while plasmashell started left the session without its panel and with a desktop that
ignored touches. This runs as ExecStartPre of plasma-plasmashell.service instead, on the files, once per user:
  plasmashellrc   [PlasmaViews][Panel <id>]: panelVisibility=2 (dodge windows), panelOpacity=2 (translucent), floating=1
  appletsrc       the pager's groups ([Containments][<id>][Applets][<n>] and below) and its number in AppletOrder
Only the panels (plugin org.kde.panel) are touched. Nothing is done before a panel exists (a new user's first start: the
template makes it right), and the state file is written once a panel was seen.
"""
import os
import re
import sys

from . import userconfig

DONE = "panel-defaults"
VIEW = {"panelVisibility": "2", "panelOpacity": "2", "floating": "1"}
PAGER = "org.kde.plasma.pager"


def parse(text):
    """[(group header or None for the top, [lines])] keeping every line as it is."""
    groups = [(None, [])]
    for line in text.splitlines(keepends=True):
        if line.startswith("[") and line.rstrip().endswith("]"):
            groups.append((line.rstrip("\r\n"), []))
        else:
            groups[-1][1].append(line)
    return groups


def unparse(groups):
    return "".join((header + "\n" if header else "") + "".join(lines) for header, lines in groups)


def value(lines, key):
    for line in lines:
        k, sep, v = line.partition("=")
        if sep and k.strip() == key:
            return v.strip()
    return None


def set_value(lines, key, val):
    """lines with key=val (changed in place or added before the trailing blank lines)."""
    out = list(lines)
    for i, line in enumerate(out):
        k, sep, _ = line.partition("=")
        if sep and k.strip() == key:
            out[i] = "%s=%s\n" % (key, val)
            return out
    end = len(out)
    while end and not out[end - 1].strip():
        end -= 1
    out.insert(end, "%s=%s\n" % (key, val))
    return out


def panels(applets_groups):
    """Containment ids of the panels."""
    ids = []
    for header, lines in applets_groups:
        m = re.fullmatch(r"\[Containments\]\[(\d+)\]", header or "")
        if m and value(lines, "plugin") == "org.kde.panel":
            ids.append(m.group(1))
    return ids


def without_pager(groups, panel):
    """The appletsrc groups without the panel's pagers, and AppletOrder without their numbers."""
    pagers = set()
    for header, lines in groups:
        m = re.fullmatch(r"\[Containments\]\[%s\]\[Applets\]\[(\d+)\]" % panel, header or "")
        if m and value(lines, "plugin") == PAGER:
            pagers.add(m.group(1))
    if not pagers:
        return groups, False
    prefix = tuple("[Containments][%s][Applets][%s]" % (panel, n) for n in pagers)
    out = []
    for header, lines in groups:
        if header and header.startswith(prefix):
            continue
        if header == "[Containments][%s][General]" % panel:
            order = value(lines, "AppletOrder")
            if order is not None:
                lines = set_value(lines, "AppletOrder", ";".join(n for n in order.split(";") if n and n not in pagers))
        out.append((header, lines))
    return out, True


def with_view(groups, panel):
    header = "[PlasmaViews][Panel %s]" % panel
    for i, (h, lines) in enumerate(groups):
        if h == header:
            for k, v in VIEW.items():
                lines = set_value(lines, k, v)
            groups[i] = (h, lines)
            return groups
    lines = ["%s=%s\n" % kv for kv in VIEW.items()] + ["\n"]
    if groups and groups[-1][1] and groups[-1][1][-1].strip():
        groups[-1] = (groups[-1][0], groups[-1][1] + ["\n"])
    return groups + [(header, lines)]


def apply(applets_text, shellrc_text):
    """(new appletsrc, new plasmashellrc, panel ids) — the texts unchanged when there is no panel."""
    applets = parse(applets_text)
    ids = panels(applets)
    shell = parse(shellrc_text)
    for panel in ids:
        applets, _ = without_pager(applets, panel)
        shell = with_view(shell, panel)
    if not ids:
        return applets_text, shellrc_text, ids
    return unparse(applets), unparse(shell), ids


def main():
    config = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    state = os.path.join(userconfig.CONFIG, DONE)
    if os.path.exists(state):
        return 0
    applets_path = os.path.join(config, "plasma-org.kde.plasma.desktop-appletsrc")
    shell_path = os.path.join(config, "plasmashellrc")
    try:
        applets_text = open(applets_path).read()
    except OSError:
        return 0                      # no desktop yet: the template makes the first panel right
    try:
        shell_text = open(shell_path).read()
    except OSError:
        shell_text = ""
    new_applets, new_shell, ids = apply(applets_text, shell_text)
    if not ids:
        return 0
    for path, old, new in ((applets_path, applets_text, new_applets), (shell_path, shell_text, new_shell)):
        if new != old:
            mode = os.stat(path).st_mode & 0o777 if os.path.exists(path) else 0o600
            userconfig.write_atomic(path, new)
            os.chmod(path, mode)
    os.makedirs(userconfig.CONFIG, exist_ok=True)
    userconfig.write_atomic(state, "panels %s\n" % " ".join(ids))
    print("panel defaults applied to panel(s) %s" % ", ".join(ids))
    return 0


if __name__ == "__main__":
    sys.exit(main())
