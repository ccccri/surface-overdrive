// SPDX-License-Identifier: MIT
#pragma once

#include <QImage>
#include <QQuickPaintedItem>

class QProcess;
class QTimer;

/**
 * Live picture of a camera: a GStreamer pipeline reads the PipeWire camera node, scales it down and writes raw RGB frames to a pipe.
 * While it runs, other applications cannot use the camera.
 */
class PreviewItem : public QQuickPaintedItem
{
    Q_OBJECT
    Q_PROPERTY(bool running READ running NOTIFY runningChanged)
    Q_PROPERTY(QString error READ error NOTIFY errorChanged)
    Q_PROPERTY(bool hasFrame READ hasFrame NOTIFY runningChanged)

public:
    explicit PreviewItem(QQuickItem *parent = nullptr);
    ~PreviewItem() override;

    bool running() const;
    QString error() const;
    bool hasFrame() const;

    Q_INVOKABLE void start(const QString &node);
    Q_INVOKABLE void stop();

    void paint(QPainter *painter) override;

Q_SIGNALS:
    void runningChanged();
    void errorChanged();

private:
    void onReadyRead();
    void setError(const QString &error);

    QProcess *m_process = nullptr;
    QTimer *m_watchdog = nullptr;
    QByteArray m_buffer;
    QImage m_frame;
    QString m_error;
};
