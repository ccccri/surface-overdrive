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
