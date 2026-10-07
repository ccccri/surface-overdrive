# Surface Overdrive: architecture (draft v0, 2026-10-06)

A personal project for one Surface Go 1824 (Wi-Fi, 8 GB, NVMe) running Fedora Kinoite 44, later 45, with Secure Boot on.
It is not meant for other models or other users. Every decision is marked **[DECIDED]** or **[TO VERIFY]**
(in which case a spike in `docs/SPIKES.md` confirms or rejects it on the device).

## 1. Goal

On a freshly installed and updated Kinoite, one command brings the tablet to a state where cameras, NFC, volume buttons,
pen, keyboard cover and audio work, and **keeps working after updates without the user rebuilding anything**.
When something breaks, the system notices, says so and offers a repair.

Constraints:
- **No Microsoft data** in the project (no calibration tables, no derivatives). Camera calibration comes from our own measurements.
- No dependency on a local clone of the repository: everything needed at runtime ships in the system image.
- The tablet **builds nothing**. Building happens in CI.
- Degrade gracefully: if a fix is missing the system behaves like stock. Never a broken boot.
- The project serves one device, so no compromises for portability. Quality should still be that of a serious project.

## 2. Principles

1. **A fix is a declaration plus a check**, not a sequence of commands.
2. **Everything inherited from the previous repository is a hypothesis**: it is re-measured before it is trusted (see SPIKES).
3. **Fewer patches are better.** For each one: is it still needed? is it an upstream bug? can it go upstream? An accepted patch is maintenance that disappears.
4. **Correctness comes before features.** Patches that fix bugs ship before patches that add controls.
5. **The system is observable.** Every component logs to the journal under a stable identifier and has a status command.

## 3. Problem map

| Problem | Solution | Lives in | Status |
|---|---|---|---|
| Rear camera: green stripes (sensor mode left stale) | Patch to the `ov8865` driver (already proposed to linux-surface) | kernel module | established |
| Rear exposure wrong by 4x (pixel rate), stepped gain, unusable 800x600 mode | Patches to the `ov8865` driver | kernel module | re-evaluate one by one (S2) |
| Front: frame rate above what the receiver accepts | Patch to `ov5693` | kernel module | check it is still needed (S2) |
| NFC: `NXP3001` not recognised, NACKed reads that stall the chip | Added id plus retry; or bind the stock driver | module or udev rule | **S1** |
| Volume buttons do not repeat when held | Patch to `intel_hid` | kernel module | established |
| WirePlumber crashes (`std::clamp`, frames in flight) | libcamera patch (upstream bug) | libcamera | established, to send upstream |
| Unstable autofocus, AE/AGC, sensor delays, black level, rear flip | libcamera patches (tier 1) | libcamera | established, re-measure (S3) |
| Vignetting and colour cast | **Own** calibration (lens shading and black level from measurements) | `/var/lib/surface-overdrive/calibration/` | **S4** |
| Live controls (gamma, saturation, denoise...) | Tier 3: deferred | libcamera + panel | after M5 |
| Pen battery always 0% | HID-BPF program | image | established |
| Keyboard-cover trackpad sometimes missing | udev rule and recovery unit | image | established |
| Quiet speakers, over-sensitive microphone | PipeWire filter-chain (as Asahi does) or ALSA/WirePlumber rules | image | **S5** |

libcamera patch tiers: **1** correctness (crashes, AF, AGC, black level, flip, delays), **2** quality (lens shading with our own tables, tone curve),
**3** features (live profile, temporal denoise, panel controls). One tier ships at a time.

## 4. Distribution: a custom bootc image **[DECIDED]**

Start from `quay.io/fedora-ostree-desktops/kinoite:44` (and `:45` once its stable base exists) and add only what is needed.

Why not on-device scripts or layering:
- kernel and modules travel together: **a new kernel cannot exist without its matching modules**. If the build fails, the image is not published;
- modules land in `/usr/lib/modules/<kver>/updates/` with `depmod`, which the system prefers over the stock ones. No `install ... insmod` rules, no `/var/lib/local-kmods`, no markers, no dedicated service to load the NFC driver;
- libcamera is replaced by a rebuilt package, with no `/usr/local` and no `LD_LIBRARY_PATH`;
- rollback and updates are the normal ostree ones.

### 4.1 CI pipeline (GitHub Actions)

CI means *continuous integration*: an automatic service that builds and tests the project on every change. Here it also builds the image every day.

Triggers: daily, on every push, and manually. Matrix: Fedora 44 and 45 (45 stays "experimental" until its stable base exists).

