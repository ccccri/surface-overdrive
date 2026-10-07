// SPDX-License-Identifier: MIT
#include "penmonitor.h"

#include <QCoreApplication>
#include <QTabletEvent>

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
    QString kind;
    switch (event->type()) {
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
        return QObject::eventFilter(watched, event);
    }
    auto *tablet = static_cast<QTabletEvent *>(event);
    const QString tool = tablet->pointerType() == QPointingDevice::PointerType::Eraser ? QStringLiteral("eraser") : QStringLiteral("pen");
    const QPointF pos = tablet->position();
    Q_EMIT penEvent(kind, tool, pos.x(), pos.y(), tablet->pressure(), tablet->xTilt(), tablet->yTilt(), tablet->rotation(), int(tablet->buttons()));
    return false;
}
