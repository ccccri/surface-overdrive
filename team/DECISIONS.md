# Decisions

Settled decisions, newest last. Do not reopen one without a new reason; if you change it, add a **new** decision that says
which one it replaces (`Supersedes D-NNN`) and why. `Owner` = the owner decided it, an agent must not change it alone.
Where a decision came from a conversation, the date is when it was said; the details of the work are in `docs/CHANGELOG.md`.

## Principles of the project

**D-001 · 2026-10-06 · Owner — A fresh repository, built as a serious developer would.**
The first version had grown by patches. The old repository (`surface-go-kinoite`) stays as a reference and its facts are hypotheses to be
re-measured, not truths. Measure with numbers (luma per frame, stress runs, benches), not by eye. Choose the best solution, not the easiest.

**D-002 · 2026-10-06 · The tablet builds nothing; CI builds the image.**
A custom bootc image on Kinoite, built by GitHub Actions on every push and daily (`.github/workflows/build-image.yml`): signed kernel
modules, libcamera and PipeWire's libcamera plugin from Fedora's SRPMs with our patches, and small rebuilds of a few Plasma packages. A failure
opens an Issue and is fixed by hand. The tablet takes the result as an ordinary update. Every patched stage **falls back to the stock Fedora
package and says so in the log** when its patch no longer fits: read the CI log after a base update.

**D-003 · 2026-10-06 · Owner — No Microsoft-derived data, anywhere.**
No calibration tables or anything derived from them, in the repository or in the image. Camera calibration is our own, measured (`tools/calib/`).

**D-004 · 2026-10-08 · Owner — Our System Settings pages must look like Plasma's.**
Same tab bars, section headers, check boxes, scroll bars (the standard ones, hidden when not needed); American spelling; explanations as tooltips
only (no text that opens inside the layout); no separator lines or frames that make our addition obvious; no extra "Surface" group (Cameras and NFC sit
under Input & Output, NFC above Accessibility). Icon names must not start with `preferences-` (Breeze then shows the generic icon).

**D-005 · 2026-10-06 · Owner — Language.** Chat with the owner in Italian. Repository, documentation, code, comments, commit messages, UI strings and
the `team/` files in English (American spelling in the UI).

**D-006 · 2026-10-08 · Owner — No code copied from the old repository without audit.**
The audit was made (kernel patches and libcamera 0001-0012 were verbatim or near it and were read line by line; two Python modules were partly kept).

**D-007 · 2026-10-07 · Owner — No Type Cover (keyboard cover) features.** The owner uses the tablet as a tablet. No folio healing, no keyboard/trackpad test page.

**D-008 · 2026-10-06 · Owner — Test as a real user would.**
Installation and repair tests go through polkit/`pkexec` and `sudo` with a password, not through tricks (no disabling sudo, no autologin tricks; a temporary
autologin for a test is removed at once). ssh is for observing and for backups. The owner gives the tablet's temporary password in chat when it is needed;
**it is never written to a file, a commit, a log or a memory** (D-025).

**D-009 · 2026-10-27 · Owner — The repository is public: nothing personal goes in.**
No photos of the owner, no wallpapers made from their photos, no faces, no screenshots of their room (camera tests show it), no addresses. A wallpaper of theirs lives only in
their home directory on the tablet.

**D-010 · 2026-10-28 · Owner — Do not cancel CI runs.**
The queue runs them in order; cancelling produced failure mails. If a run is wrong, push the fix.

**D-011 · 2026-10-28 · Owner — No tablet mode of our own.**
It was built, tried and rejected. Plasma 6.7's behaviour is left stock. Do not propose it again unless they ask.

## Design choices

