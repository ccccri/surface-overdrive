// SPDX-License-Identifier: MIT
#pragma once

#include <KQuickConfigModule>

class QProcess;

/**
 * The shared back end of every page in the Surface Control group of System Settings.
 *
 * It does not do any work itself: it runs `overdrivectl` (which reads the system, or asks polkit for the administrator password when a
 * setting changes) and hands the result to the QML page.
 */
class OverdriveKCM : public KQuickConfigModule
{
    Q_OBJECT
    Q_PROPERTY(QString statusJson READ statusJson NOTIFY statusChanged)
    Q_PROPERTY(bool busy READ busy NOTIFY busyChanged)

public:
    OverdriveKCM(QObject *parent, const KPluginMetaData &data);

    QString statusJson() const;
    bool busy() const;

    /** Read the health of every fix again. */
    Q_INVOKABLE void refresh();
    /** Change a setting, for example ("volume-hold", "off"), then read the state again. */
    Q_INVOKABLE void changeSetting(const QString &name, const QString &value);

Q_SIGNALS:
    void statusChanged();
    void busyChanged();
    void changeFinished(bool ok, const QString &message);

private:
    void setBusy(bool busy);

    QString m_statusJson;
    bool m_busy = false;
};
