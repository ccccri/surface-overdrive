# Project status

**Last updated:** 2026-11-19 by claude
**Phase:** in daily use on the owner's tablet; development goes on in small steps, the owner tests and reports

The image `ghcr.io/ccccri/surface-overdrive:45` is built by CI on every push to `main` and every day; the tablet takes it as a
normal Kinoite update (`sudo rpm-ostree upgrade`, then a restart). What exists is listed in `docs/FEATURES.md`, what changed and
why in `docs/CHANGELOG.md` (newest first, one entry per day, every claim marked as tried on the Surface or not).

## Next step

The tablet was **off or out of reach from 2026-11-17 05:00 (battery at 27 %, the owner does not charge it at night because of the
charger's light)**. When it is back, the owner does `team/USER_STEPS.md` step 1 (update, restart). Until then agents can work on
code, patches, tests and CI, but nothing can be tried on the device. Useful in that case: T-12, T-15, T-16, T-17.

## Where things stand (2026-11-19)

- `main` is at the commit named in the top log entry; CI of 2026-11-17 13:26Z is green and built the image with everything below.
- **On-screen keyboard** (T-01, done): Plasma's own keyboard rebuilt with our patch (`patches/plasma-keyboard/`), tried on the
  tablet with a virtual finger (typing, menu, extra keys, clipboard, emoji, floating, split, Italian layout, terminal, Firefox).
  Never seen: the lock-screen behaviour, the digits page of the extra row, XWayland apps.
- **Camera sharpening** (T-02): libcamera patch 0049 makes it 11x cheaper (30 ms to 2.7 ms at 2560x1920, byte-identical output,
  tested by a bench). Whether it removes the camera stall of 2026-11-11 is **not tried**.
- **Plasma 6.8.3** is in the image since 2026-11-16: seven of eight of our settings pages were opened and are fine.
- **Beta branch** `beta/auto-brightness` (T-08): automatic brightness from the light sensor; not on `main`.
- The tablet itself: last known on image 45.20261116.0 with a hand-made test overlay (lost at restart), a newer image downloaded
  and waiting for a restart. After a restart it has the 2026-11-17 image.

## Tasks

Status: `[x]` done · `[ ]` to do · `[~]` in progress · `[!]` blocked. Owner: `user`, `agent` (either agent) or a specific agent.
IDs are never reused: refer to them in log entries and commit messages (`git log --grep T-05`).

### Waiting for the user
- [ ] T-03 user — Update and restart the tablet, then try the keyboard, esp. on the lock screen (`team/USER_STEPS.md` 1 and 2).
- [ ] T-04 user — Camera stall test in daylight with sharpness above zero (`team/USER_STEPS.md` 3).
- [ ] T-05 user — List of the KDE settings they want as defaults of the image (feature #28 in `docs/FEATURES.md`); nothing to do until they send it.
- [ ] T-06 user — Publish the Firefox voice search extension on addons.mozilla.org (`docs/voice-search-amo.md`).

### To do (agents)
- [ ] T-07 agent — Look by eye, on the tablet, at the patched parts of Plasma 6.8.3: lock screen, desktop edit hold, Force Quit in the
      task manager, Brightness popup, Discover (the settings pages are done). The CI log says which patches applied (`patched:` / `skipped:` lines).
- [~] T-08 agent — Beta `beta/auto-brightness`: try it by day on the tablet (`overdrivectl brightness auto dry`, then `on`), look at the curve
      against real rooms and at Plasma's idle dimming, add a switch to a settings page, then ask the owner whether it goes to `main`.
- [ ] T-09 agent — Front camera in low light: grain (owner: acceptable for now, do not spend time unless asked).
- [ ] T-10 agent — Keyboard in XWayland apps: they cannot make the keyboard appear (owner: only if cheap).
- [ ] T-11 agent — Lock screen media player look (owner: "later, much later").
- [ ] T-12 agent — Explain why one late frame stops a camera for good instead of costing one frame (libcamera IPU3 pipeline, `Request ... never completed`, then
      `CIO2 buffer underrun`; reproduction `tools/dev/camera_sharp_stall.sh`). Reading and a log-only build are possible without the tablet.
- [ ] T-13 agent — Research tablet features worth building (the owner asked for it on 2026-11-16; not done). Write candidates in `team/CONTEXT.md`
      "Ideas", cheap and useful first; examples already known: automatic brightness (T-08), scan-to-text with the rear camera, pen shortcuts, a
      per-app on-screen keyboard layout, battery care limits if the firmware allows them.
- [ ] T-14 agent — Health monitor: repairs now exist for audio, cameras, NFC, pen battery filter, volume hold. The other checks keep an explanation only, by
      design (what mends them is another image or a restart).
- [ ] T-15 agent — Housekeeping: `RIPRISTINO.md` lists what the reset of 2026-11-02 left (broken symlinks in `build/`, venvs to redo, `build-dal-duplicato/`
      24 GB of capture data on the PC: ask before deleting anything there).
- [ ] T-16 agent — When Fedora ships another `plasma-keyboard` version the patch may stop applying: CI then installs Fedora's stock keyboard and says
      `warning: the keyboard patch does not apply` in the log. Check the log after a Plasma update (`tools/dev/keyboard-dev.sh` rebases it: set `PK_TAG`).
- [ ] T-17 agent — Read the libcamera patches not yet read line by line (0001 AF scan, 0003 BLC, 0004 CCM, 0005 crash fixes, the LiveProfile reader,
      the rest of 0028).

### Done (recent)
- [x] T-01 claude — On-screen keyboard: Plasma's own plus our additions (2026-11-16/17).
- [x] T-02 claude — libcamera 0049: sharpening in bands and SSE2 (2026-11-17).
- [x] T-18 claude — Two more repair buttons (pen battery filter, volume hold); PySide6 installed by name in the image (Fedora dropped it).
- [x] T-19 claude — Team workflow for Claude Code and OpenCode: `AGENTS.md`, `team/`, `tools/handoff.py` (2026-11-19).

## Unverified assumptions (check before relying on them)

- Patch 0049 removes the camera stall (T-02/T-04). Only the cost of sharpening was measured.
- On the lock screen the keyboard has no clipboard, no Settings and no floating mode: by code and a test of the patch, never seen.
- Plasma's idle dimming appears as a changed brightness that the beta leaves alone (T-08): assumed from the code, not seen.
- The keyboard's digits page (Fn pressed once) was written last and never looked at.

## Risks

- A new Fedora base can break any patch stage; each stage falls back to the stock package and says so in the CI log: read the log after a base bump.
- The tablet can be left on a hand-made overlay that vanishes at restart: after a restart check `rpm -q plasma-keyboard` (must end `.overdrive1`), `python3 -c "import PySide6"`.
- The tablet discharges when left on at night: ask before long tests, and look at the battery (`/sys/class/power_supply/BAT1/capacity`).
