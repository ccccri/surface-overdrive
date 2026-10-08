// SPDX-License-Identifier: MIT
import QtQuick
import org.kde.kirigami as Kirigami

// "Sound and EQ": the Sound page of Plasma with the settings of this project inside it. The page of Plasma is a column: a heading
// and the list of playback devices, a heading and the list of recording devices, then the streams. Our speaker settings go right
// under the first list and our microphone settings right under the second; if the page is ever built differently they stay at
// its end, where StockMerged puts them.
StockMerged {
    id: page
    stock: "kcm_pulseaudio"

    onMergedInto: column => {
        const lists = []
        for (let i = 0; i < column.children.length; i++) if (String(column.children[i]).indexOf("ListView") >= 0) lists.push(column.children[i])
        if (lists.length < 2) return
        // each one right after its list; the message last, so that it ends up first, above the speaker settings
        if (!kcm.placeAfter(tuning.micPart, lists[1])) return
        kcm.placeAfter(tuning.speakerPart, lists[0])
        kcm.placeAfter(tuning.messagePart, lists[0])
    }

    Tuning { id: tuning }
}
