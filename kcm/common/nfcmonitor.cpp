// SPDX-License-Identifier: MIT
#include "nfcmonitor.h"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QLocalSocket>

#include <unistd.h>

namespace
{
const QString kSocket = QStringLiteral("/run/overdrive-nfc/events.sock");

QString pidFilePath()
{
    QString runtime = qEnvironmentVariable("XDG_RUNTIME_DIR");
    if (runtime.isEmpty()) {
        runtime = QStringLiteral("/run/user/%1").arg(getuid());
    }
    return QDir(runtime).filePath(QStringLiteral("overdrive-nfc-window"));
}
}

NfcMonitor::NfcMonitor(QObject *parent)
    : QObject(parent)
{
    m_retry.setInterval(3000);
    connect(&m_retry, &QTimer::timeout, this, &NfcMonitor::connectToDaemon);
}

NfcMonitor::~NfcMonitor()
{
    setActive(false);
}

bool NfcMonitor::active() const
{
    return m_active;
}

bool NfcMonitor::connected() const
{
    return m_socket && m_socket->state() == QLocalSocket::ConnectedState;
}

void NfcMonitor::setActive(bool active)
{
    if (m_active == active) {
        return;
    }
    m_active = active;
    writePidFile(active);
    if (active) {
        connectToDaemon();
        m_retry.start();
    } else {
        m_retry.stop();
        if (m_socket) {
            m_socket->disconnect(this);
            m_socket->abort();
            m_socket->deleteLater();
            m_socket = nullptr;
            Q_EMIT connectedChanged();
        }
    }
    Q_EMIT activeChanged();
}

void NfcMonitor::writePidFile(bool on)
{
    QFile f(pidFilePath());
    if (on) {
        if (f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
            f.write(QByteArray::number(QCoreApplication::applicationPid()));
        }
    } else {
        f.remove();
    }
}

void NfcMonitor::connectToDaemon()
{
    if (connected() || (m_socket && m_socket->state() == QLocalSocket::ConnectingState)) {
        return;
    }
    if (m_socket) {
        m_socket->deleteLater();
    }
    m_socket = new QLocalSocket(this);
    connect(m_socket, &QLocalSocket::readyRead, this, &NfcMonitor::onReadyRead);
    connect(m_socket, &QLocalSocket::connected, this, &NfcMonitor::connectedChanged);
    connect(m_socket, &QLocalSocket::disconnected, this, &NfcMonitor::connectedChanged);
    m_buffer.clear();
    m_socket->connectToServer(kSocket);
}

void NfcMonitor::onReadyRead()
{
    m_buffer += m_socket->readAll();
    int nl;
    while ((nl = m_buffer.indexOf('\n')) >= 0) {
        const QByteArray line = m_buffer.left(nl);
        m_buffer.remove(0, nl + 1);
        if (!line.trimmed().isEmpty()) {
            Q_EMIT tag(QString::fromUtf8(line));
        }
    }
}
