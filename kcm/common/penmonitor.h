// SPDX-License-Identifier: MIT
#pragma once

#include <QObject>

/** Reports every pen event the application receives (position, pressure, tilt, buttons) to the pen test page. */
class PenMonitor : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool active READ active WRITE setActive NOTIFY activeChanged)

public:
    explicit PenMonitor(QObject *parent = nullptr);
    ~PenMonitor() override;

    bool active() const;
    void setActive(bool active);

    bool eventFilter(QObject *watched, QEvent *event) override;

Q_SIGNALS:
    void activeChanged();
    /** kind: "move", "press", "release", "enter" or "leave"; tool: "pen" or "eraser"; x and y are window coordinates. */
    void penEvent(const QString &kind, const QString &tool, qreal x, qreal y, qreal pressure, qreal xTilt, qreal yTilt, qreal rotation, int buttons);

private:
    bool m_active = false;
};
