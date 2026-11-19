# Knowledge: how things work here, and what has already gone wrong

Technical lessons, recipes and traps, sorted by subject. Each one cost somebody time. Add yours at the end of its section (date in
brackets), and **delete or correct** an item that turns out wrong. Facts about who the owner is are in `CONTEXT.md`, decisions in `DECISIONS.md`.

## 1. Working on the tablet over ssh

- `ssh surface` gives a shell **without** the graphical session. For anything that draws, talks to KWin, Plasma or polkit, source `tools/dev/tablet-env.sh`
  (copy it to the tablet first: `scp tools/dev/tablet-env.sh surface:/var/tmp/overdrive-env.sh`). It copies the session environment from the user systemd manager and defines
  `shot NAME` (a spectacle screenshot to `/var/tmp/vis/NAME.png`; `scp` it back and look at it, downscale big ones).
- **Start GUI apps with `systemd-run --user --collect --unit NAME app`**, not straight from the ssh shell: an app started from ssh is not in the graphical session, so polkit dialogs never
  show and portals refuse. Stop them with `systemctl --user stop NAME` (and `pkill -x name` for a leftover).
- **Never `pkill -f 'pattern'` where the pattern also appears in your own command line**: it kills your shell (exit 144). Use `pkill -x name`, or `^...[.]`-style patterns.
- Before the owner has logged in on the tablet, user services (pipewire, wireplumber) start without access to the devices; do not leave them running at the login screen.
- Never type a password blind into whatever has focus: look at a screenshot first for the polkit dialog. `sudo -k -S` in scripts, or a cached sudo eats the first stdin line.
- Root on the tablet: `printf '%s\n' "$PW" | ssh surface "sudo -S -p '' bash -c '...'"` with the password only in an environment variable of your own session (D-025).
- **Test deployments go to an overlay**: `sudo ostree admin unlock` (says "already in unlocked state" when it is), then write files into `/usr`. **Install next to the target and `mv` over it**
  (`install -D file target.new && mv -f target.new target`): overwriting a library that is in use crashes whatever has it open. The overlay vanishes at the next restart, by design.
- After a restart, check what the tablet really runs: `rpm-ostree status`, `rpm -q plasma-keyboard` (ends `.overdrive1`), `python3 -c 'import PySide6'`, `systemctl --user --failed`.
  Failed units that are not ours (`systemd-remount-fs`, `drkonqi-coredump-pickup` once) are stock Fedora noise.
- `rpm-ostree upgrade` downloads and stages; the owner decides the restart. Never restart the tablet on your own when they might be using it.
- Look at the tablet before using it: its screen may be in use. A screenshot that is identical twenty seconds apart means it is idle. Do not tap anything the owner may be touching
  (a Discover page with delete buttons was open once).
- The tablet's screen can be put to brightness 0 with `echo 0 | sudo tee /sys/class/backlight/intel_backlight/brightness` (the raw maximum of the Intel backlight is 1500; PowerDevil's own scale is different) and its
  sleep prevented with `systemd-run --user kde-inhibit --power --screenSaver sleep N`. Restore both when done (D-024).

## 2. Virtual input and looking at the screen

