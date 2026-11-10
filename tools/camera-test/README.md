# Camera test for web pages

`camera-test.html` tries every way a web page uses the Surface's cameras: listing them, getUserMedia with no camera and no
size, each camera at its default and at 640x480, 1280x720, 1280x960 and 1920x1080 (frames that reach a `<video>` per
second, and how bright the picture is), facingMode, MediaRecorder, and a WebRTC call to itself (encode, send, decode, as
video calls do). The result goes to `/result` after every step.

On the tablet:

    python3 serve.py <dir with camera-test.html> /tmp/cam.json &
    firefox --new-instance --profile <empty dir with user.js: media.navigator.permission.disabled true> --kiosk http://127.0.0.1:8765/camera-test.html
    flatpak run io.github.ungoogled_software.ungoogled_chromium --headless=new --user-data-dir=<empty dir> --password-store=basic \
        --use-fake-ui-for-media-stream --enable-features=WebRtcPipeWireCamera http://127.0.0.1:8765/camera-test.html

`--password-store=basic`: a new Chromium profile otherwise asks to open the KDE wallet.

Results (2026-11-10, evening light): Firefox 159 and Chromium 157 get both cameras at every size; the rear one gave no
frames after the front one until camera nodes were suspended at once (wireplumber 91-surface-overdrive-camera-suspend);
WebRTC 960x540 VP8 at 15 fps; facingMode is not known to either browser through PipeWire (OverconstrainedError for an
exact facingMode).
