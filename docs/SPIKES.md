# Spikes: what to verify on the tablet before writing code

Each spike has a question, a method, a success criterion and what changes in the architecture depending on the result.
They need access to the Surface (SSH or a local terminal) and its updated installation.

## S1: does NFC work without a kernel patch?
- **Question**: can the stock `nxp-nci_i2c` driver bind to the ACPI device `NXP3001:00` without building anything?
- **Method**: see whether the i2c bus exposes `driver_override` for the device; try binding the stock driver; otherwise inspect `/sys/bus/i2c/devices/i2c-NXP3001:00`.
  Measure how often NACKed reads show up without the retry patch.
- **Success**: tags read with the stock driver and a latency close to the old repository's.
- **If yes**: NFC leaves the set of modules to build (only camera and volume remain). **If no**: a signed module built in CI, with the retry patch sent upstream.

## S2: which kernel patches are still needed on stock 7.2.x?
- **Question**: after recent releases, which of the 9 driver patches are still necessary?
- **Method**: for each one, read the source of the Fedora kernel in use and try the behaviour with the stock module (`ov8865`: stale mode, pixel rate, gain, 800x600; `ov5693`: 30 fps; `intel_hid`).
- **Success**: a minimal list of patches with a reason and a measurement.
- **Outcome**: every unneeded patch leaves the project.

## S3: marginal value of each libcamera patch
- **Question**: which of the 12 patches really change image quality, and by how much?
- **Method**: rebuild libcamera adding one patch at a time, using the old repository's measurement tools (AF sharpness, luminance stability, crashes in the stress test).
- **Success**: a table patch -> measured effect -> tier (1, 2, 3).

## S4: own calibration
- **Question**: from our own measurements, do we get lens shading and black level at least as good as the Microsoft tables?
- **Method**: capture RAW from the CIO2 (white field and covered lens), estimate the grids, apply them and measure luminance and R/G and B/G ratios at the centre and edges. Private comparison with the old tuning.
- **Success**: centre and edge deviation equal to or lower than the old repository (luminance: edge 1.00 of centre within 3%; R/G and B/G within 2%).
- **Outcome**: if it is not enough we look for a better method; the Microsoft tables stay out regardless.

## S5: audio
- **Question**: can the low volume and the over-sensitive microphone be solved at the ALSA/UCM/WirePlumber level, or is the filter-chain needed?
- **Method**: inspect `amixer contents`, the ALSA profile in use and the codec limits; try WirePlumber rules on the mixer controls.
- **Success**: audible volume without distortion and a sensible microphone gain without an extra virtual device.

## S6: bridge between the KCM and `overdrived`
- **Question**: what is the minimum way to make a System Settings page talk to a D-Bus service?
- **Method**: try a minimal KCM with a C++ plugin and check what pure QML allows. Also check how to make an entry show up in System Settings.
- **Success**: a page visible in System Settings showing state read over D-Bus.

## Baseline

Before the tablet is wiped, a backup of the current camera configuration and a system snapshot exist outside the repository.
A reference capture of the same scene with the old stack is worth taking for S3 and S4, so that comparisons have a "before".
