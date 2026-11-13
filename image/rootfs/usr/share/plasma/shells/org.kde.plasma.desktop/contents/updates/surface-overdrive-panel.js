// Surface Overdrive: the owner's panel on panels that already exist. Plasma runs every script here once per user (it keeps
// the names it ran in plasmashellrc, [Updates]). The default panel template of the image (ci/patch_plasma_defaults.py)
// gives a new panel these settings, but the first login of a fresh install happens on stock Kinoite, before the switch to
// the image, and that panel kept Fedora's: always visible, opaque, not floating, with the virtual desktop pager.
panels().forEach(function (panel) {
    panel.hiding = "dodgewindows";      // Visibility: Dodge Windows
    panel.opacity = "translucent";      // Opacity: Translucent
    panel.floating = true;              // Floating: Panel and applets
    panel.widgets("org.kde.plasma.pager").forEach(function (pager) {
        pager.remove();
    });
});
