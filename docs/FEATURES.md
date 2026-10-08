# Features

What the previous project (`surface-go-kinoite`) did, and where each piece stands here. Anything about the keyboard cover (Type Cover) is out of scope: the tablet is used as a tablet.

| # | Feature | State |
|---|---|---|
| 1 | Patched kernel modules: cameras, NFC, volume buttons | **done**, built in CI-style stage, verified on the tablet |
| 2 | Patched libcamera (crash fixes, autofocus, exposure, black level, flicker, start-up behaviour) | **done**; colour (lens shading) waits for our own calibration |
| 3 | NFC reader daemon (`overdrive-nfcd`) | **done**, running from the image; reading a real tag still to be tried |
| 4 | NFC notifications (`overdrive-nfc-notify`) | **done** |
| 5 | Volume buttons: hold to repeat, with an on/off switch (`overdrivectl volume-hold`) | **done** |
| 6 | Pen: hide the fake 0% battery (HID-BPF), with a switch (`overdrivectl stylus-filter`) | **done** |
| 7 | Speakers: louder (software gain on a filter-chain sink, default sink) | **done**; the equaliser is not ported yet |
| 8 | Microphone: sane hardware level (+18 dB, boost off) | **done**; noise suppression and the enhancer are not ported yet |
| 9 | Plasma volume: up to 150%, 5% steps | **done** |
| 10 | Plymouth scale 1, GRUB 3 s countdown | **done**: boot-time service `overdrive-bootconfig` keeps a marked block in `/boot/grub2/user.cfg` |
| 11 | Sensors: udev rule lets the settings page raise the accelerometer/gyro rate | **done** (`61-overdrive-sensors.rules`) |
| 12 | Health monitor with explanations (`overdrivectl status`) and a desktop notification when a fix stops working (user timer `overdrive-health-watch`) | **done**; repair actions and the update guard are not yet |
| 13 | Our pages in System Settings, written to blend in with Plasma's (same tab bars, section headings, check boxes, scroll bars). Two pages of our own under Input & Output: "Cameras" and "NFC". Five Plasma pages are replaced by ours, which load the Plasma page and add our part to it: "Sound and EQ" (boost and equalizer right under the playback devices, microphone enhancement right under the recording devices), "Drawing Tablet" (Plasma's Display and Pen tabs plus a pen test next to the pen settings; Pad and the unsupported left-handed mode left out), "Power Management" (one line of battery figures at the bottom), "About this System" (firmware in the hardware list, light and motion sensors next to it) and "Software Update" ("Kernel Patches and Modules" first, Plasma's update settings under it) | **done**: C++ KCMs + QML, run `overdrivectl`; the Plasma plugins are moved to `plasma/kcms/overdrive-stock` in the image and loaded from there. Pages a Plasma page opens on top of itself take the whole view, as in Plasma |
| 14 | Cameras page: live preview, live editor, per-camera presets, manual focus, rainbow | **done** (`overdrivectl camera`, page "Cameras"); needs the user to judge the looks |
| 15 | Sound: speaker boost, 10-band equalizer per output (presets, reset, APO/AutoEQ import and export), limiter, left/right swap per output (on for the headphone jack), microphone enhancement (noise suppression, low cut, three bands, gain). All of it runs **inside the built-in devices** (PipeWire filter graphs loaded into the device nodes), so the device lists keep one entry per real device | **done** (`overdrivectl audio`, user service `overdrive-audio-route` loads the filters at login and after a sound server restart; own LADSPA plugin `ladspa/overdrive_denoise.c` on rnnoise). Measured through the speakers with the microphone; headphones not yet tried by the user |
| 16 | NFC page: tags shown in the page (live from the daemon), reader test | **done**; real tag not yet tried by the user |
| 17 | Pen page: pen test (pressure, tilt, buttons), Bluetooth pen battery, filter switch | **done**; the pen itself not yet tried by the user |
| 18 | Sensors (light, accelerometer/gyro bars, firmware) at the end of "About this System"; battery line (charge, power, health, cycles) above Plasma's Power Management page | **done** (2D bars, the old 3D model view was not ported) |
| 19 | Updates and log; export/import of presets | not yet |
| 20 | Installer wizard | replaced by `bootstrap.sh` (one command, one reboot, MOK enrolment); untested until the first CI image exists |
| 21 | Own colour calibration (lens shading) | not yet |
| 22 | CI that rebuilds the image daily | workflow written (`.github/workflows/build-image.yml`), waits for the push permission and the signing secrets |
