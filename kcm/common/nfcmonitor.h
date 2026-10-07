// SPDX-License-Identifier: MIT
#pragma once

#include <QObject>
#include <QTimer>

class QLocalSocket;

/**
 * Receives the tags read by overdrive-nfcd (one JSON line per tag on its unix socket) for the NFC page. While it is active it writes
 * its pid to $XDG_RUNTIME_DIR/overdrive-nfc-window, so that the desktop notifier does not show a notification for the same tag.
 */
class NfcMonitor : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool active READ active WRITE setActive NOTIFY activeChanged)
    Q_PROPERTY(bool connected READ connected NOTIFY connectedChanged)

public:
    explicit NfcMonitor(QObject *parent = nullptr);
    ~NfcMonitor() override;

    bool active() const;
    void setActive(bool active);
    bool connected() const;

Q_SIGNALS:
    void activeChanged();
    void connectedChanged();
    /** One tag, as the JSON the daemon sent. */
    void tag(const QString &json);

private:
    void connectToDaemon();
    void onReadyRead();
    void writePidFile(bool on);

    QLocalSocket *m_socket = nullptr;
    QTimer m_retry;
    QByteArray m_buffer;
    bool m_active = false;
};
