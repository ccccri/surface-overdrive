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
