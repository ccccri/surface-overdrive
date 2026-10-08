// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// "Sound and EQ": the Sound page of Plasma with the settings of this project inside it. The page of Plasma is a column: a heading
// and the list of playback devices, a heading and the list of recording devices, then the streams. Our speaker settings go right
// under the first list and our microphone settings right under the second; if the page is ever built differently they stay at
// its end, where StockMerged puts them.
//
// The row of the built-in device has a "Profile" selector that chooses between layouts of the sound card (stereo, HDMI, off...).
// On this tablet only one of them is of use and the others make the speakers vanish, so in the rows of the built-in output and
// microphone that selector is replaced by ours, which lists the sound profiles (the equalizer presets). Rows of other devices
// are left as they are. If the row is ever built differently, the selector of Plasma stays and ours shows next to the equalizer.
StockMerged {
    id: page
    stock: "kcm_pulseaudio"

    readonly property string card: "pci-0000_00_1f.3"
    property var lists: []

    onMergedInto: column => {
        const found = []
        for (let i = 0; i < column.children.length; i++) if (String(column.children[i]).indexOf("ListView") >= 0) found.push(column.children[i])
        if (found.length < 2) return
        // each one right after its list; the message last, so that it ends up first, above the speaker settings
        if (!kcm.placeAfter(tuning.micPart, found[1])) return
        kcm.placeAfter(tuning.speakerPart, found[0])
        kcm.placeAfter(tuning.messagePart, found[0])
        lists = [found[0], found[1]]
    }

    // the rows are made again whenever a device comes or goes: look after them while the page shows
    Timer { interval: 700; repeat: true; running: page.visible && page.lists.length === 2; triggeredOnStart: true; onTriggered: page.dressRows() }
    function dressRows() {
        try {
            tuning.eqProfilesInRow = dress(lists[0], "alsa_output." + card, eqBox)
            tuning.micProfilesInRow = dress(lists[1], "alsa_input." + card, micBox)
        } catch (e) {
            console.warn("Surface Control: could not put the sound profiles into the device rows:", e)
            tuning.eqProfilesInRow = false
            tuning.micProfilesInRow = false
        }
    }
    // Finds the row of the built-in device in a list, and in it the "Profile:" label with the selector after it.
    function dress(list, namePrefix, component) {
        const rows = list.contentItem ? list.contentItem.children : []
        for (let i = 0; i < rows.length; i++) {
            const row = rows[i]
            if (!row.pulseObject || String(row.pulseObject.name).indexOf(namePrefix) !== 0) continue
            const line = row.children.length > 0 ? row.children[0] : null
            if (!line) continue
            let ours = null, stock = null
            for (let k = 0; k < line.children.length; k++) {
                const c = line.children[k]
                if (c.objectName === "overdriveProfiles") ours = c
                else if (c.currentText !== undefined && c.model !== undefined && k > 0 && /profile/i.test(String(line.children[k - 1].text || ""))) stock = c
            }
            if (ours) return true
            if (!stock) return false
            const box = component.createObject(line)
            if (!box || !kcm.placeAfter(box, stock)) return false
            // out of sight but not hidden: the "Profile:" label in front of it shows only while this selector counts as visible
            stock.Layout.maximumWidth = 0
            stock.Layout.minimumWidth = 0
            stock.opacity = 0
            stock.enabled = false
            stock.activeFocusOnTab = false
            return true
        }
        return false
    }
    Component {
        id: eqBox
        ProfileBox {
            objectName: "overdriveProfiles"
            presets: tuning.eqPresets; current: tuning.eqCurrent
            onChosen: name => tuning.applyEqPreset(name)
        }
    }
    Component {
        id: micBox
        ProfileBox {
            objectName: "overdriveProfiles"
            enabled: tuning.d.mic.available
            presets: tuning.micPresets; current: tuning.micCurrent
            onChosen: name => tuning.applyMicPreset(name)
        }
    }

    Tuning { id: tuning }
}
