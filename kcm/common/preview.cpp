// SPDX-License-Identifier: MIT
#include "preview.h"

#include <QPainter>
#include <QProcess>
#include <QTimer>

namespace
{
constexpr int kWidth = 800;
constexpr int kHeight = 600;
constexpr int kFrameBytes = kWidth * kHeight * 3;
constexpr int kRetries = 6;          // one a second: the camera service takes up to a few seconds to restart
}

PreviewItem::PreviewItem(QQuickItem *parent)
    : QQuickPaintedItem(parent)
{
    m_watchdog = new QTimer(this);
    m_watchdog->setSingleShot(true);
    m_watchdog->setInterval(8000);
    m_retry = new QTimer(this);
    m_retry->setSingleShot(true);
    m_retry->setInterval(1000);
    connect(m_retry, &QTimer::timeout, this, [this]() {
        if (!m_node.isEmpty())
            launch();
    });
    connect(m_watchdog, &QTimer::timeout, this, [this]() {
        stop();
        setError(QStringLiteral("The camera did not deliver pictures (is another app using it?)"));
    });
}

PreviewItem::~PreviewItem()
{
    stop();
}

bool PreviewItem::running() const
{
    return m_process != nullptr || m_retry->isActive();
}

QString PreviewItem::error() const
{
    return m_error;
}

bool PreviewItem::hasFrame() const
{
    return m_process != nullptr && !m_frame.isNull();
}

void PreviewItem::setError(const QString &error)
{
    if (m_error != error) {
        m_error = error;
        Q_EMIT errorChanged();
    }
}

void PreviewItem::start(const QString &node)
{
    m_node = node;
    m_retries = 0;
    launch();
}

void PreviewItem::launch()
{
    stopProcess();
    setError({});
    m_process = new QProcess(this);
    m_process->setProgram(QStringLiteral("gst-launch-1.0"));
    m_process->setArguments({QStringLiteral("-q"),
                             QStringLiteral("pipewiresrc"),
                             QStringLiteral("target-object=") + m_node,
                             // PipeWire lets the camera write the next picture into a buffer a few frames after handing it out,
                             // whether or not we are done with it: copy each picture at once, or scaling a large one shows
                             // rectangles of two different frames. The queue drops pictures we are too slow for, so the preview
                             // shows the newest one instead of falling behind.
                             QStringLiteral("always-copy=true"),
                             QStringLiteral("!"),
                             QStringLiteral("queue"),
                             QStringLiteral("leaky=downstream"),
                             QStringLiteral("max-size-buffers=1"),
                             // scaled on the GPU (VA-API): in software the preview of the rear camera at 3200x2400 took
                             // 74% of a core, this takes 13%; only the small picture is converted to RGB here
                             QStringLiteral("!"),
                             QStringLiteral("vapostproc"),
                             QStringLiteral("!"),
                             QStringLiteral("video/x-raw,format=RGBA,width=%1,height=%2").arg(kWidth).arg(kHeight),
                             QStringLiteral("!"),
                             QStringLiteral("videoconvert"),
                             QStringLiteral("!"),
                             QStringLiteral("video/x-raw,format=RGB"),
                             QStringLiteral("!"),
                             QStringLiteral("fdsink"),
                             QStringLiteral("fd=1")});
    connect(m_process, &QProcess::readyReadStandardOutput, this, &PreviewItem::onReadyRead);
    connect(m_process, &QProcess::errorOccurred, this, [this](QProcess::ProcessError) {
        stop();
        setError(QStringLiteral("Could not start the camera preview (is GStreamer installed?)"));
    });
    connect(m_process, &QProcess::finished, this, [this](int, QProcess::ExitStatus) {
        if (!m_process)
            return;
        // Right after a change of size the camera service is still bringing the cameras back, and the preview finds no
        // camera and ends: try again a few times before saying so (it showed "stopped" and never came back).
        stopProcess();
        if (m_retries < kRetries) {
            m_retries++;
            m_retry->start();
            Q_EMIT runningChanged();
            return;
        }
        setError(QStringLiteral("The camera preview stopped"));
    });
    m_buffer.clear();
    m_process->start();
    m_watchdog->start();
    Q_EMIT runningChanged();
}

void PreviewItem::stop()
{
    m_retry->stop();
    m_node.clear();
    stopProcess();
}

void PreviewItem::stopProcess()
{
    m_watchdog->stop();
    if (m_process) {
        QProcess *p = m_process;
        m_process = nullptr;
        p->disconnect(this);
        p->terminate();
        if (!p->waitForFinished(1500)) {
            p->kill();
            p->waitForFinished(1000);
        }
        p->deleteLater();
    }
    m_buffer.clear();
    m_frame = QImage();
    update();
    Q_EMIT runningChanged();
}

void PreviewItem::onReadyRead()
{
    m_buffer += m_process->readAllStandardOutput();
    bool got = false;
    // keep only the newest complete frame
    while (m_buffer.size() >= kFrameBytes) {
        m_frame = QImage(reinterpret_cast<const uchar *>(m_buffer.constData()), kWidth, kHeight, kWidth * 3, QImage::Format_RGB888).copy();
        m_buffer.remove(0, kFrameBytes);
        got = true;
    }
    if (got) {
        m_retries = 0;
        m_watchdog->start();
        setError({});
        update();
        Q_EMIT runningChanged();
    }
}

void PreviewItem::paint(QPainter *painter)
{
    painter->fillRect(boundingRect(), Qt::black);
    if (!m_frame.isNull()) {
        painter->setRenderHint(QPainter::SmoothPixmapTransform);
        painter->drawImage(boundingRect(), m_frame);
    }
}