**D-012 · 2026-10-08 · Sound is filter graphs inside the real device nodes** (`src/overdrive/audio/graph.py`), not virtual devices: boost, equalizer, limiter (LADSPA swh at
the end of the speaker chain: the boost distorted) and the microphone enhancement (our `ladspa/overdrive_denoise.c` on Fedora's rnnoise). No AirPlay outputs. The
headphone jack has left/right swap on by default (the owner hears them exchanged there).

**D-013 · 2026-10-26 · Owner — Our own camera app, not Kamoso.** Hardware encoding (VA-API H.264 + AAC, RPM Fusion's intel-media-driver, Cisco's openh264). The app uses
the QML of Plasma Camera with small stand-ins for its C++ backend (`src/overdrive/camera_ui`); the owner did not want it rewritten from scratch. Quality is always
maximum, no selector.

**D-014 · 2026-10-26 · The rear camera stays at 15 fps in full resolution.** The sensor's 30 fps modes (288 MHz, other MIPI dividers) gave broken lines or no frames; abandoned.

**D-015 · 2026-11-04 · Front camera in low light: "darker but clean".** Chosen with the owner; automatic night mode with a switch was discussed. Grain is acceptable for now (2026-11-16).

**D-016 · 2026-11-06 · Firefox:** voice search is a system extension that opens Google's own voice search directly (`docs/voice-search-amo.md`); no Fedora start page and no
Fedora bookmarks (policies.json), only the project's repository pinned.

**D-017 · 2026-11-13 · Streaming to/from the owner's PC (Sunshine, Moonlight, Tailscale) is a separate project.** The image carries none of it.

**D-018 · 2026-11-16 · Owner — Camera pause when hidden is merged** (the app stops the camera while its window is minimised or the screen is locked).

**D-019 · 2026-11-16 · Owner — NFC tag contents may stay in the journal** (visible to administrators only) **but must not go into any log that leaves the tablet**
(the problem report scrubs them).

**D-020 · 2026-11-16 · Owner — The on-screen keyboard is Plasma's own keyboard plus our additions**, not an application of ours. Same size and look as stock, never taller than
the docked keyboard; no scale/opacity buttons; a menu on holding the space bar; slide on the space bar moves the cursor; the extra keys, clipboard and emoji; a floating mode (moved,
sized in both directions with sensible limits) and a split one for the thumbs. Its code is one patch (`patches/plasma-keyboard/`). A first Python prototype was tried and rejected.

**D-021 · 2026-11-17 · The floating keyboard is a window of its own** (layer shell, overlay), because KWin always places an input panel at the bottom centre and moves the
focused window away from it. On the lock screen the keyboard is always the docked one, without clipboard, Settings and Float (whoever holds a locked tablet has the keyboard).

**D-022 · 2026-11-17 · Camera sharpening is split over the processors and vectorised** (libcamera 0049), output unchanged. Replaces nothing; read the patch's message for the numbers.

## How agents behave

**D-023 · 2026-11-16 · Owner — Permissions and security are the owner's.** Granting permissions, accepting terms, deleting data and changing security settings need their
yes in chat. An agent does not unlock the tablet's lock screen itself, does not try its PIN or pattern, does not disable its auto-lock, and does not run `mokutil --import` on the PC.

**D-024 · 2026-11-16 · Owner — Night work is silent and dark.** When working while they sleep in the room: screen brightness 0, audio muted, no camera (its LED), no loud fan load, the
tablet not left to run flat (they do not charge it at night because the charger has a light). Respect any stop time they give.

**D-025 · 2026-11-19 · Owner — Nothing secret in the repository, ever.** Passwords (the temporary one for the tablet included), PINs, unlock patterns, tokens, keys, private addresses.
`tools/handoff.py end` scans the notes and changed files. If one slips into a commit, tell the owner at once (history is public).

**D-026 · 2026-11-19 · Owner — Two agents, one at a time.** Claude Code and OpenCode take turns on their requests; the repository (`AGENTS.md`, `team/`) is the shared memory, private agent memories are
not. This layout is the same as in the WOA project on purpose.

**D-027 · 2026-11-19 · Owner — The two-agent workflow is the standard in every project, and its tool is one shared copy.**
Every project of the owner gets `AGENTS.md`, `CLAUDE.md`, `opencode.json`, `team/` and `tools/handoff.py`, so that work can pass between Claude Code and OpenCode (partly to spend fewer credits/tokens).
The reusable template and the scaffold script live in `~/.claude/skills/team-handoff/` (outside this repository); standing rules for both agents are in `~/.claude/CLAUDE.md` and `~/.config/opencode/AGENTS.md`.
`tools/handoff.py` here is that template's copy: project differences are in `team/handoff.json`. Fix bugs in the template and copy them (`scaffold.py --update-tool`). Mark mechanical tasks `[opencode-ok]` in `STATUS.md`.
