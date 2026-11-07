// SPDX-License-Identifier: MIT
// Surface Overdrive: Moonlight on a virtual desktop of its own, one Moonlight at a time.
//
// When Moonlight opens, a desktop "Moonlight" is added next to the current one and Moonlight goes there: a three-finger
// swipe sideways on the touch screen (or up, for the overview) takes back to the Surface's own desktop and another swipe
// back to the stream, which keeps running. When Moonlight closes, the desktop is removed and, if it was the one shown,
// the desktop it came from comes back.
//
// Moonlight opened again from the menu while a stream ran on that desktop was a second Moonlight: quitting the app from it
// cut the first one's stream ("Connection terminated", error -1) and left two windows. Now the newest Moonlight stays and
// the one before is closed: its stream ends as when its window is closed (the app keeps running on the PC, the new
// Moonlight resumes or quits it).

const NAME = "Moonlight";
let home = null;          // the desktop that was current when Moonlight opened
let newest = 0;           // the pid of the Moonlight that stays
const seen = new Set();   // pids of every Moonlight seen

// The desktop goes 3 s after the last Moonlight window: between its own window and the stream's there is a moment with
// none, and removing and adding it again at once lost the user's last desktop once.
const removal = new QTimer();
removal.singleShot = true;
removal.interval = 3000;

function isMoonlight(w) {
    return !!w && w.normalWindow && (String(w.desktopFileName).toLowerCase().indexOf("moonlight") >= 0 ||
                                     String(w.resourceClass).toLowerCase().indexOf("moonlight") >= 0);
}

function streamDesktop() {
    return workspace.desktops.find(d => d.name === NAME) || null;
}

function anyMoonlight(except) {
    return workspace.windowList().some(o => o !== except && isMoonlight(o));
}

function place(w) {
    if (!isMoonlight(w))
        return;
    removal.stop();
    if (w.pid !== newest) {
        if (seen.has(w.pid)) {
            // a window of a Moonlight that was replaced (its main window coming back once its stream ended)
            w.closeWindow();
            return;
        }
        seen.add(w.pid);
        newest = w.pid;
        workspace.windowList().filter(o => o !== w && isMoonlight(o) && o.pid !== w.pid).forEach(o => o.closeWindow());
    }
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
    if (isMoonlight(w) && streamDesktop() && !anyMoonlight(w))
        removal.start();
});

removal.timeout.connect(() => {
    const desk = streamDesktop();
    if (!desk || anyMoonlight(null))
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
