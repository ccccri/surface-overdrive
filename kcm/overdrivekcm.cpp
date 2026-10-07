// SPDX-License-Identifier: MIT
#include "overdrivekcm.h"

#include <KPluginFactory>

#include <QProcess>

K_PLUGIN_CLASS_WITH_JSON(OverdriveKCM, "kcm_overdrive.json")

static const QString s_ctl = QStringLiteral("/usr/bin/overdrivectl");

OverdriveKCM::OverdriveKCM(QObject *parent, const KPluginMetaData &data)
    : KQuickConfigModule(parent, data)
{
    refresh();
}

QString OverdriveKCM::statusJson() const
{
    return m_statusJson;
}

bool OverdriveKCM::busy() const
{
    return m_busy;
}

void OverdriveKCM::setBusy(bool busy)
{
    if (m_busy != busy) {
        m_busy = busy;
        Q_EMIT busyChanged();
    }
}

void OverdriveKCM::refresh()
{
    auto *process = new QProcess(this);
    setBusy(true);
    connect(process, &QProcess::finished, this, [this, process]() {
        // "overdrivectl status" exits with 1 when something is red: the JSON on stdout is valid either way
        m_statusJson = QString::fromUtf8(process->readAllStandardOutput());
        process->deleteLater();
        setBusy(false);
        Q_EMIT statusChanged();
    });
    connect(process, &QProcess::errorOccurred, this, [this, process](QProcess::ProcessError) {
        process->deleteLater();
        setBusy(false);
    });
    process->start(s_ctl, {QStringLiteral("status"), QStringLiteral("--json")});
}

void OverdriveKCM::changeSetting(const QString &name, const QString &value)
{
    auto *process = new QProcess(this);
    setBusy(true);
    connect(process, &QProcess::finished, this, [this, process](int code, QProcess::ExitStatus) {
        const QString message = QString::fromUtf8(process->readAllStandardError()).trimmed();
        process->deleteLater();
        setBusy(false);
        Q_EMIT changeFinished(code == 0, message);
        refresh();
    });
    process->start(s_ctl, {name, value});
}

#include "overdrivekcm.moc"
