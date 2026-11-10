// SPDX-License-Identifier: MIT
// Surface Overdrive (PC companion): the active window between the Surface's screen (Virtual-surface, made by
// surface-screen-start) and the PC's monitor, without the mouse.
// - Meta+Shift+Down: to the Surface; Meta+Shift+Up: to the monitor (the Surface stands below it). KWin's own
//   Meta+Shift+Left/Right (next/previous screen) work too.
// - a swipe in from the right edge of the Surface (touch): to the other screen. In Extended Display the Surface's right
//   edge is an edge of the whole desktop, which KWin's touch edges need.
// Nothing happens without the Surface's screen.

const SURFACE = "Virtual-surface";

function surface() {
    return workspace.screens.find(s => s.name === SURFACE) || null;
}

function monitor() {
    return workspace.screens.find(s => s.name !== SURFACE) || null;
}

function movable(w) {
    return !!w && w.normalWindow && w.moveableAcrossScreens !== false && !w.specialWindow;
}

function sendTo(target) {
    const w = workspace.activeWindow;
    if (!target || !movable(w) || w.output === target)
        return;
    const wasMax = w.maximizeMode;
    workspace.sendClientToScreen(w, target);
    // a maximized or full-screen window fills its new screen (KWin does it), a normal one is kept inside it
    if (!wasMax && !w.fullScreen) {
        const a = workspace.clientArea(KWin.PlacementArea, target, workspace.currentDesktop);
        const g = w.frameGeometry;
        const width = Math.min(g.width, a.width), height = Math.min(g.height, a.height);
        w.frameGeometry = {
            x: Math.max(a.x, Math.min(g.x, a.x + a.width - width)),
            y: Math.max(a.y, Math.min(g.y, a.y + a.height - height)),
            width: width, height: height
        };
    }
    workspace.activeWindow = w;
}

registerShortcut("OverdriveWindowToSurface", "Move Window to the Surface", "Meta+Shift+Down", () => sendTo(surface()));
registerShortcut("OverdriveWindowToMonitor", "Move Window to the Monitor", "Meta+Shift+Up", () => sendTo(monitor()));
registerTouchScreenEdge(KWin.ElectricRight, () => {
    const s = surface();
    const w = workspace.activeWindow;
    if (!s || !w)
        return;
    sendTo(w.output === s ? monitor() : s);
});
