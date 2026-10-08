// SPDX-License-Identifier: MIT
import QtQuick
import org.kde.kirigami as Kirigami

// "Sound and EQ": the Sound page of Plasma (devices and volumes) with our tuning (boost, equaliser, microphone, volume buttons)
// after it, as one page.
StockMerged {
    stock: "kcm_pulseaudio"
    Tuning { }
}
