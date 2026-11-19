# Context

Who the project is for, what it runs on, how the owner works, words used, where to look things up. Durable facts only; what is
happening now is in `STATUS.md`. Technical lessons and recipes are in `KNOWLEDGE.md`.

## The owner

- A single person, the owner of the tablet and of the repository (GitHub account `ccccri`). It is a personal project: no other models, no other users.
  Refer to the owner as "the owner" or "they" (no pronoun was ever given).
- Writes to the agents in Italian, often from bed or from another device; expects answers in Italian, short and plain. Everything in the repository is English (D-005).
- Judges by **using the tablet**: the owner's tests are the real acceptance. They asked for work to be re-checked, repeated and tested before it is called finished,
  and for reports that say plainly what was and was not tried.
- Dislikes (said so): text that opens inside layouts, separators or frames that flag our additions, buttons that make the keyboard or a page huge, being told a fix is
  done when it was only written.
- Does the user-side tests that need a person (pen pressure, resume after sleep, calls, wallpaper with a finger were reported fine on 2026-11-16) and reports bugs as they
  find them. Gives permissions explicitly; see `DECISIONS.md` D-023/D-025.
- Sleeps in the room where the PC and the tablet stand: see D-024.

## Hardware

**The tablet**: Microsoft Surface Go (model 1824), Pentium Gold 4415Y (2 cores, 4 threads, 1.6 GHz), HD 615 graphics (VA-API H.264/HEVC/JPEG encode with
RPM Fusion's driver, no VP8/VP9 encode), 8 GB RAM, NVMe, Wi-Fi ath10k (correctable PCIe errors in the log are normal), 1800x1200 screen (scale 1.45 in Plasma),
used as a tablet (no Type Cover). Secure Boot is **on**; the module key is enrolled once through the blue MOK screen.
- Front camera **ov5693** (5 MP, the one used for calls), rear camera **ov8865** (8 MP, autofocus); both through the Intel IPU3 (CIO2 + ImgU). Rear sensor raw is BGGR; the rear
  black level is in doubled ImgU units (sensor pedestal 16 becomes 32).
- NFC: NXP3001 on I2C (kernel driver `nxp-nci` patched); reader antenna behind the right corner of the screen, back of the tablet.
- Pen: ELAN digitizer, Surface Pen over Bluetooth (battery over BlueZ); the touchscreen invents a fake pen battery that a HID-BPF program hides.
- Volume buttons: `intel_hid` patched so that they repeat when held. Light sensor (IIO `als`, lux), accelerometer and gyro through iio-sensor-proxy.
- It discharges slowly when powered off and rarely switches itself off by itself after hours of use (known upstream, linux-surface issues; a pstore dump is kept in the journal).
- Battery care: it is not left on charge overnight by the owner (charger LED). A long test can find it flat.

**The PC "dsktp"** (where agents run): Bazzite (Fedora atomic) with Plasma 6.8, 3840x2160 at scale 1.7, "us" keyboard layout, podman, Claude Code and OpenCode. It
also drives the owner's streaming setup (not part of this project). Fans, RGB lighting, webcam and a Flipper are the owner's own business there: never touch them.
Heavy builds can freeze it (12 of 14 GB used once): see `KNOWLEDGE.md` "Builds".

## Machines and access (no secrets here)

| What | How |
| --- | --- |
| The repository | `~/Claude/surface-overdrive` on the PC; GitHub `ccccri/surface-overdrive` (public); `gh` is logged in on the PC |
| The image | `ghcr.io/ccccri/surface-overdrive:45` and a dated tag per build; the tablet follows `:45` |
| The install page | `curl -L ccccri.github.io \| bash` runs `bootstrap.sh` (the repo `ccccri/ccccri.github.io` is only a Pages redirect); raw.githubusercontent may serve a stale copy for ~5 minutes |
| The tablet over ssh | alias `surface` in `~/.ssh/config` of the PC, user `cri`, key login. The tablet's LAN address **changes at every install**: when ssh says "No route to host" the tablet is off, asleep or has a new address (ask the owner; do not scan the network). Tailscale also names it `surface` |
| Root on the tablet | `sudo` with the owner's **temporary** password, given in chat when needed, kept only in your own session (D-025). Prefer commands that need none |
| Out-of-repo build trees | `~/Claude/so-build/` (keyboard checkout and build `pk/`, libcamera build `lc/`, built RPMs `kbrpm/`); `build/` in the repository is git-ignored (old calibration captures, test images, 24 GB of unique files in `build-dal-duplicato/`) |
| Containers on the PC | podman: `pkdev` (keyboard build, made by `tools/dev/keyboard-dev.sh setup`), `lcdev` (libcamera build, `ci/build_libcamera.sh`), `so-kcm-dev` image (settings pages build). Stop them when idle |
| Private notes | `old-project-chat-archive/` (git-ignored) holds the old chats; Claude's private memory is not shared (D-026) |

## Words

- **Image**: the bootc/ostree system image CI builds. **Overlay**: `ostree admin unlock` makes `/usr` writable until the next restart; test deployments go there.
- **KCM**: a System Settings page (C++ plugin with QML, in `kcm/`). **Stock page**: Plasma's own page that ours wraps.
- **IPA**: libcamera's image processing algorithm module (3A: exposure, white balance, focus); **ImgU/CIO2**: the Intel IPU3 image unit and capture unit.
- **TNR**: temporal noise reduction (our software filter and the hardware TNR3). **Live profile**: the per-camera text file under `~/.config/surface-overdrive/camera/`
  that libcamera and the Cameras page read while a camera runs.
- **MOK**: the machine owner key the firmware trusts for our signed kernel modules. **Guard**: `overdrive-osk-guard`, keeps the keyboard available on the lock screen.
- **Boost / EQ**: the Volume Boost and equalizer of the Sound page. **Health monitor**: `overdrivectl status`, the checks and repairs in Software Update.
- **OSK**: on-screen keyboard. **The owner's unlock PIN and pattern**: they exist; they are never written anywhere and never tried by agents.

## Ideas (not tasks; the owner asked for research on 2026-11-16 and it is not done: T-13)

- Automatic brightness (beta exists, T-08). Scan-to-text from the rear camera. Pen button shortcuts in more places. A different keyboard layout per app. Charge limit if the
  firmware exposes one (look at `/sys/class/power_supply/BAT1`). A "battery saver" profile that also lowers the camera and wallpaper work. Resume-time checks after sleep.
- Upstreaming: the `ov8865`/`nxp-nci`/`intel_hid` kernel patches and the libcamera crash fixes could go to their projects (linux-surface, libcamera); `docs/UPSTREAM-WORKAROUNDS.md`
  lists what to remove when others fix theirs.

## References

- `docs/ARCHITECTURE.md` (section 0 = how it is built today), `docs/FEATURES.md`, `docs/CHANGELOG.md`, `docs/TEST-RESULTS.md`, `docs/SPIKE-RESULTS.md`, `docs/UPSTREAM-WORKAROUNDS.md`,
  `docs/FRONT-CAMERA-BASELINE.md` (the state of the front camera before the 2026-11-04 rebuild; git tag `front-baseline-2026-11-04`), `docs/voice-search-amo.md`, `RIPRISTINO.md`.
- Git tags: `before-concept-pages` (before the Software Update additions, a revert point the owner asked for), `front-baseline-2026-11-04`.
- Upstream: libcamera (https://libcamera.org), linux-surface (https://github.com/linux-surface), KDE Plasma source (https://invent.kde.org/plasma), Fedora Kinoite (https://fedoraproject.org/kinoite),
  KWin's input method code (`src/inputmethod.cpp`, `src/inputpanelv1window.cpp` in kwin) for how keyboards are placed.
