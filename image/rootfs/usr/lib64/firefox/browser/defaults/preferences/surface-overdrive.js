// Surface Overdrive (loaded after Firefox's own defaults and Fedora's): extensions of the image (/usr/share/mozilla/extensions, the system scope) are on without asking:
// the Google Voice Search button beside the address bar. Other sideloaded extensions still ask first.
pref("extensions.enabledScopes", 15);
pref("extensions.autoDisableScopes", 7);
// The translation offer no longer opens by itself (it covered Google's voice search); its button stays in the address bar.
pref("browser.translations.automaticallyPopup", false);
// Firefox's default permissions plus the microphone for google.com (the voice search button), made at image build
// time (Containerfile). Default permissions hold in private windows too, which the Permissions policy does not.
pref("permissions.manager.defaultsUrl", "file:///usr/lib64/firefox/browser/defaults/surface-overdrive-permissions");
