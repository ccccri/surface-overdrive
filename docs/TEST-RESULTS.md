# Hardware test results

## Test 1 (2026-10-07): first image on the Surface Go, kernel modules only

Image `surface-overdrive:44` built locally (kernel `7.2.8-200.fc44`, five signed modules, Plymouth scale), transferred as an OCI archive,
`rpm-ostree rebase ostree-unverified-image:oci-archive:...`, MOK enrolment of the development key at the blue screen. One reboot.

| Check | Result |
|---|---|
| Boots into the new deployment | **ok** |
| MOK enrolment of the project key | **ok** |
| `ov8865`, `ov5693`, `nxp-nci`, `nxp-nci_i2c`, `intel_hid` loaded from `updates/`, flagged `(O)` | **ok** |
| NFC: `nfc0` appears, `nxp-nci_i2c` binds to `NXP3001:00` on its own (no helper service) | **ok** |
| Rear camera no longer green (stale-mode fix) | **ok** |
| Front camera | works, soft and with a pink cast (stock tuning, no lens shading, 640x480) |
| Volume buttons: tap = one step, hold = repeats | **ok** |
| Plymouth `DeviceScale=1` | **ok** |
| GRUB countdown | not shown: nothing installs `/boot/grub2/user.cfg` yet. Installed by hand afterwards, to confirm at the next boot |

### Exposure with the base tuning only (no code patches)
With the stock `uncalibrated.yaml` the rear camera exposed for a bright light and the rest of the frame went black (a phone torch in front of the lens
gave one white dot on black). Installing the 27-line tuning from the previous repository (`image/rootfs/usr/share/libcamera/ipa/ipu3/{ov5693,ov8865}.yaml`:
brightness target 0.30 and a lower constraint on the shadows) fixed the exposure of both cameras. What is left is the colour cast (lens shading), the
fixed 640x480 size, the missing autofocus work and the noise: those need the libcamera patches and our own calibration.

### Findings that shape the design
- **WirePlumber started before the graphical login finds no cameras** and does not retry (`Permission denied` on `/dev/media*`: the access ACLs only exist for the user with an active seat session).
  It happens when something opens a user manager early (an SSH login at boot). The health check must not call this a camera failure: it has to wait for a seat session, and the repair is a WirePlumber restart.
- The tablet logs in with a password (no autologin by choice), so tests type it through a virtual keyboard: `tools/dev/uinput_type.py` (root, `/dev/uinput`). Worked on the Plasma login screen.
- `rpm-ostree` cannot read the archive from the home directory: it has to be in `/var/tmp`.
- The deployment came from a different Kinoite composition than the installed one (the container image has `dnf5`, no `fedora-repos-ostree`); updates will come from our registry, not from Fedora's ostree remote.

## Test 2 (2026-10-07): libcamera rebuilt from Fedora's SRPM with the 12 patches

Image rebuilt with `libcamera-0.7.1-1.fc44.overdrive1` and `libcamera-ipa` replacing the stock packages (`ci/build_libcamera.sh`, `patches/libcamera/`), plus the base IPU3 tuning.
Rebase from a second OCI archive, one reboot, no MOK screen (key already enrolled), login typed through `tools/dev/uinput_type.py`.

| Check | Result |
|---|---|
| WirePlumber loads the system `libcamera` (no `LD_LIBRARY_PATH`, no `/usr/local`) | **ok** |
| Build: Fedora's spec plus 12 patches applies and compiles | **ok** (needed `elfutils-devel`, which Fedora's spec does not declare) |
| Rear camera | **ok**: 1536x1152 offered first, sharp, well exposed |
| Front camera | **ok**: 1152x864, sharp, well exposed |
| Colour | still a pink centre with green/blue edges: no lens shading yet (own calibration, S4) |

Open: which of the 12 patches are really needed (S3), lens shading and black level from our own measurements (S4), autofocus behaviour in a controlled scene, noise.

## Test 3 (2026-10-07): WirePlumber crashes when a camera stops or the camera is switched

Reported symptom: switching between the cameras, or toggling Kamoso's mirror option (which stops and restarts the stream), aborts WirePlumber every time.
Two separate defects in libcamera's IPU3 pipeline, both found from the core dumps (`coredumpctl info`):

1. `IPU3Frames::find(id)` ends in `LOG(Fatal)` when a frame is not tracked. After stop() clears the tracking, a late `paramsComputed` / `metadataReady` message from the IPA
   arrives and the process aborts. Fixed by `0013-ipu3-ignore-late-ipa-messages.patch` (those two callbacks use a lookup that ignores frames that are gone).
2. `PipelineHandler::stop()` aborts on `assertion "data->queuedRequests_.empty()" failed` when requests were in flight: the IPU3 `stopDevice()` only cancelled the requests it had not started,
   while the others wait for IPA metadata that never comes after the stop. Fixed by `0014-ipu3-cancel-in-flight-requests-on-stop.patch` (cancel and complete the requests still tracked).

`tools/dev/camera_stress.sh` starts and stops the two cameras through PipeWire at random sizes, alone, switching and overlapping.

| Image | Result |
|---|---|
| 12 patches | crashes at once when a camera stops (`find()` Fatal) |
| + 0013 | crashes at cycle 2 (`queuedRequests_` assertion) |
| + 0013 + 0014 | **40 of 40 cycles, 0 crashes** |

Open: the rear camera picture is reported as mirrored. The sensor's HFLIP control reads 1 while streaming (checked through the subdevice), so the hardware flip is applied; whether the picture is
really mirrored needs a real text in front of the lens. Colour (magenta centre) waits for our own calibration.

## Test 4 (2026-10-07): the brightness "flash" when a camera starts

Reported: the picture flashes whenever the camera is switched or Kamoso's mirror option is toggled (the stream stops and restarts).
Measured with the mean luma of each frame (`GRAY8` 640x480 through PipeWire, 75 frames per start). Before: the first ~30 frames of every start were erratic
(rear: 8 near-black frames, a jump to ~200, then ~25 frames to settle; front: steps between 77, 119 and 166).

Cause: `Agc::configure()` resets the exposure to a fixed 10 ms at minimum gain on every start (black in a dim room), then the algorithm ignores 8 frames and takes one large first step.

Fix: `0015-ipu3-agc-start-from-settled-exposure.patch`. Each camera remembers the exposure and gain it had settled on after about a second of streaming
(`kAgcSettledFrames`) and the next start begins there, clamped to the limits of the new sensor mode.

| Start | Result |
|---|---|
| first start of a camera after boot | still rough (nothing to remember yet): rear starts black and takes ~40 frames to settle |
| any later start (switching cameras, mirror toggle) | flat from the first valid frame (front 111 on every frame, rear 112-120) |
| stress test, 25 cycles | 0 crashes |

Left over: **one black frame at position 2 of every start**, on both cameras. No kernel error is logged; WirePlumber logs `Zero sequence expected for first frame (got 1)` and
`Obtained an uninitialised FrameContext`, so the frame numbering of the first frames is shifted by one between the CIO2 and the IPA. To investigate.
