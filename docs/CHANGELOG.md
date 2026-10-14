# Changelog

What was added, what broke, and what fixed it. Newest first. "Verified" means tried on the Surface Go itself.

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

- *Report a Problem*: the report file is checked; opening the browser and attaching it on GitHub were not tried.
- Lock screen actions with a real finger on the real lock screen (simulated touch does not reach it; seen by the user).
- Camera colours (own calibration not done) and the one-frame brightness glitch at camera start.
- Rotation: the animation shows garbage in the newly exposed area; not fixed.
- The CI workflow has never run.
