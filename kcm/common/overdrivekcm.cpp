// SPDX-License-Identifier: MIT
#include "overdrivekcm.h"

#include "nfcmonitor.h"
#include "penmonitor.h"
#include "preview.h"

#include <QProcess>
#include <QQmlEngine>
#include <mutex>

static const QString s_ctl = QStringLiteral("/usr/bin/overdrivectl");

OverdriveKCM::OverdriveKCM(QObject *parent, const KPluginMetaData &data)
    : KQuickConfigModule(parent, data)
{
    static std::once_flag registered;
    std::call_once(registered, []() {
        qmlRegisterType<PreviewItem>("org.surfaceoverdrive.kcm", 1, 0, "PreviewItem");
        qmlRegisterType<PenMonitor>("org.surfaceoverdrive.kcm", 1, 0, "PenMonitor");
        qmlRegisterType<NfcMonitor>("org.surfaceoverdrive.kcm", 1, 0, "NfcMonitor");
    });
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

void OverdriveKCM::call(const QString &tag, const QStringList &args)
{
    auto *process = new QProcess(this);
    connect(process, &QProcess::finished, this, [this, process, tag](int code, QProcess::ExitStatus status) {
        const QString out = QString::fromUtf8(process->readAllStandardOutput());
        const QString err = QString::fromUtf8(process->readAllStandardError()).trimmed();
        process->deleteLater();
        Q_EMIT callFinished(tag, code == 0 && status == QProcess::NormalExit, out, err);
    });
    connect(process, &QProcess::errorOccurred, this, [this, process, tag](QProcess::ProcessError error) {
        if (error == QProcess::FailedToStart) {
            process->deleteLater();
            Q_EMIT callFinished(tag, false, {}, QStringLiteral("Could not run overdrivectl"));
        }
    });
    process->start(s_ctl, args);
}
