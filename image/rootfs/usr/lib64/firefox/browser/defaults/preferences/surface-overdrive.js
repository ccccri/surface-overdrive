// Surface Overdrive (loaded after Firefox's own defaults and Fedora's): extensions of the image (/usr/share/mozilla/extensions, the system scope) are on without asking:
// the Google Voice Search button beside the address bar. Other sideloaded extensions still ask first.
pref("extensions.enabledScopes", 15);
pref("extensions.autoDisableScopes", 7);
// The translation offer no longer opens by itself (it covered Google's voice search); its button stays in the address bar.
pref("browser.translations.automaticallyPopup", false);
// Firefox's default permissions plus the microphone for google.com (the voice search button), made at image build
// time (Containerfile). Default permissions hold in private windows too, which the Permissions policy does not.
pref("permissions.manager.defaultsUrl", "file:///usr/lib64/firefox/browser/defaults/surface-overdrive-permissions");
// A page asking for a camera without a size (getUserMedia({video: true})) got the camera's first size, the picture size of
// the Cameras page: 2560x1920 at 8 frames a second on the front camera (measured in Firefox 159, tools/camera-test). 1280x960
// is the sensor's 4:3 at about 25 fps; a page that asks for a size still gets it.
pref("media.navigator.video.default_width", 1280);
pref("media.navigator.video.default_height", 960);
