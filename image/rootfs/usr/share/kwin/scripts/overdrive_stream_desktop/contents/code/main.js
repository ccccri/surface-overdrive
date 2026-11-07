// SPDX-License-Identifier: MIT
// Surface Overdrive: Moonlight on a virtual desktop of its own.
//
// When Moonlight opens, a desktop "Moonlight" is added next to the current one and Moonlight goes there: a three-finger
// swipe sideways on the touch screen (or up, for the overview) takes back to the Surface's own desktop and another swipe
// back to the stream, which keeps running. When Moonlight closes, the desktop is removed and, if it was the one shown,
// the desktop it came from comes back.

const NAME = "Moonlight";
let home = null;    // the desktop that was current when Moonlight opened

function isMoonlight(w) {
    return !!w && w.normalWindow && (String(w.desktopFileName).toLowerCase().indexOf("moonlight") >= 0 ||
                                     String(w.resourceClass).toLowerCase().indexOf("moonlight") >= 0);
}

function streamDesktop() {
    return workspace.desktops.find(d => d.name === NAME) || null;
}

function place(w) {
    if (!isMoonlight(w))
        return;
    let desk = streamDesktop();
    if (!desk) {
        home = workspace.currentDesktop;
        workspace.createDesktop(workspace.desktops.indexOf(home) + 1, NAME);
        desk = streamDesktop();
        if (!desk)
            return;
    }
    w.desktops = [desk];
    workspace.currentDesktop = desk;
    workspace.activeWindow = w;
}

workspace.windowAdded.connect(place);

workspace.windowRemoved.connect(w => {
    if (!isMoonlight(w))
        return;
    const desk = streamDesktop();
    if (!desk || workspace.windowList().some(o => o !== w && isMoonlight(o)))
        return;
    if (workspace.currentDesktop === desk) {
        const back = home && workspace.desktops.indexOf(home) >= 0 ? home : workspace.desktops[0];
        if (back !== desk)
            workspace.currentDesktop = back;
    }
    // KWin moves the windows left on it to a neighbour.
    workspace.removeDesktop(desk);
    home = null;
});

// Moonlight already open when the script starts (login, or the script turned on).
workspace.windowList().forEach(place);
