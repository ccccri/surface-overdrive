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
| 10 | Plymouth scale 1, GRUB 3 s countdown | Plymouth done; GRUB `user.cfg` needs a first-boot step |
| 11 | Sensors: allow the settings page to raise the accelerometer/gyro rate | not yet (needed by the sensors page) |
| 12 | Health monitor with explanations, repair and an update guard | not yet |
| 13 | Settings page in System Settings: Overview | not yet |
| 14 | Cameras page: live preview, live editor, per-camera presets, manual focus, rainbow | not yet |
| 15 | Audio page: volume, 10-band equaliser per output, microphone enhancer, tests | not yet |
| 16 | NFC page: tags shown in the window, reader test | not yet |
| 17 | Pen and touch page: pen test, Bluetooth pen battery, filter switch | not yet |
| 18 | Sensors and battery page: light, accelerometer/gyro 3D view, battery, about this tablet | not yet |
| 19 | Updates and log; export/import of presets | not yet |
| 20 | Installer wizard | replaced by the bootstrap (not yet) |
| 21 | Own colour calibration (lens shading) | not yet |
| 22 | CI that rebuilds the image daily | not yet |
