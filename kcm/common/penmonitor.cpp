// SPDX-License-Identifier: MIT
#include "penmonitor.h"

#include <QCoreApplication>
#include <QDebug>
#include <QKeyEvent>
#include <QTabletEvent>
#include <QWindow>

PenMonitor::PenMonitor(QObject *parent)
    : QObject(parent)
{
}

PenMonitor::~PenMonitor()
{
    setActive(false);
}

bool PenMonitor::active() const
{
    return m_active;
}

void PenMonitor::setActive(bool active)
{
    if (m_active == active) {
        return;
    }
    m_active = active;
    if (active) {
        qApp->installEventFilter(this);
    } else {
        qApp->removeEventFilter(this);
    }
    Q_EMIT activeChanged();
}

bool PenMonitor::eventFilter(QObject *watched, QEvent *event)
{
    const QEvent::Type type = event->type();
    // The same sample passes here several times: for the real window, then for the widget and the off-screen Qt Quick window that
    // System Settings draws the page in, each time with coordinates of its own. Only the real window counts.
    auto *window = qobject_cast<QWindow *>(watched);
    const bool realWindow = window && window->handle();

    // The click of the top button does not come through the screen: the pen sends it over Bluetooth as a key, the Windows key with
    // F20 (one click), F19 (two clicks) or F18 (press and hold).
    if (type == QEvent::KeyPress && realWindow) {
        auto *key = static_cast<QKeyEvent *>(event);
        if (!key->isAutoRepeat() && key->key() >= Qt::Key_F18 && key->key() <= Qt::Key_F20) {
            Q_EMIT topButton(key->key() == Qt::Key_F20 ? QStringLiteral("click") : key->key() == Qt::Key_F19 ? QStringLiteral("double") : QStringLiteral("hold"));
        }
        return false;
    }

    QString kind;
    switch (type) {
    case QEvent::TabletMove:
        kind = QStringLiteral("move");
        break;
    case QEvent::TabletPress:
        kind = QStringLiteral("press");
        break;
    case QEvent::TabletRelease:
        kind = QStringLiteral("release");
        break;
    case QEvent::TabletEnterProximity:
        kind = QStringLiteral("enter");
        break;
    case QEvent::TabletLeaveProximity:
        kind = QStringLiteral("leave");
        break;
    default:
        return false;
    }
    // Entering and leaving the range of the screen is told to the application, not to a window.
    const bool proximity = type == QEvent::TabletEnterProximity || type == QEvent::TabletLeaveProximity;
    if (!proximity && !realWindow) {
        return false;
    }
    auto *tablet = static_cast<QTabletEvent *>(event);
    const QString tool = tablet->pointerType() == QPointingDevice::PointerType::Eraser ? QStringLiteral("eraser") : QStringLiteral("pen");
    const QPointF pos = tablet->globalPosition();
    // the buttons of a pen that has just left are stale
    const int buttons = type == QEvent::TabletLeaveProximity ? 0 : int(tablet->buttons());
    if (qEnvironmentVariableIsSet("OVERDRIVE_PEN_DEBUG") && (type != QEvent::TabletMove || buttons != 0)) {
        qInfo() << "pen" << kind << tool << pos << "pressure" << tablet->pressure() << "button" << tablet->button() << "buttons" << tablet->buttons();
    }
    Q_EMIT penEvent(kind, tool, pos.x(), pos.y(), tablet->pressure(), tablet->xTilt(), tablet->yTilt(), tablet->rotation(), buttons);
    return false;
}
