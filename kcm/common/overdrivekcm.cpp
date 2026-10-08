// SPDX-License-Identifier: MIT
#include "overdrivekcm.h"

#include "nfcmonitor.h"
#include "penmonitor.h"
#include "preview.h"

#include <KPluginMetaData>
#include <KQuickConfigModuleLoader>
#include <QProcess>
#include <QQmlEngine>
#include <QQuickItem>
#include <mutex>

static const QString s_ctl = QStringLiteral("/usr/bin/overdrivectl");

OverdriveKCM::OverdriveKCM(QObject *parent, const KPluginMetaData &data, const QVariantList &args)
    : KQuickConfigModule(parent, data)
{
    for (const QVariant &arg : args) {
        if (arg.typeId() == QMetaType::QString && !arg.toString().isEmpty()) {
            m_startTab = arg.toString().toLower();
            break;
        }
    }
    static std::once_flag registered;
    std::call_once(registered, []() {
        qmlRegisterType<PreviewItem>("org.surfaceoverdrive.kcm", 1, 0, "PreviewItem");
        qmlRegisterType<PenMonitor>("org.surfaceoverdrive.kcm", 1, 0, "PenMonitor");
        qmlRegisterType<NfcMonitor>("org.surfaceoverdrive.kcm", 1, 0, "NfcMonitor");
    });
    // every setting of ours applies at once and has its own reset: no Defaults / Reset / Apply row
    setButtons(NoAdditionalButton);
    refresh();
}

// Where the image keeps the Plasma pages that ours replace in the sidebar (see the Containerfile), then where Plasma installs them.
static const QStringList s_stockDirs = {QStringLiteral("plasma/kcms/overdrive-stock"), QStringLiteral("plasma/kcms/systemsettings"), QStringLiteral("plasma/kcms/kinfocenter"), QStringLiteral("plasma/kcms")};

void OverdriveKCM::loadStock(const QString &pluginId)
{
    if (m_stock || !m_stockError.isEmpty()) {
        return;
    }
    KPluginMetaData meta;
    for (const QString &dir : s_stockDirs) {
        meta = KPluginMetaData::findPluginById(dir, pluginId);
        if (meta.isValid()) {
            break;
        }
    }
    if (!meta.isValid()) {
        m_stockError = QStringLiteral("The Plasma page %1 was not found.").arg(pluginId);
        Q_EMIT stockChanged();
        return;
    }
    const auto result = KQuickConfigModuleLoader::loadModule(meta, this, {}, engine());
    if (!result) {
        m_stockError = result.errorString;
        Q_EMIT stockChanged();
        return;
    }
    m_stock = result.plugin;
    m_stockPage = m_stock->mainUi();
    if (!m_stockPage) {
        m_stockError = m_stock->errorString();
        Q_EMIT stockChanged();
        return;
    }
    showStockButtons(m_stockButtons);
    connect(m_stock, &KAbstractConfigModule::buttonsChanged, this, [this]() {
        showStockButtons(m_stockButtons);
    });
    connect(m_stock, &KAbstractConfigModule::needsSaveChanged, this, [this]() {
        setNeedsSave(m_stock->needsSave());
    });
    connect(m_stock, &KAbstractConfigModule::representsDefaultsChanged, this, [this]() {
        setRepresentsDefaults(m_stock->representsDefaults());
    });
    connect(m_stock, &KAbstractConfigModule::authActionNameChanged, this, [this]() {
        setAuthActionName(m_stock->authActionName());
    });
    connect(m_stock, &KQuickConfigModule::pagePushed, this, [this](QQuickItem *page) {
        push(page);
    });
    connect(m_stock, &KQuickConfigModule::pageRemoved, this, [this]() {
        if (depth() > 1) {
            pop();
        }
    });
    connect(this, &KQuickConfigModule::currentIndexChanged, m_stock, [this](int index) {
        m_stock->setCurrentIndex(index);
    });
    m_stock->load();
    Q_EMIT stockChanged();
}

void OverdriveKCM::showStockButtons(bool show)
{
    m_stockButtons = show;
    setButtons(show && m_stock ? m_stock->buttons() : Buttons(NoAdditionalButton));
}

QQuickItem *OverdriveKCM::stockPage() const
{
    return m_stockPage;
}

QString OverdriveKCM::startTab() const
{
    return m_startTab;
}

QString OverdriveKCM::stockError() const
{
    return m_stockError;
}

void OverdriveKCM::load()
{
    if (m_stock) {
        m_stock->load();
    }
}

void OverdriveKCM::save()
{
    if (m_stock) {
        m_stock->save();
    }
}

void OverdriveKCM::defaults()
{
    if (m_stock) {
        m_stock->defaults();
    }
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
