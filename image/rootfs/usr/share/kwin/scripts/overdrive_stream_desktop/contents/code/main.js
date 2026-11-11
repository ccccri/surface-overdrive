// SPDX-License-Identifier: MIT
// Surface Overdrive: Moonlight on a virtual desktop of its own, one Moonlight at a time.
//
// When Moonlight opens, a desktop "Moonlight" is added next to the current one and Moonlight goes there: a three-finger
// swipe sideways on the touch screen (or up, for the overview) takes back to the Surface's own desktop and another swipe
// back to the stream, which keeps running. When Moonlight closes, the desktop is removed at once and, if it was the one
// shown, the desktop it came from comes back. The desktop is known by its id, not its name: a desktop of the user's
// called the same is never touched.
//
// Moonlight opened again from the menu while a stream ran on that desktop was a second Moonlight: quitting the app from it
// cut the first one's stream ("Connection terminated", error -1) and left two windows. Now the newest Moonlight stays and
// the one before is closed: its stream ends as when its window is closed (the app keeps running on the PC, the new
// Moonlight resumes or quits it).

const NAME = "Moonlight";
let home = null;          // the desktop that was current when Moonlight opened
let deskId = null;        // the id of the desktop this script made
let newest = 0;           // the pid of the Moonlight that stays
const seen = new Set();   // pids of every Moonlight seen

// When a stream ends, its full-screen window closes a moment before Moonlight's own window comes back: then the desktop
// waits up to 3 s for it (removing and adding it again at once lost the user's last desktop once). When Moonlight's own
// window closes (the app quits), the desktop goes at once.
const removal = new QTimer();
removal.singleShot = true;
removal.interval = 3000;

function isMoonlight(w) {
    return !!w && w.normalWindow && (String(w.desktopFileName).toLowerCase().indexOf("moonlight") >= 0 ||
                                     String(w.resourceClass).toLowerCase().indexOf("moonlight") >= 0);
}

function streamDesktop() {
    return deskId ? workspace.desktops.find(d => d.id === deskId) || null : null;
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
        const at = workspace.desktops.indexOf(home) + 1;
        workspace.createDesktop(at, NAME);
        desk = workspace.desktops[at];
        if (!desk || desk.name !== NAME)
            return;
        deskId = desk.id;
    }
    w.desktops = [desk];
    workspace.currentDesktop = desk;
    workspace.activeWindow = w;
}

workspace.windowAdded.connect(place);

workspace.windowRemoved.connect(w => {
    if (!isMoonlight(w) || !streamDesktop() || anyMoonlight(w))
        return;
    if (w.fullScreen)
        removal.start();
    else
        removeDesktop(w);
});

function removeDesktop(gone) {
    removal.stop();
    const desk = streamDesktop();
    if (!desk || anyMoonlight(gone))
        return;
    if (workspace.currentDesktop === desk) {
        const back = home && workspace.desktops.indexOf(home) >= 0 ? home : workspace.desktops[0];
        if (back !== desk)
            workspace.currentDesktop = back;
    }
    // KWin moves the windows left on it to a neighbour.
    workspace.removeDesktop(desk);
    home = null;
    deskId = null;
}

removal.timeout.connect(() => removeDesktop(null));

// A "Moonlight" desktop left from before the script started (KWin restarted) is taken back when only Moonlight's windows
// are on it; then Moonlight already open goes there (login, or the script turned on).
const left = workspace.desktops.find(d => d.name === NAME &&
    !workspace.windowList().some(o => o.normalWindow && !isMoonlight(o) && o.desktops.indexOf(d) >= 0));
if (left)
    deskId = left.id;
workspace.windowList().forEach(place);