1. **detect**: reads the base digest from the registry and the kernel and libcamera versions from the Fedora repositories. If nothing changed and the patches are the same, skip.
2. **kmods**: downloads from Koji the **exact** `kernel-devel` of the kernel in the base image (not the current repo one, which may already be newer) and the kernel SRPM,
   from which it extracts only the sources of the drivers to patch. The source is thus that of the running kernel, not an upstream tag. Safety check: if a Fedora patch touches
   one of those files the job fails and says so. It builds, signs with the project key and produces a `kmod-surface-overdrive` RPM.
3. **libcamera**: downloads Fedora's SRPM, applies the patch series, rebuilds with `mock`. Cached by (version + patch hash).
4. **image**: a `Containerfile` = base + RPMs + configuration files, systemd units, udev rules, Rust binaries, KCM. Smoke test inside the container.
5. **sign + publish**: cosign signature, push to `ghcr.io/ccccri/surface-overdrive:<44|45>` and a dated tag.
6. **series-check** (separate, independent job): applies the patch series on Fedora 44, 45, `updates-testing` and Rawhide. This is the early warning: it tells us in advance what will break.
7. If a job fails: it opens an Issue with kernel, versions, commit and the log tail, and GitHub notifies you. We fix it together in a Claude Code session. The tablet keeps pulling the previous image.

Module signing key: a repository secret. The public certificate ships in `/usr/share/surface-overdrive/mok.der` and must be enrolled in the firmware once (MOK).

### 4.1.1 System tuning outside the packages

Small settings that are not about the hardware fixes but belong to the final build:
- **Plymouth scaling**: `DeviceScale=1` in `/etc/plymouth/plymouthd.conf` (`image/rootfs/etc/plymouth/plymouthd.conf`). Plymouth's configuration is copied into the initramfs
  (checked on the tablet: `lsinitrd` lists `etc/plymouth/plymouthd.conf`), so the image build has to **regenerate the initramfs** with `dracut` after adding the file.
- **GRUB countdown**: `set timeout_style=countdown` and `set timeout=3` (`image/rootfs/usr/share/overdrive/grub-user.cfg`, merged into the file by `overdrive-bootconfig.service`). On Kinoite `grub.cfg` is static and lives in `/boot`, which is **not** part of the image;
  it sources `/boot/grub2/user.cfg` after its own `timeout_style=menu` and `timeout=1`, so a first-boot step writes that file idempotently (the bootstrap does it too).
  The countdown lasts 3 seconds (chosen by the owner).

### 4.2 Updates on the tablet

Kinoite's standard automatic updates download the new image and activate it at the next reboot.
**Promotion guard [DECIDED]**: on boot, `overdrived` checks that the critical fixes work on the new deployment. If they do not,
within a set number of boots it notifies and offers rollback (`rpm-ostree rollback`) without doing it on its own.

## 5. Installation **[DECIDED]**

