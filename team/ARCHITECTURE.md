# Architecture: how the code is laid out (as of 2026-11-19)

The design and its reasons are in `docs/ARCHITECTURE.md` (section 0 = as built; sections 1-13 = the first design, partly overtaken).
This file is the working map: where each thing lives, how the pieces talk, and where to change what. If code and this file disagree, fix this file in the same turn.

## The shape in one paragraph

CI builds **one bootc image** (`Containerfile`) on Fedora Kinoite 45. It carries our signed kernel modules, a rebuilt libcamera and PipeWire plugin, small rebuilds of a few Plasma
packages, our Python package `overdrive` with its services, our System Settings pages (C++/QML plugins), a few KWin pieces and files in `image/rootfs`. The tablet installs it once
(`bootstrap.sh` + `installer/`) and then follows it with `rpm-ostree upgrade`. Nothing is built on the tablet. The runtime is **Python** (not Rust, as the first design said).

## Repository map

| Path | What it is | Notes |
| --- | --- | --- |
| `Containerfile` | The multi-stage image build | Stages: `kernel-src`, `kmods`, `probe`, `libcamera`, `spalibcamera`, `taskmanager`, `login`, `plasmapa`, `powerdevil`, `discover`, `keyboard`, `hidbpf`, `kcm`, `ladspa`, `kwineffect`, `wallpaper`, final. Each patched-RPM stage falls back to stock |
| `.github/workflows/build-image.yml` | CI: tests, build, push `:45` + dated tag, Issue on failure | MOK key from secrets; `cancel-in-progress: false` |
| `ci/` | Build helpers: `build_*.sh` (rebuild an RPM with a patch), `patch_*.py` (edit Plasma sources in place), `detect.sh`, `local-build.sh`, `mok.der` (public key) | Each patcher refuses when the file differs and has a test |
| `patches/kernel/<driver>/` | Patches for `ov5693`, `ov8865`, `nxp-nci`, `intel_hid`, built by `ci/build_kmods.py` from `kmods/modules.toml` | Signed with the MOK key |
| `patches/libcamera/` | The libcamera series 0001-0049 (+ `since-0.7.2/`) | Numbered, each explains its *why* |
| `patches/pipewire/` | The PipeWire libcamera plugin patches 0001-0005 (frame rate, drop broken frames, default size, YUY2, one rate per node) | built by `ci/build_spa_libcamera.sh` |
| `patches/plasma-keyboard/` | One patch against KDE's `plasma-keyboard` v6.8.3 | `tools/dev/keyboard-dev.sh` |
| `bpf/` | HID-BPF program hiding the pen's fake battery | udev rule in `image/rootfs` |
| `ladspa/` | `overdrive_denoise.c`: microphone noise suppression on rnnoise | |
| `kwin-effect/rotation` | Our screen-rotation effect (KWin's Transform effect with fixes) | |
| `kcm/<page>/` | System Settings pages: `about`, `cameras`, `nfc`, `power`, `screenlock`, `sound`, `tablet`, `updates`; `kcm/common` shares C++ (`overdrivekcm`, monitors, preview) and QML | C++ plugin + `ui/*.qml` |
| `src/overdrive/` | The Python package (below) | `/usr/lib/overdrive/python` on the tablet |
| `image/rootfs/` | Files copied into the image as they are: launchers (`usr/bin`, `usr/libexec/overdrive`), systemd units, udev rules, wireplumber/pipewire config, KWin scripts, Plasma Welcome pages, policies, defaults | |
| `installer/` | `install.py` (the install, with a little show), `ask.py` (the two password windows, PySide6), `root-step.sh` | `bootstrap.sh` at the top fetches it |
| `tests/` | `unittest` (about 250), the patchers' tests, launcher import test | `PYTHONPATH=src python3 -m unittest discover -s tests` |
| `tools/dev/` | Device tools: virtual touch/mouse/pen/typing, deploy and overlay scripts, benches, `keyboard-dev.sh`, `tablet-env.sh` | |
| `tools/calib/` | Camera calibration (monitor as a light box, LSC, CCM) | needs numpy in a venv |
| `tools/camera-test/` | Web page and server to see which sizes and rates browsers get | |
| `tools/handoff.py` | Turn start/end for the agents | `team/` |
| `docs/` | Human documentation; `CHANGELOG.md` is the daily record | |
| `build/`, `build-dal-duplicato/`, `old-project-chat-archive/` | Git-ignored local material | `RIPRISTINO.md` |

## The Python package `src/overdrive`

| Module | Role |
| --- | --- |
| `ctl.py` | `overdrivectl`, the one command line behind the pages: `status`, `volume-hold`, `stylus-filter`, `pen`, `audio ...`, `nfc`, `settings ...`, `repair`, `image`, `report`, `sensors`, `unlock`, `camera ...`, (beta) `brightness auto` |
| `health.py` | The checks (modules, kernel match, libcamera, cameras, tuning, NFC, pen battery, volume hold, audio, Secure Boot, image) and their explanations |
| `maintenance.py` | Settings export/import/undo, `REPAIRS` (check id to one fixed command), the system images (rpm-ostree), the scrubbed problem report |
| `watch.py` | `overdrive-health-watch`: one notification when a fix stops working; the update guard (offers to start the previous image) |
| `helper.py` | The polkit helper's actions (`volume-hold`, `stylus-filter`, ...) |
| `camera.py`, `cameraapp.py`, `camera_ui/`, `camboost.py` | Camera profile files and presets; the camera application (PySide6 + GStreamer, Plasma Camera's QML); the performance-profile hold while a camera streams |
| `audio/` | `graph.py` (filter graphs into PipeWire nodes), `eq.py`, `mic.py`, `route.py` (the route service), `sounds.py`, `store.py`, `pw.py` |
| `nfc/` | `daemon.py` (netlink reader service), `ndef.py`, `tag.py`, `notify.py` (the user's tag notifications) |
| `sensors.py`, `pen.py` | Battery/light/motion for the About page; pen, digitizer and Bluetooth pen battery |
| `unlock.py` | PIN and pattern unlock for the screen and login |
| `osk.py` | `overdrive-osk-guard`: keyboard stays available on the lock screen. (Not the keyboard itself, which is the Plasma patch) |
| `wallpaper.py`, `loginwallpaper.py`, `paneldefaults.py`, `welcome.py`, `flatpaks.py`, `bootconfig.py`, `userconfig.py` | Housekeeping services: screen-sized wallpapers, login wallpaper, panel defaults before plasmashell starts, first-login Welcome Center, flatpak preinstall/flags, GRUB/kargs, user settings paths |

Launchers are three lines each (`image/rootfs/usr/bin/overdrive-*`, `usr/libexec/overdrive/*`) and are import-checked by `tests/test_launchers.py`.

## Flows worth knowing

- **From a click to the system**: a page (QML) calls the backend (`overdrivekcm.cpp`, at most 12 concurrent `overdrivectl` calls) which runs `overdrivectl ...`; privileged changes go through `pkexec /usr/libexec/overdrive/helper`
  (polkit). Long-running readers (`sensors follow`, `audio serve`, `camera ... follow-focus`) are one process that ends with the page.
- **Camera settings**: the Cameras page and the app write the **live profile** (`~/.config/surface-overdrive/camera/<sensor>.profile`); libcamera's `LiveProfile` re-reads it while a camera runs (pipeline: `colourGrade`,
  `temporalDenoise`; IPA: agc, awb, af, blc, lsc, tone mapping, noise reduction).
- **Audio**: the route service (`overdrive-audio-route`) loads the filter graphs into the real nodes and follows device changes; the Sound page streams control values live.
- **Updates**: CI image -> `rpm-ostree upgrade` -> restart -> the health watch compares the checks with the image before and may offer the rollback.
- **Keyboard**: KWin starts `plasma-keyboard` (the input method); our patch adds the floating window, the space-bar gestures, the extra keys (own uinput keyboard), clipboard (Klipper over D-Bus) and emoji.
  The guard `overdrive-osk-guard` flips KWin's virtual keyboard mode while locked.

## Where to change what

| I want to... | Look at |
| --- | --- |
| add a health check | `health.py` (+ `REPAIRS` in `maintenance.py` if a restart mends it) + `tests/test_health.py`, `tests/test_maintenance.py` |
| add a command or page backend | `ctl.py`, the module it calls, a test; the page in `kcm/<page>/` |
| change a camera algorithm | a new libcamera patch (section 3 of `KNOWLEDGE.md`), and `tools/dev/` bench if it is arithmetic |
| change a Plasma behaviour | prefer a `ci/patch_*.py` that edits the file and refuses when it differs, with a test |
| change the keyboard | `tools/dev/keyboard-dev.sh` flow; commit the exported patch; `tests/test_keyboard_patch.py` |
| ship a new service | `image/rootfs/usr/lib/systemd/user/` unit + a launcher + a test; off by default if it is a beta |
| record a decision | `team/DECISIONS.md` |
