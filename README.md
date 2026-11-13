# Surface Overdrive

Hardware fixes, a system image and System Settings pages for a **Surface Go (1824)** running **Fedora Kinoite** with Secure
Boot on. A personal project: it is not meant for other models or other users.

**Status**: in daily use on the owner's tablet. CI builds the image for Fedora 45 every day and on every push
(`ghcr.io/ccccri/surface-overdrive:45`); the tablet gets it as a normal Kinoite update.

## What it does

- Kernel modules patched and signed for Secure Boot: both cameras, NFC, volume buttons.
- libcamera rebuilt with our patch series and our own calibration (no Microsoft data): exposure, focus, colour, noise.
- A camera app with hardware video encoding, a Cameras page, NFC, sound (boost, equalizer, microphone noise suppression),
  pen, sensors, PIN or pattern unlock, a health monitor (`overdrivectl status`) and update pages in System Settings.

The full list, with what is still open: [`docs/FEATURES.md`](docs/FEATURES.md). What changed and why: [`docs/CHANGELOG.md`](docs/CHANGELOG.md).

## Install

On a freshly installed Fedora Kinoite, as the normal user:

    curl -L ccccri.github.io | bash

`bootstrap.sh` checks the machine and starts the installer (`installer/`): one administrator password in a window, the
module key queued for enrolment only when it is not enrolled yet (its one-time password in a window too), and the switch
to the image, followed on screen by a little show and the numbers (percentage, layer, speed, time left). After one reboot
(the blue MOK screen only the first time on a machine) the tablet runs Surface Overdrive. `python3 installer/install.py
--demo` plays the show without installing anything.

## Documents

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): how it is built (the first section) and the original design.
- [`docs/UPSTREAM-WORKAROUNDS.md`](docs/UPSTREAM-WORKAROUNDS.md): patches for other projects' bugs, to remove once they are fixed.
- [`docs/TEST-RESULTS.md`](docs/TEST-RESULTS.md), [`docs/SPIKE-RESULTS.md`](docs/SPIKE-RESULTS.md): measurements on the tablet.
- [`tools/camera-test`](tools/camera-test): how web pages get the cameras, checked in Firefox and Chromium.
- [`docs/voice-search-amo.md`](docs/voice-search-amo.md): the Firefox voice search extension and its store listing.

Its predecessor, with the original patches and the write-up of root causes, is the `surface-go-kinoite` repository.

## License

MIT for original code. Patches derived from other projects keep their license (libcamera LGPL-2.1+, kernel GPL-2.0).
