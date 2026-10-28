// SPDX-License-Identifier: MIT
#pragma once

#include <KQuickConfigModule>
#include <QQuickItem>

#include <QHash>

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
    Q_PROPERTY(QQuickItem *stockPage READ stockPage NOTIFY stockChanged)
    Q_PROPERTY(QString stockError READ stockError NOTIFY stockChanged)
    /** The tab to open first, from the command line: `systemsettings kcm_overdrive_sound --args tuning`. Empty when none was asked. */
    Q_PROPERTY(QString startTab READ startTab CONSTANT)

public:
    OverdriveKCM(QObject *parent, const KPluginMetaData &data, const QVariantList &args);

    QString statusJson() const;
    bool busy() const;

    /** Read the health of every fix again. */
    Q_INVOKABLE void refresh();
    /** Change a setting, for example ("volume-hold", "off"), then read the state again. */
    Q_INVOKABLE void changeSetting(const QString &name, const QString &value);
    /** Run `overdrivectl <args>` without privileges; the answer (usually JSON) comes back through callFinished with the same tag. */
    Q_INVOKABLE void call(const QString &tag, const QStringList &args);
    /** The same, with input written to its standard input (for a secret, which must not appear in the arguments). */
    Q_INVOKABLE void callWithInput(const QString &tag, const QStringList &args, const QString &input);
    /**
     * Send one line to a long-running `overdrivectl <args>` (started on the first line, kept for the life of the page): for changes
     * made many times a second, such as a slider being dragged, which would cost a new process each. Each line it answers comes back
     * through callFinished with this tag; if it cannot run (or ends), callFinished says so with ok false.
     */
    Q_INVOKABLE void stream(const QString &tag, const QStringList &args, const QString &line);
    /**
     * Load a page that ships with Plasma (for example "kcm_pulseaudio") so that our page can show it in one of its tabs. Its page is then
     * in stockPage; its Apply/Defaults buttons, its unsaved state and the sub-pages it opens are passed on to System Settings.
     */
    Q_INVOKABLE void loadStock(const QString &pluginId);
    /**
     * Put an item of ours right after an item of a Plasma page, in the same column: that is how our settings of the speakers come
     * right under the list of playback devices and not at the end of the page. False when the two cannot be put together.
     */
    Q_INVOKABLE bool placeAfter(QQuickItem *item, QQuickItem *sibling);
    /** Show the Apply/Defaults row of the Plasma page only while its tab is the one in front. */
    Q_INVOKABLE void showStockButtons(bool show);

    QQuickItem *stockPage() const;
    QString stockError() const;
    QString startTab() const;

    void load() override;
    void save() override;
    void defaults() override;

Q_SIGNALS:
    void statusChanged();
    void busyChanged();
    void stockChanged();
    void changeFinished(bool ok, const QString &message);
    void callFinished(const QString &tag, bool ok, const QString &output, const QString &error);

private:
    void setBusy(bool busy);

    QString m_statusJson;
    bool m_busy = false;
    KQuickConfigModule *m_stock = nullptr;
    QQuickItem *m_stockPage = nullptr;
    QString m_stockError;
    QString m_startTab;
    bool m_stockButtons = true;
    QHash<QString, QProcess *> m_streams;
};
