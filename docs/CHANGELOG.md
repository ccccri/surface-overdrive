# Changelog

What was added, what broke, and what fixed it. Newest first. "Verified" means tried on the Surface Go itself.

## 2026-10-27

**Fixed**
- Wallpaper page listed some wallpapers twice ("Waterfall" twice): the screen-sized copies made by the wallpaper service
  were packages in ~/.local/share/wallpapers, which Plasma lists. They now go to ~/.local/share/surface-overdrive/
  wallpapers; copies in the old place are made again there when in use and removed otherwise.
- CI: the base images are pulled with retries before the build (a cut download from quay.io's CDN failed a build).


**Fixed (night, found by stressing the camera app on the tablet)**
- The wallpaper service asked `kscreen-doctor` for the screen size at every check; it crashed once at the start of a
  session (a crash report in the journal). The size now comes from the kernel: the native mode of the connected eDP
  panel in /sys/class/drm (orientation does not matter there: long and short side).
- Boot: the initramfs we regenerate (for Plymouth) was 240 MB, 150 of them firmware of NVIDIA and AMD graphics cards
  the Surface Go does not have; the firmware read it for about 12 s at every boot (systemd-analyze: loader 15 s of a
  50 s boot). dracut now leaves out nouveau, amdgpu and radeon.
- Stopping a recording right after starting it froze the app ("Not Responding"): EOS sent to a camera source that had
  not delivered a frame yet blocks, and it was sent on the window's thread. EOS now goes out on a thread of its own, a
  recording stopped before its first frame is thrown away (it was a 0-byte file), a second tap while saving does
  nothing, and a video that does not finish within ten seconds is closed anyway. Closing the window while recording
  keeps the video (verified: 11 s, H.264 + AAC, playable).
- No camera in the app when the camera service had started before the login gave it the devices (it does not look
  again by itself): the app looks again every 2 s, restarts the camera service once, and only then says so.
- After a burst of six camera switches the front camera ran without frames until the camera service restarted.
  Switches are now one a second at most, and a preview without frames for 5 s is started again (the second time with
  the camera service restarted).
- Started outside Plasma (no platform theme) the buttons had no icons: Breeze is set when no icon theme is.
- A stall of the preview during a recording would have stopped the preview for good (it cannot start again while a
  recording holds the camera): the watchdog leaves the camera alone while recording, and the preview is started again
  when a recording ends if it is not running.
- Taking a photo encoded the full-size JPEG on the window's thread (up to a second at 7.7 MP, the window frozen):
  now on a thread of its own, the file name taken at once (a burst of four in one second: four files) and the file
  written aside and renamed, so a half-written photo never shows in the folder.

**Added (evening)**
- Camera app (`overdrive-camera`, "Camera" in the menu; `src/overdrive/cameraapp.py` + `.qml`, PySide6 and GStreamer):
  preview scaled on the GPU (`vapostproc`) and shown by Qt, mirrored for the front camera; photos from the full-size
  frame (JPEG, ~/Pictures/Camera); videos on a second stream of the same camera, H.264 on the GPU (`vah264enc`) with
  AAC sound in MP4 (~/Videos). The size is the one the Cameras page chooses. Verified on the tablet, front at 2560x1920
  in the evening: 23.9 s recorded in 23.9 s (579 frames, 24.3 fps, AAC 48 kHz stereo), the whole system at 117% of
  400% while recording (Kamoso's software Theora alone took over 100% and its videos played too fast); switching to the
  rear (3200x2400) works.

**Added (afternoon)**
- RPM Fusion's `intel-media-driver` replaces Fedora's `libva-intel-media-driver` in the image, for H.264 and HEVC
  encoding on the GPU (Fedora's build has neither; on the tablet only VA-API JPEG worked, and the HD 615 has no VP8/VP9
  encoder). It installs in `/usr/lib64/dri-nonfree`, which Fedora's libva searches first. The RPM Fusion repositories
  are used during the build only. Tried in a Fedora 44 container: signed package, key from the release package.

**Fixed (afternoon)**
- Front camera grain at 4.9 MP (patch `0030`). The motion detector of the temporal filter used the median block
  difference as its first threshold, so half of a still picture counted as a little moving and, widened by one block,
  nearly all of it: at 2592x1944 (gain 1.3) the flicker of still pixels went down by only 18%. Thresholds are now 1.5
  and 3 times the median; moving areas are smoothed in space at every size (it was left out above 2.6 MP while the
  filter ran in bands). Offline, 40 frames at 2592x1944: flicker 1.91 -> 1.31 (raw 2.34), grain 0.86 -> 0.56; the
  100 frames of a person moving at 1152x864 give the same trail (0.74). On the tablet: 24.3 fps at 2560x1920 (26
  before), 59% of a core; 1152x864 unchanged (28.9 fps, 44%). The owner had set "maximum" grain removal on the
  23 October Cameras page (`tnr 12 16`), which with the new filter left trails and lag; back to the default.
- The new bench `build/tnrbench/benchcur.cpp` is extracted from ipu3.cpp itself, so offline numbers are the real filter.

**Added**
- Rear camera, tried and dropped: full resolution at 30 fps (kernel patch `ov8865/0005`, removed again). The full
  resolution modes clock the sensor array at 144 MHz (15 fps); at 288 MHz the sensor did deliver 29.9 fps, but the
  pictures came out broken (stripes, lines cut short). Raising the sensor's MIPI pixel clock as well (divider 4, 5 or
  6 instead of 8) gave no frames at all or black ones at 25-35 fps. The rear stays at 15 fps above 1536x1152 and 30 fps
  at 1536x1152.

**Fixed**
- Camera colours read wrong in every application (patch `0029`). The ImgU used the kernel's default colour conversion,
  which gives full-range analogue YUV (V = 0.877 (R - Y)), and the pipeline declared no colour space, so GStreamer (and
  Kamoso, which ignores a declared one anyway) read it as limited-range BT.709: blacks crushed, whites clipped, red 57%
  too strong. The owner saw pink skin and red grain on the front camera at 4.9 MP. The IPA now programs limited-range
  BT.709 and the pipeline declares it. The bias of the conversion is in 1/32 of an 8-bit level (measured: 512 adds
  exactly 16). In Kamoso, same scene: wall saturation 0.157 -> 0.120 (the phone: 0.097), black cloth 29 -> 35, colour
  noise on a white ceiling -12%. Both cameras; the rear's black lamp base lost its red cast.
- Front camera tone curve: contrast 0.45 -> 0.7 (blacks lifted once they were no longer crushed by the wrong decoding).
  The owner's profile had gamma 1.55, contrast 0.65 and shadows 0.35, set to make up for the crushed blacks; they were
  taken out on the tablet (copy in /var/tmp/art/ov5693.profile.before-csc).

## 2026-10-25

**Fixed (evening)**
- Temporal denoise on one thread (patch `0028`). The frame was cut into up to four bands filtered in parallel; on the
  Surface Go (two cores, four threads) that only added CPU. Measured with `cam`, steady state, per stream: front
  1152x864 76% of a core with four bands, 43% with one (the filter itself 8.5 ms a frame, the camera without it 13%);
  2592x1944 26 fps with one band, 13 with two; rear 3264x2448 15 fps with one, 9 with two. In Kamoso the camera service
  went from about 1.6 cores to 35% of one (preview, front, evening light). `LIBCAMERA_IPU3_TNR_THREADS` brings the bands
  back for measuring. Tried and dropped: filtering a copy of the frame in ordinary memory (no faster).
- The PipeWire camera plugin offers at most 30 fps. The front camera reported 60 at 1152x864 but delivers about 29.
- Health check: a missing camera now comes with its cause when the IPA refused the tuning file (the algorithm it did not
  know, and the command that sets the file aside).
- CI: the image push retry used `podman push --retry`, which the runner's podman does not know, so every push failed.

**Known limits (evening)**
- Kamoso videos at 1152x864 and above play too fast. Kamoso records Theora in software through `camerabin`, which
  numbers the frames instead of keeping their times when the encoder falls behind. Reproduced on the tablet with a test
  pattern and no camera at all: 10 s became 10 s at 640x480 and 4.3 s at 1152x864 (Theora manages about 13 fps there).
  The camera's own timestamps are right (checked with `pipewiresrc`). Kamoso itself uses one full core while recording.

**Added**
- Front camera: XNR3 of the ImgU turned on for chroma (new IPA algorithm `NoiseReduction`, patch `0026`; key `xnr3` in
  the tuning file and the live profile). The kernel leaves XNR3 at alpha 2047 and strength 0, which does nothing; earlier
  tries with "strong" values did nothing either, because alpha is the inverse of the filter's sigma (Intel's CSS:
  1024 * 32 / sigma). Measured by switching it on in the middle of one stream on a static scene: chroma blotches -25% in
  the shadows and -45% in the midtones at full resolution, -10-15% binned, colours and detail unchanged; the red and green
  dots in dark areas are gone. XNR3 acts on chroma only on the firmware's video binaries. Also measured and left as they
  are: CHNR (wider filters wash out pale colours), the Bayer denoiser (does not act at daylight gains, breaks the picture
  pushed further), a stronger software temporal filter (-10-25% luma grain at full resolution but smears motion). The
  luma grain left is the sensor's.
