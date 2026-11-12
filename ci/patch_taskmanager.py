#!/usr/bin/env python3
"""A "Force Quit" entry in the task manager's context menu (the menu of an open app's icon in the panel), in plasma-desktop's
source tree.

"Close" asks the app to close, and an app that hangs never answers. Force Quit ends it at once: Plasma starts every app in a
systemd unit of its own (app-<...>.scope or app-<...>@<...>.service), and the whole unit is killed, with the helper processes
around the app (a Flatpak's wrapper and sandbox stayed behind when only the app's process was killed). An app outside such
a unit gets its own process killed. Nothing else is touched: the unit must be an app- one, and plasmashell itself never.

When the files have a layout this was not written for, nothing is changed and the build goes on with Fedora's applet.

usage: patch_taskmanager.py <plasma-desktop source tree>
"""
import sys
from pathlib import Path

MARK = "Surface Overdrive"
H = "applets/taskmanager/backend.h"
CPP = "applets/taskmanager/backend.cpp"
QML = "applets/taskmanager/qml/ContextMenu.qml"

EDITS = {
    H: [("""    Q_INVOKABLE qint64 parentPid(qint64 pid) const;
""", """    Q_INVOKABLE qint64 parentPid(qint64 pid) const;
    // %s: the app of this process ended at once ("Force Quit" in the context menu)
    Q_INVOKABLE void forceQuit(qint64 pid) const;
""" % MARK)],
    CPP: [("""#include <QTimer>
""", """#include <QTimer>
#include <QFile>
#include <QProcess>
#include <csignal>
#include <unistd.h>
"""), ("""qint64 Backend::parentPid(qint64 pid) const
""", """// %s: the systemd unit Plasma started the app in is killed whole (a Flatpak's wrapper and sandbox with it); a process
// outside an app- unit gets only itself killed. Never plasmashell.
void Backend::forceQuit(qint64 pid) const
{
    if (pid <= 1 || pid == static_cast<qint64>(getpid())) {
        return;
    }
    QString unit;
    QFile cgroup(QStringLiteral("/proc/%%1/cgroup").arg(pid));
    if (cgroup.open(QIODevice::ReadOnly)) {
        const QString path = QString::fromUtf8(cgroup.readAll()).trimmed().section(QLatin1Char('\\n'), -1).section(QLatin1Char(':'), 2);
        const QString last = path.section(QLatin1Char('/'), -1);
        if (last.startsWith(QLatin1String("app-")) && (last.endsWith(QLatin1String(".scope")) || last.endsWith(QLatin1String(".service")))) {
            unit = last;
        }
    }
    if (!unit.isEmpty()
        && QProcess::startDetached(QStringLiteral("systemctl"), {QStringLiteral("--user"), QStringLiteral("kill"), QStringLiteral("--signal=KILL"), unit})) {
        return;
    }
    ::kill(static_cast<pid_t>(pid), SIGKILL);
}

qint64 Backend::parentPid(qint64 pid) const
""" % MARK)],
    QML: [("""    PlasmaExtras.MenuItem {
        id: closeWindowItem
""", """    // %s: ends a hung app at once (Backend::forceQuit), where Close waits for the app to agree
    PlasmaExtras.MenuItem {
        id: forceQuitItem
        visible: closeWindowItem.visible && !menu.get(TaskManager.AbstractTasksModel.IsGroupParent)
                 && menu.get(TaskManager.AbstractTasksModel.AppPid) > 0
        text: i18nc("@action:inmenu", "Force Quit")
        icon: "process-stop"
        onClicked: menu.backend.forceQuit(menu.get(TaskManager.AbstractTasksModel.AppPid))
    }

    PlasmaExtras.MenuItem {
        id: closeWindowItem
""" % MARK)],
}


def patch(root):
    root = Path(root)
    new = {}
    for rel, pairs in EDITS.items():
        p = root / rel
        if not p.exists():
            print("skipped: %s not found" % rel)
            return False
        text = p.read_text()
        if MARK in text:
            print("skipped: %s already patched" % rel)
            return False
        for old, rep in pairs:
            if text.count(old) != 1:
                print("skipped: %s has another layout (Fedora's task manager is used)" % rel)
                return False
            text = text.replace(old, rep)
        new[p] = text
    for p, text in new.items():
        p.write_text(text)
    print("patched: Force Quit in the task manager's context menu")
    return True


if __name__ == "__main__":
    patch(sys.argv[1])