- A virtual **finger** (`tools/dev/uinput_touch.py W H`, commands on stdin: `tap`, `hold`, `swipe`, `path`, `wait`), a virtual **mouse** (`uinput_mouse.py`), **pen** (`uinput_pen.py`), **scroll**, and
  **typing** (`uinput_type.py`, for the login screen). They need root (`/dev/uinput`) or a seat user with access (Fedora KDE gives the logged-in seat user access through KDE Connect's udev rule).
- The **first tap of each new virtual device is lost** (the compositor needs a moment): start with a harmless tap, or wait 1.5 s after creating it.
- Touch coordinates in portrait are rotated: use the mouse with width and height swapped instead. The **simulated touch does not reach the real lock screen or login screen**
  (the keyboard never opens); the simulated mouse does. The `kscreenlocker_greet --testing` and `plasma-login-greeter --test` windows are safe test benches (touch does not reach them, mouse does).
- A mouse click gives a window focus; a virtual finger does not necessarily. A slow press, a stay, then a slide (hold and drag) is needed for long-press and space-bar gestures: add such
  a command to your copy of the tool when you need it (`hold X Y` then moving while down).
- Screen recording from remote: portal ScreenCast. Screenshots: `spectacle -b -n -f -o file.png` (inside the session environment).
- `wl-copy` over ssh keeps the connection open until it is killed: run it in the background or `pkill -x wl-copy`.
- Reddit is unreadable from here (403, mirrors refused); do not plan on it.

## 3. Builds, CI and the image

- `Containerfile` is multi-stage on `quay.io/fedora-ostree-desktops/kinoite:45`. A **patched RPM stage** (libcamera, pipewire's libcamera plugin, plasma-pa, powerdevil, discover, the task manager,
  the login screen, the keyboard) follows one pattern: fetch the SRPM of **exactly** the version in the base from Koji, `rpmbuild -bp` it, apply our patch or Python patcher to the tree, turn the
  difference into one more `Patch9000:` of the spec, build with release `.overdrive1`. **If the patch does not apply, nothing is built and the stock package stays, with a warning line in the log.**
  So after any base update read the log for `skipped:` / `warning:` lines (`gh run view <id> --log | grep -E "warning: |skipped: |patched: "`).
- Python patchers under `ci/patch_*.py` edit Plasma's QML/C++ in place and **refuse (skip) rather than guess** when the file differs; each has a unit test in `tests/`. When Plasma fixes the bug
  itself the patcher says `already ...` and the stage can be deleted (see `docs/UPSTREAM-WORKAROUNDS.md`).
- libcamera patches (`patches/libcamera/NNNN-name.patch`, numbered in order, applied after Fedora's; `since-<version>/` directories hold adaptations for newer libcamera) are written against the
  tree **after** the earlier ones. To work on one: run `ci/build_libcamera.sh <nvr> patches/libcamera /out/rpms` in a persistent `fedora:45` container (the tree stays in `/build/BUILD/...`), then edit,
  `diff -u`, and number the new patch. `rpmbuild -bp` alone gives the fully patched tree for reading. A header with `From:`/`Subject:` and a body that explains the *why* and the measurements.
- The keyboard patch is one file; use `tools/dev/keyboard-dev.sh` (setup, build, export, deploy).
- **Builds on the PC must be throttled**: a full uncached build froze it once (12 of 14 GB RAM). `OVERDRIVE_JOBS` (default: half the CPUs) is honoured by `ci/build_kmods.py` and `ci/build_libcamera.sh`.
  Do not run a full build while the owner is working on the PC; use `podman build --memory`.
- CI: one job per push to `main` and a daily one (cron 04:17 UTC; GitHub often starts it hours late); an Issue opens on failure and closes when it works again. Runs queue in order
  (`cancel-in-progress: false`): **do not cancel** them. GitHub keeps one running and one *pending* run per branch, so a pending run is shown `cancelled` when a newer push queues behind it: that is not a failure of the code. The image is not cosign-signed (the tablet pulls `ostree-unverified-registry`); kernel modules are signed with the
  CI key (private key only in the repository's secrets; `ci/mok.der` is the public certificate).
- `raw.githubusercontent.com` can serve an older `bootstrap.sh`/installer for about five minutes after a push.
- Fedora changes under you: a new base once removed `python3-pyside6` (the camera app and keyboard stopped starting: now installed by name and import-checked in the Containerfile), once changed Plasma to 6.8
  (lock screen and rotation effect patches had to be redone), once broke RPM Fusion's release package on F45 (`--setopt=optional_metadata_types=filelists`).
- A Python **package must not share a name with a module** next to it: `overdrive/osk/` hid `overdrive/osk.py` and would have killed the lock-screen keyboard guard. `tests/test_launchers.py` imports
  everything every launcher names.
- Run the tests with `PYTHONPATH=src python3 -m unittest discover -s tests` (about 250, a few seconds). `qmllint`, `pyflakes` and ShellCheck are used by hand when available.

## 4. Cameras (libcamera 0.7.2 IPU3, patches 0001-0049)

- The IPA must be **really signed**: Fedora's spec re-signed the stripped IPA modules at a path libcamera 0.7 no longer uses, so libcamera ran the IPA isolated in its own process at normal priority; under
  load it fell behind and streams stopped after ~8 frames. Fixed in `ci/build_libcamera.sh` (2026-11-06).
- Frame bookkeeping lives in `frames.cpp` (`IPU3Frames::create/tryComplete`); `ipu3.cpp` has the pipeline handler: `queuePendingRequests`, `cio2BufferReady`, `imguOutputBufferReady`
  (where `temporalDenoise`, `colourGrade` (saturation/hue/temperature/tint and **sharpening**), `rememberFrame` run), `concealBlankFrame` and `startupGarbage` (the first frames after a start are black or garbage).
  The IPA algorithms (`src/ipa/ipu3/algorithms/`: agc, awb, af, blc, lsc, tone_mapping, noise_reduction) read the **live profile** (`LiveProfile`) every frame.
- Open bug (T-12): changing the profile (e.g. sharpness) during a front 2560x1920 stream with sharpness above zero once stopped the camera until `wireplumber@video-capture` was restarted
  (`Request N never completed`, then `CIO2 buffer underrun`; no busy thread; not reproducible with extra DEBUG logging, so timing). Patch 0049 removes the likely trigger (30 ms of sharpening on the pipeline thread).
- Colour: the kernel's default colour conversion is analogue full-range; patch 0029 programs BT.709 limited range and declares Rec709. Front camera contrast 0.7 in the owner's profile.
- Front low-light: AE capped at 33 ms for a steady 30 fps; the black level follows the gain (0043); software TNR with remembered noise and 8x8 motion blocks (0028, 0040, 0045, 0046);
  hardware TNR3 in the IPA (0039). Hardware Y_EE_NR does nothing (video firmware), IEFD/XNR3 ~nothing, ANR is a 1:1 blur; judge trails by looking at crops, the metrics mislead.
- The rear sensor's 15 fps in full resolution is the 144 MHz pixel clock; 288 MHz and other MIPI dividers broke the picture (abandoned, D-014). Pixel rates in the patches are measured.
- Calibration: our own, from a monitor used as a light box (`tools/calib/screen.py` serves a page, flats, colour patches), LSC from raw only, no iterative tweaking; black level per mode in `ov8865.yaml`.
- Tools: `tools/dev/camera_stress.sh`, `rear_stress.sh`, `luma_series.py`, `camera_sharp_stall.sh`, `sharpen_bench.cpp`. gst test streams need caps or stream properties:
  `pipewiresrc target-object=<node> ! video/x-raw,... ! ...` (without caps GStreamer 1.28 says "target not found"); `pipewiresrc` into `vah264enc` needs a `queue` between.
- PipeWire/WirePlumber: one wireplumber instance for the cameras (`wireplumber@video-capture`, suspend timeout 0.05 s so switching cameras works); the camera boost service holds the
  "performance" power profile while a camera streams (24.6 to 28.7 fps on battery). Browsers get the cameras without patches; Firefox default 1280x960.
- The camera app: `qml6glsink` preview (zero-copy) and **no `tee`+`appsink` next to it** (it froze the preview after four frames); stop on a thread; MP4 is fragmented every second so an interrupted video stays playable.
  Pausing while hidden or locked is in `cameraapp.should_pause`.
- The camera's LED is on while any camera streams: never run camera tests while the owner sleeps in the room (D-024).

## 5. Audio

- Boost, equalizer, limiter and microphone enhancement are PipeWire filter graphs **loaded into the real nodes** with `pw-cli set-param ... audioconvert.filter-graph.0` (`src/overdrive/audio/graph.py`);
  PipeWire does not report the graph back, so a marker file in `$XDG_RUNTIME_DIR/surface-overdrive/` records node serial and version. Live controls are `"node:Control"` params; the Sound page streams
  values with `overdrivectl audio serve`.
- Do not patch the speaker ACP path for jack state (it made the headphones "unknown" and would break auto-switch). Writing a huge value to an IIO `sampling_frequency` froze gyro reads (clamped 1-100 now).
- `audio-route` once used 9 % CPU because a sink-input matched "sink": keep matches exact. The image also patches the ACP microphone profile paths (`ci/patch_acp_mic.py`: read it before touching audio profiles).

## 6. Settings pages (KCM, QML)

- Pages are C++ plugins with QML in `kcm/<page>/`, shared QML in `kcm/common/qml` (`Adjust`, `HelpLabel`, `Section`, `StockMerged`, `StockWithSide`, `Bars`); the backend is Python in `src/overdrive/`, called through
  `overdrivectl`. Try a page without installing: `tools/dev/build_kcm.sh` and `QT_PLUGIN_PATH`; on the tablet `systemd-run --user kcmshell6 kcm_overdrive_<page>`.
- Some pages **wrap Plasma's own page** (Sound and EQ, Drawing Tablet, Power Management, About this System, Software Update): the stock plugin is moved to `plasma/kcms/overdrive-stock` (or `kinfocenter`) and a
  wrapper `/usr/bin/systemsettings` remaps old ids and keeps `$0` so `kinfocenter` still starts as Info Center.
- Drawing Tablet: the stock page is loaded 0.5 s late, otherwise System Settings dies with the Wayland `tablet_added` protocol error when started through the sidebar.
- QtQuick combo boxes are **not modal**: a tap outside closes them and also reaches what is underneath (it moved sliders). All pages use the modal lists of `common/qml/Bars.qml`. Binding loops come from
  `currentIndex` being lost when a model changes: use delayed bindings.
- A `Flickable` that fits must stay still, or a touch drag moves the whole page (`Bars.qml` keeps every Flickable non-interactive when it fits). Wallpaper page: `ci/patch_plasma_defaults.py wallpaper`.
- A long-running reader is one `overdrivectl ... follow` process that ends with the page; **never** start a process per refresh (627 piled-up `overdrivectl sensors` readers once brought the tablet down). The backend
  limits itself to 12 concurrent `overdrivectl` calls.
- Never remove applets from a Plasma update script: it broke the panel at the first login (2026-11-13). The panel defaults are edited by `overdrive-panel-defaults` before plasmashell starts.
- Icon names must not start with `preferences-`; American spelling; no German/Italian strings.

## 7. Lock screen and login

- PIN and pattern unlock: `unlock.py`, `patch_pam.py`, `patch_unlock_pad.py`, `build_login.sh`, `kcm/screenlock`. The pad is sized from the screen. A layout loop (`prompts.children[2]` was the box itself) once ran the greeter at 100 % CPU.
- `overdrive-osk-guard` switches the on-screen keyboard back **on** while the screen is locked and off again after unlocking if it was the one that turned it on, and tells the unlock code the user is in.
- Log out only through `org.kde.Shutdown` (`loginctl terminate-session` breaks the session). A temporary autologin for tests (`/etc/plasmalogin.conf.d/zz-overdrive-test-autologin.conf` + restart `plasmalogin`) is removed at once.
- The owner's PIN and pattern exist and are **never** written or tried by an agent (D-023). `kscreenlocker_greet --testing` is the safe place to try the pad.
- Capturing the greeter or the locked screen needs root (`ffmpeg -f kmsgrab`).

## 8. KWin, Plasma and the on-screen keyboard

- KWin (6.8.3 source read): an **input panel** (the keyboard) is always placed at the bottom centre by the bounding box of its input region, and the focused window is kept clear of it; therefore the floating keyboard is a
  second, layer-shell overlay window (`org.kde.layershell`) and the real input panel stays behind as one point. A keysym sent by an input method **loses its modifiers** for text-input-v3 clients, so Ctrl/Alt/Meta
  combinations and Esc/F-keys/arrows go out through our own `/dev/uinput` keyboard (`src/extrakeys.cpp` in the patch). `/dev/uinput` is writable by the seat user.
- KWin starts the input method again **only when told that `kwinrc [Wayland] InputMethod` changed**: `kwriteconfig6 --notify --file kwinrc --group Wayland --key InputMethod ""`, wait, then the same key with
  `/usr/share/applications/org.kde.plasma.keyboard.desktop` (and remove the key from the file: the value is the default; never `--delete` it, that hides the system default). `tools/dev/keyboard-dev.sh restart-remote` does it.
- `org.kde.KWin /VirtualKeyboard` has `mode` 0 off / 1 touch / 2 always, `active` (follows text-field focus), `visible`, `forceActivate`, `willShowOnActive`. With the last input from a mouse or a hardware keyboard KWin keeps the panel back
  (`visible` false): good, the floating keyboard follows it through `InputPanelWindow.shown`.
- Qt VirtualKeyboard styles are looked up in the **system's** directory whatever the import path says: to test a locally built keyboard on the PC use `bwrap` to bind the built style, layouts and QML module over the
  system ones.
- Settings of the keyboard are `~/.config/plasmakeyboardrc` (`floating`, `floatX/Y/Width/Height`, `splitLayout`, `extraKeysVisible`, `enabledLocales`...). Fedora's Qt writes QML warnings to the journal, not stderr, when stderr
  is not a terminal: `journalctl --user -b -o cat | grep '\.qml'`.
- The Plasma keyboard's long-press popups and the space-bar gestures: the first press of a gesture can be lost in tests; the menu opens on a 0.55 s hold and a slide cancels it into a cursor move.
- Fedora's `plasma-keyboard` ships layouts in `/usr/share/plasma/keyboard/layouts/<locale>/main.qml` (fallback and `it_IT` are ours to change); `QT_VIRTUALKEYBOARD_LAYOUT_PATH` is set by the program.
- KWin effect `screentransform` (rotation animation) shows garbage in the newly exposed area; our own `kwin-effect/rotation` (KWin's Transform effect with fixes) replaces it. Auto-rotate is Plasma's own (Display Configuration), not a widget of ours.
- Screen lock auto-lock and sleep on the tablet: set by the owner. Do not change them (D-023); to stay awake use an inhibitor (section 1).

## 9. Packaging, services and Python

- Everything we ship at runtime is in the image: `image/rootfs/` (files), `src/overdrive` (`/usr/lib/overdrive/python`), launchers in `/usr/bin` and `/usr/libexec/overdrive` (three lines each). The tablet needs no clone.
- User units are enabled through `image/rootfs/usr/lib/systemd/user/*.wants`; a beta service must be **off by default** and enabled by a command (`overdrivectl ... on`).
- Settings the user chooses live under `~/.config/surface-overdrive/`; the export/import in Software Update has an allow-list of paths: add new files there.
- Reports (`overdrivectl report`) are scrubbed (NFC tag contents, serials); the repository is public and the owner attaches the file by hand.
- Python 3.15 on the tablet and the PC; no pytest, plain `unittest`. QML files can be linted with `qmllint` where installed; noise from Kirigami's own files is normal.

## 10. Hardware and power notes

- The tablet loses charge when powered off and sometimes powers itself off after hours of use (upstream linux-surface issues #1111, #1227, cause unknown). A pstore dump at every shutdown is kept in the journal:
  `journalctl -b -1 -t systemd-pstore`.
- NFC polling period 50 ms in the patched driver (a modprobe file is not enough: the module loads from the initramfs). The reader works through the back of the tablet behind the right corner.
- The pen's side button is MiddleButton in Qt and only arrives with movement; the top button sends Meta+F20/F19/F18 (F20 is MicMute: a bare F20 mutes the system microphone), recognised by XKB keycodes 196-198;
  it is the camera shutter in the camera app.
- The initramfs was trimmed (`dracut --omit-drivers "nouveau amdgpu radeon"`): boot 50 to 43 s.
- Every image build logs `dracut-install: ERROR: installing '/root'` once; images boot; not looked into.
- `systemd-remount-fs` failing on composefs is stock Kinoite and harmless.