- Temporal denoise rewritten (patch `0028`), after the owner saw a trail behind a moving hand and the grain coming
  back while moving: motion is judged per 4x4 block (noise cancels out in a block, a soft moving edge does not), the
  block map is widened by one block and interpolated between block centres (no steps), the thresholds follow the noise
  of each frame, and moving areas are smoothed in space (a 3x3 mean, by at most 3 levels) instead of passing raw.
  Measured offline on the same 100 raw frames of a person moving: trail 0.74 against 1.94 for the per-pixel filter,
  grain on moving areas 0.49 against 0.79, on still ones 0.32 against 0.35.
  A first version of it cost up to six times the CPU of the old filter (the owner saw the frame rate collapse and
  glitches): the kernels are now SSSE3 (16 pixels at a time, plain loops as a fallback), the motion is measured on
  every second row, histogram and block map are built in parallel, and the spatial part is left out above 2.6
  megapixels. Measured on the tablet (frames per second, filter on): front 28.6 / 28.6 / 26.6 / 22.3 at 1152, 1536,
  2048 and 2560 wide (the old filter: 28.6 and 19.6 at 1152 and 2560), rear 30.1 at 1536 and 13.8 of 15 at 3200, with
  less CPU than the old filter at every size. 150-frame runs at every size: no broken frame, no step at block edges.
  With Kamoso showing the front camera the system is 69% idle.
