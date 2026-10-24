// SPDX-License-Identifier: MIT
// Surface Overdrive: the password prompt (polkit) and the on-screen keyboard in tablet mode.
//
// The prompt takes the focus without a touch on its field, and KWin shows the keyboard only after a touch: with no hardware
// keyboard there was no way to type, short of opening the keyboard from the panel (which sent the prompt behind the window).
// In tablet mode the keyboard now opens with the prompt.

function isPrompt(w) {
    return !!w && (String(w.resourceClass).indexOf("polkit") >= 0 || String(w.desktopFileName).indexOf("polkit") >= 0);
}

workspace.windowAdded.connect(w => {
    if (!isPrompt(w))
        return;
    callDBus("org.kde.KWin", "/org/kde/KWin", "org.freedesktop.DBus.Properties", "Get", "org.kde.KWin.TabletModeManager", "tabletMode",
             tablet => {
        if (!tablet)
            return;
        // A moment later, once the prompt has the focus.
        const t = new QTimer();
        t.singleShot = true;
        t.timeout.connect(() => callDBus("org.kde.KWin", "/VirtualKeyboard", "org.kde.kwin.VirtualKeyboard", "forceActivate"));
        t.start(300);
    });
});