**Phase 0: bootstrap** (on stock Kinoite, with no graphical dependencies that might be missing). A short, readable shell script downloaded from a release with a checksum:
1. checks (model from DMI, Kinoite, network, space);
2. writes the policy and key for verifying the signed image into `/etc/containers`;
3. queues the MOK enrolment with a random password it shows on screen;
4. `rpm-ostree rebase ostree-image-signed:docker://ghcr.io/ccccri/surface-overdrive:44`;
5. reboot. Steps that need root go through `pkexec` (Plasma's password dialog), not `sudo` in a terminal.

One reboot only: the blue MOK screen appears before the boot into the new image. The bootstrap is not a Flatpak: a sandboxed app cannot change the operating system.

**Phase 1: first-boot assistant** (inside the image, with Qt/KDE available): checks the fixes, guided camera calibration (§8), summary.
The calibration needs the user's help (white screen, covered lens), so it cannot be fully automated.

## 6. Runtime

Components, each with a single job:

| Component | What it does | Language |
|---|---|---|
| `overdrived` | system service: reads the fix manifest, runs checks, orchestrates repairs, exposes state on D-Bus; privileged actions are guarded by polkit | Rust |
| `overdrive-nfcd` | always-on NFC reader, talks to the kernel over netlink (no neard) | Rust |
| `overdrive-notify` | session agent: notifications with buttons, opens the right System Settings page | Rust or C++ |
| `Surface Overdrive` KCM | a System Settings page: status, repairs, calibration | C++ + QML |
| `overdrivectl` | CLI for status, verification, repair, log collection | Rust |
| offline tools | calibration and image analysis, CI scripts | Python |

Rust for the daemons: small binaries, low memory, no interpreter kept awake on a Pentium, good support for D-Bus (`zbus`) and netlink.
The KCM has to be C++: **a pure QML KCM cannot call D-Bus** (**[TO VERIFY, S6]**: a small plugin may be enough).

### 6.1 Fix manifest

Each fix is a folder `fixes/<id>/` with a `fix.toml`:
```toml
id = "camera-rear"
title = "Rear camera"
class = "kernel"            # kernel | userspace | calibration | config
requires = ["mok", "module:ov8865"]
match.dmi = { product_name = "Surface Go" }
check = ["module-loaded ov8865 updates", "node pipewire LNK0"]
repair = ["recalibrate", "restart wireplumber"]
```
States: `ok`, `degraded` (self-repairable), `needs-reboot`, `needs-user` (MOK, calibration), `unsupported`.
Checks are data, not code: they can be tested without the tablet.

### 6.2 Monitor

Triggers: boot, deployment change (`rpm-ostreed`), a daily timer, a manual request. Silence while everything is `ok`.
One notification only for what needs the user (reboot, MOK, calibration, rollback). Background repair for what is `degraded`.
**There is no on-device rebuild any more**: the only repairs are restoring configuration, redoing the calibration and going back to the previous deployment.

## 7. User experience

The main portal is **System Settings**: a "Surface" entry with Status, Cameras, NFC, Audio and Updates pages.
Plasma notifications only lead you there: a notification button opens the right page directly (`kcmshell6`).
The extras of the old panel (equaliser with AutoEQ import, 3D view, pen and keyboard tests) stay **outside the core**: they come later as optional features.

## 8. Own camera calibration **[TO VERIFY, S4]**

Goal: get lens shading and black level without any Microsoft data, and better: specific to this unit.
- **Black level**: RAW frames with the lens covered, at several gains, per channel.
- **Lens shading**: RAW frames of a uniform white field (the desktop screen in full screen with the lens close to it, as done before), estimating a grid per channel and correcting for the illuminant.
- The result goes to `/var/lib/surface-overdrive/calibration/<sensor>.json`. A system unit turns it into libcamera's tuning file in `/etc/libcamera/ipa/ipu3/`.
- The image ships a generic starting tuning derived from **my own** measurements (own data, so it can be included).
- Microsoft's tables can be compared **privately** to check that ours are plausible, but never enter the repository.

CCM and illuminant-constrained white balance stay out of the first pass (in the old repository the matrix amplified white-balance errors).
Studied and rejected for now: libcamera's SoftISP. It has CCM and lens shading but runs in software: on a Pentium 4415Y it would give up the ImgU hardware advantage.

## 9. Testing

- **Unit**: manifest logic, state machine, NFC parser, calibration maths.
- **CI**: patch series on several versions, build, image smoke test.
- **Hardware**: `overdrivectl verify` on the tablet; one-off experiments are the spikes.
- **Fast development loop**: to try a binary or a file without waiting for CI, use `rpm-ostree usroverlay` (writable until reboot). CI confirms afterwards.
- **Tests behave like a real user**: on the tablet we log in with the real password, keep autologin and use `sudo` with the password as a user would, with no disabled sudo and no SSH tricks.

## 10. Out of scope

IR camera (not exposed by libcamera), other Surface models, GPU filters and a virtual camera, SoftISP, signing keys shared between several users.

## 11. Open risks

- libcamera patches depend on the version: CI warns, but porting is work.
- Whoever controls CI controls the code the kernel accepts: the signing key is in repository secrets. Acceptable for personal use.
- MOK has to be confirmed by hand once, on the blue screen (and again after the firmware keys are cleared).
- If CI stops for days, the tablet stays on the last working image but receives no security updates.
- The KCM needs C++: extra skills and time (S6).

## 12. Plan

| Milestone | Content | Done when |
|---|---|---|
| M0 | Repo, documents, spikes S1-S6 on the tablet | every spike has a written answer |
| M1 | CI: signed kernel modules + a minimal image that boots on the Surface | cameras and NFC work from the image |
| M2 | libcamera from SRPM with tier-1 patches; trial on Fedora 45 | no crashes, stable AF, repeatable measurements |
| M3 | Bootstrap + MOK + rebase with a single reboot, from a clean install | from-scratch trial on the tablet |
| M4 | `overdrived` + manifest + monitor + notifications + `overdrivectl` | a provoked fault is detected and repaired |
| M5 | Own calibration + KCM + assistant | colour and vignetting equal to or better than the old repo |
| M6 | Audio, pen, keyboard cover, volume moved into the image | all checks green |
| M7 | Optional extras (tier 3, equaliser, tests) | as chosen |

## 13. Reuse from the old repository (`surface-go-kinoite`, kept separately)

As **specification and reference**, not as code to copy: driver and libcamera patches (re-measured one by one), the document of root causes, the measurement tools
(`tools/focus-test/`), the NFC daemon logic (rewritten), the list of known problems (`Gotchas`, `Tried and rejected`). What does not carry over:
`~/mok` and the fixed password, Microsoft-derived tables, `modprobe install` rules, `/usr/local/libcamera-patched`, a wizard based on script output.