- Front camera: stronger temporal denoise by default (24/18 instead of 48/12, patch `0027`; superseded by `0028`). Tried in Kamoso from the tablet with a virtual touchscreen, late afternoon light (20-30 ms, gain 1.1-1.3): the
  grain of flat areas in the preview drops by about a third, pictures show 5-10% less grain with the same detail. The
  "Grain removal" control of the Cameras page shows each camera's own default.

**Fixed**
- Kamoso listed every camera twice when the cameras' WirePlumber instance ran without the configuration that takes the
  cameras away from the main one (on a system where only part of the change was in place): the instance now starts only
  when that file is there.

**Verified**
- Rear camera stress test (`tools/dev/rear_stress.sh`, every frame checked for black, flat or frozen): 40 start/stop at every
  size, 15 size changes through the camera service, two applications at once, rear and front in turn, 10 minutes at
  30.0 fps with steady PipeWire memory, no crash and no kernel error. Suspend and resume with the camera streaming (in
  Kamoso and in the Cameras page): the stream goes on after the resume and the cameras open again. Both cameras at once is
  not possible (libcamera's IPU3 pipeline: the second gets no frames, the first goes on). `gst-launch pipewiresrc` run
  from ssh sometimes did not find the camera ("target not found"): without a media type the stream was not matched with
  video nodes; the test script states it.

**Fixed**
- Changing a camera's picture size in the Cameras page no longer takes the sound away (Plasma showed "Built-in Audio
  Analog Stereo") nor leaves the preview glitching: the cameras have a WirePlumber instance of their own
  (`wireplumber@video-capture`, the main one runs with `hardware.video-capture` disabled), the page restarts only that
  one and waits until the cameras are back (1.5 s) before starting the preview again. Verified on the tablet with a
  virtual touchscreen: ten size changes in a row on both cameras, every one clean, the sound nodes untouched.
- Videos recorded with Kamoso: 6 frames in 18 seconds, with a frame every 2^31 seconds. PipeWire's libcamera plugin
  offered no frame rate at all, and GStreamer then fixed the smallest one it could. The plugin is now rebuilt with a
  frame rate (patch `patches/pipewire/0001`; a fixed rate, since GStreamer left a range unfixed at 3200x2400 and the stream failed, built by `ci/build_spa_libcamera.sh`). Recording
  stays slow on this processor (Theora in software: about 10 frames a second at 1152x864, 2-3 at 2048x1536).

**Changed**
- Both cameras retuned for their look, against phone pictures of the same room, in every stream size (verified by the
  owner in Kamoso: "the colours are exactly as I wanted"). The colour matrices measured on a laptop screen are gone: they
  made real things far too saturated (a light blue wall turquoise, skin red or pink, hair purple) and raised the colour
  noise by a quarter. A small hand-made matrix turns reds a little towards yellow instead (skin hue 10-14 -> 17-22
  degrees, the phone's 21). Black level per channel and per sensor mode (dark cloth was magenta on the front camera,
  blue-cyan on the rear one), gamma 1.5 with an S curve (contrast 0.45), mean target 0.20. No data from Windows: the
  front camera's lens shading is our own table, which on the same scene did as well as the Windows one of the
  previous project.

## 2026-10-24

**Added**
- One wallpaper everywhere (verified on the tablet, the login screen photographed after switching to it): when the wallpaper
  of the desktop changes, the lock screen and the login screen get it too, in the variant the desktop shows (Fedora's look is
  Breeze Dark, so F44 is the blue one). The login screen runs as its own user and cannot read the home folder: the user
  service sends the two screen-sized JPEGs to `/usr/libexec/overdrive/login-wallpaper` (polkit, no password for
  administrators: rule in `/usr/share/polkit-1/rules.d`), which decodes them, writes them again into
  `/var/lib/surface-overdrive/login-wallpaper` and points `/etc/plasmalogin.conf` at them (the login screen reads its
  wallpaper from that file only, not from `plasmalogin.conf.d`). A lock screen wallpaper chosen on its own stays until the
  desktop one changes again.

**Fixed**
- Password prompt in tablet mode (verified on the tablet, driven through a virtual touchscreen): the on-screen keyboard now
  opens with the prompt (KWin script `overdrive_prompt_keyboard`; KWin shows it only after a touch on a field), and it is
  drawn over the windows (`OverlayVirtualKeyboardOnWindows`): when the prompt closed, KWin shrank the window behind it to
  make room and left it in the top half of the screen. Our pages also take the focus off text fields before an action that
  asks for the password.
- Serial number in "About this System": shown in its line (dots, an eye to show it, a button to copy it) instead of
  Plasma's dialog, which opened off centre inside our page.
- Cameras start without the flash and the green tint (verified after a reboot, in Kamoso and in the Cameras page):
  - Sensor delays (patch `0011`): a new exposure or gain shows in the frame after the one it was written in, on both
    sensors (measured by logging the controls pushed and the brightness of every frame). The delay of 2 made the AE judge
    one frame at every change with the old values, so it overshot and bounced, seen as a flash in the first two seconds.
  - White balance start (patch `0024`): it started from gains of 1, the sensor's own green, until a frame bright enough
    to measure; it now starts from the last session, or the middle of the locus, and moves towards a new estimate
    instead of jumping. The AE weighed the channels with the blue and green gains swapped (upstream bug), fixed too.
  - Memory across reboots (patch `0025`): the settled exposure and white balance are kept in
    `~/.local/state/surface-overdrive/camera/<sensor>.exposure|white-balance`, so the first picture after a reboot starts
    from them.
- Nightly build: the registry of the base image answered 503 for a few minutes and the build failed in 15 s.
  `ci/detect.sh` now asks once (not twice), without listing the tags, and tries again up to five times.
- Splash screen after logging in back (the `/etc/xdg/ksplashrc` that turned it off is gone): without it the Surface did
  not look faster, only blank for a moment.

## 2026-10-18

**Added**
- Rear camera calibrated with our own measurements (tools in `tools/calib`). The laptop screen is the light source, driven
  from the PC (`screen.py`: a page that shows the colour it is told), which makes every measurement repeatable:
  - Black level per sensor mode (patch `0022`): the ImgU's optical black counts about twice the sensor's codes, so the
    pedestal of 16 is written as 34 (full resolution) and 30 (2x2 binned). Too little left part of the pedestal in, which
    the lens shading gains blew up in the corners: up to +11% red in the 3200x2400 mode, where Kamoso takes pictures.
  - Lens shading: brightness from paper on the screen showing white with the camera pressed against it, colour from a
    matt white sheet lit from the front by a window (`lsc_colour.py`). Light leaving backlit paper at a slant is warmer,
    which made the corners 8% too red and left a pink centre in pictures (+34% to +42% red); now about +5%. Checked in
    every stream size (`shading_probe.py`).
  - Colour matrix from the 24 colours of the chart shown one at a time on the whole screen and measured on the optical
    axis (`ccm_screen.py`), saturated colours dimmed so they do not clip.
  - White balance held to the line of real lights (patch `0023`, "locus" in the tuning file): a dual white LED desk lamp at
    its five settings, daylight and the screen's D65 white. The grey world estimate can no longer drift towards green or
    magenta; some room for greenish LED and fluorescent lights.
  - sRGB tone curve (`curve: srgb`) with lower exposure targets. The default nearly linear curve, read as sRGB, made
    pictures about twice as saturated as an iPhone's of the same scene.
- Apps of the image: Xournal++ and Kamoso preinstalled, KMines, Elisa and KolourPaint removed
  (`overdrive-flatpaks.service`: `flatpak preinstall` from `/usr/share/flatpak/preinstall.d`, and a list of apps removed
  once, so that one installed again by hand stays).

**Verified**
- The nightly image of 2026-10-18 came to the tablet through Discover and booted: the whole update path works.

**Open**
- The colour matrix still turns orange towards red on real objects (a screen emits three narrow lights, real surfaces
  reflect broad ones); a printed reference chart would settle it. Front camera not calibrated yet. Kamoso restarts the
  camera for every picture (blurred or dark shots). Tablet mode of our own (Plasma 6.7 only enlarges the tray icons).

## 2026-10-15

**Added**
- Unlock with a PIN or a pattern (nine dots), chosen in Settings > Screen Locking ("Unlock with: Password only / PIN /
  Pattern", set twice, confirmed with the password through polkit). The pad shows on the lock screen (after idle and
  after sleep) and on the login screen (cold start): a keypad that turns 4x3 in landscape so Sleep/Restart/Shut Down keep
  their place, or the dots. "Use Password" switches to the field. The password works everywhere as before; sudo, polkit
  and the wallet never take the PIN. Five wrong codes leave the password only until it is used once.
  How: `pam_exec` line in front of the password check of the "kde" and "plasmalogin" PAM services (`ci/patch_pam.py`),
  scrypt hash in `/var/lib/surface-overdrive/unlock/<user>`, Plasma's lock screen patched in the image, the login
  screen rebuilt from Fedora's package with the pad (`ci/build_login.sh`; QML is compiled into it).
- Pad, second version: while the pad is in use the face of the user goes away, the name stays above the pad and the
  whole column moves up into its place, so the classic 3x4 keypad fits in landscape too. A PIN is tried at its last
  digit (no Enter key; the length is kept next to the hash), also when a new PIN is typed the second time in Settings.
  The dots take touches through a pointer handler: the login screen does not turn touches into mouse events.
- Pad, third version: the keys and dots are sized from the height between the name and the actions (and at most four fifths
  of the screen width), so the keypad and the grid are as big as the screen allows, landscape and upright like a phone;
  Sleep/Restart/... stay at the bottom; "Use Password" moved to the bottom row, between the keyboard button and the battery.
- Screen Locking page: the dialog that sets a PIN or a pattern is a plain modal dialog (the Kirigami one scrolled sideways
  under a finger, moving the pad), its keys sized to the window; the page scrolls when the window is short; an old message
  goes away when a new change starts; leaving the page no longer leaves Plasma's form pointing at ours. Stress-tested with
  dozens of quick taps, cancelled password prompts, mismatched second entries, landscape and upright.
- On-screen keyboard no longer dimmed behind a password prompt (polkit): KWin's dim screen effect leaves the input method
  window alone (`ci/patch_dimscreen.py`).
- No splash screen after logging in (`/etc/xdg/ksplashrc`): the desktop shows as it is drawn instead of behind the KDE logo.
- "Show the Surface fixes" in the health notification opens Software Update: System Settings was started inside the oneshot
  service and stopped with it, and the button worked for two minutes only.

**Fixed (unlock)**
- A right PIN or pattern could be refused on the login screen after wrong tries: SELinux lets the login screen create and
  write files in the state directory but not replace, delete or write files made by the session, and that error turned the
  right code into a failure. Each side now counts in its own file, written in place; a right code always lets the user in.
- The face of the user came back behind the pad after a wrong try on the login screen (it dims the list itself).
- "Use Password" in the bottom row took a finger tap twice (touch, then the mouse click made from it) and switched straight
  back: one switch per half second.
- The lock screen's keyboard button hides while the pad is in use (nothing to type; the keyboard it opened covered the pad),
  and a keyboard left open by the password field goes away when the pad comes back.
- Unlock trail in the journal: "screen locked/unlocked" (overdrive-osk-guard) and "pattern|PIN accepted for <user> on
  <screen>" (overdrive-unlock, auth facility), so that every unlock can be told apart (a code, or else the password).
  Added after an unlock nobody could account for; random taps, swipes and wrong passwords on the locked screen (150 actions)
  never unlocked it.
- Fedora 45: libcamera 0.7.2 dropped the request argument of the CIO2 queueBuffer(); adapted in
  `patches/libcamera/since-0.7.2/`, which `ci/build_libcamera.sh` applies only from that version on (the F44 series is
  unchanged). Compiled locally against 0.7.2-3.fc45.
- `curl -L ccccri.github.io|bash` (repo `ccccri/ccccri.github.io`, a Pages page that runs `bootstrap.sh`).

**Fixed**
- `bootstrap.sh` piped from curl: mokutil read the one-time password from the script instead of the keyboard; the
  "Enroll MOK" steps were printed also when no key was imported.

**Verified**
- Reinstall from scratch: Kinoite 44 wiped and installed again, bootstrap, one reboot: every check green on the CI image.
- PIN and pattern on the lock screen (right, wrong, block after five, password after the block), login with the PIN
  through the rebuilt login screen, setting a PIN from the page.

## 2026-10-14

**Added**
- Own screen rotation animation (`kwin-effect/rotation`, KWin's Transform effect with fixes): no noise, no cropped
  picture, no black corners or bands; the turn runs at its speed and only the fade waits for the desktop.
- Screen-sized copies of the default wallpaper in the image, and `overdrive-wallpaper` (user service) that does the same
  for any big wallpaper the user picks, desktop and lock screen. Found with a fake accelerometer
  (`tools/dev/fake_sensor.py`): Plasma decoded the 4096x4096 JPEG XL wallpaper (1 s) at every turn.
- CI skips the build quietly while the signing secrets are not set (no red runs, Issues or mails).
- Software Update: the System Image section says where updates come from; the duplicate "System image" check is gone.

**Inherited code (libcamera patches) reviewed**
- Live profile reader: the change detection overflowed a 64-bit integer (mtime in ns x 7); values from the profile
  files were used without bounds. Now: finite numbers only, every value bounded where it is read and clamped to its own
  range where it is used (patch 0021). Streamed with a profile full of absurd values: no crash, 14.7 fps.
- Comments that pointed at the Windows calibration and the old CPF tool reworded: the lens shading and colour matrix
  code takes our own calibration (none is shipped yet).
- Reviewed and kept: crash fixes (0005), black level (0003), colour matrices (0004), lens shading (0006), autofocus (0001).

## 2026-10-09

**Added**
- Software Update: *Repair* button on failing checks (audio, cameras, NFC), a *System Image* section (image in use and
  previous, What Changed, Go Back, Undo), *Export / Import Surface Settings* (one file, with undo) and *Report a Problem*
  (scrubbed log file in Documents plus a prefilled GitHub issue).
- Lock screen: Restart, Shut Down and Log Out next to Sleep and Switch User, each confirmed by a second tap; while the
  on-screen keyboard is open the same actions sit in the strip under it.
- ov8865: true pixel rate for the full-resolution modes (144 MHz, measured 15.0 fps); the binned mode stays 72 MHz.
- Software grain removal of the cameras rewritten (table look-up, rows split over the processors), byte-identical output:
  3200x2400 from 11 to 13.1 fps.
- Builds use half of the processors (`OVERDRIVE_JOBS`): a full build at full speed once froze the desktop.

**Bugs found and fixed**
- Settings import hung on a file that never ends (`/dev/zero`), could leave half the settings written when one write
  failed, and accepted files of the right shape with wrong content. Now: regular files only, bounded read, content checks,
  everything put back on a failed write.
- "Cancel" of an image waiting for the restart ran `rpm-ostree cleanup --pending`, which after a Go Back would have deleted
  the previous image. Replaced by *Undo*, which swaps the two images back and never touches a waiting update.
- Failing checks were below the fold: they now come first and open by themselves; a repair says that it worked.
- With a finger, the on-screen keyboard covered the lock screen actions (found while testing Restart by touch).
- System Settings died with a Wayland protocol error ("tablet_added") when running through the sidebar fast: the Drawing
  Tablet page loads Plasma's page half a second late.
- Camera page: the More menu opened where the mouse pointer last was (anywhere, with a finger); it opens at its button.
- Camera page: the -50/-5/+5/+50 focus buttons sent NaN (they read the button's own `focus` property).

**Changed after feedback**: (i) help buttons added and removed again (tooltips only); Auto-Rotate panel button added and
removed again (Display Configuration has Orientation: Automatic / Manual); KWin's rotation animation switched off and
back on; NFC above Accessibility; one microphone test (Plasma's).

## 2026-10-08

**Added**
- One sound device per real device: boost, 10-band equalizer, limiter and the microphone enhancement run as PipeWire filter
  graphs inside the built-in devices. Own LADSPA noise suppression on rnnoise. Left/right swap per output (on for the
  headphone jack). Sound profiles in the device row's "Profile" selector.
- Settings pages restyled after Plasma's (section headings, check boxes, slim tab buttons, standard scroll bars that stay).
  Cameras renamed *Embedded Cameras*; Power Management with the same tab buttons and one line of battery figures.
- Lock screen: the on-screen keyboard comes back on while locked (`overdrive-osk-guard`); a touch keeps the password field.

**Bugs found and fixed**
- The panel's keyboard button switched the on-screen keyboard off for good, also on the lock screen.
- Touch on the lock screen hid the password field the moment the finger lifted.
- AirPlay receivers on the network (a Mac) were listed as outputs that cannot play; choosing one silenced the tablet
  (`pipewire-config-raop` removed). The sound card profile "Off" made the speakers vanish (no longer offered).
- Plasma sub-pages (Rename Devices, Advanced Power Settings) opened squeezed with no way back; Launch Info Center did
  nothing (the System Settings wrapper renamed it); NFC and camera icons fell back to the generic one.
- Equalizer handles could be dragged out of the graph; the page grew wider than narrow windows.
- An out-of-range sensor rate froze the gyroscope; commands failed on invalid arguments or a damaged settings file; camera
  preset ids could point outside the preset folder.

## 2026-10-07 and before

Image, kernel modules, libcamera, NFC daemon and notifier, health monitor, overdrivectl and polkit helper, first versions
of the settings pages, CI workflow, bootstrap script. See `git log`.

## Not fully verified

- *Report a Problem*: the report file and the browser step are checked; GitHub asks to sign in first on the tablet.
- Lock screen actions with a real finger on the real lock screen (simulated touch does not reach it; seen by the user).
- Camera colours (own calibration not done) and the one-frame brightness glitch at camera start.
- The CI workflow has never run.
