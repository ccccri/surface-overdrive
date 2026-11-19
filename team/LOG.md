# Session log

One entry per agent turn, **newest first**. Never edit or delete old entries (append a
correction in a new entry instead). `tools/handoff.py` reads the top entry. History before
2026-11-19 is in `docs/CHANGELOG.md` and `git log`; the entries below start from the day this
log was made and summarise the three days before it.

Template (copy it to the top, below this header block):

```
## YYYY-MM-DD — <claude|opencode> — <short title>
**Request:** what the user asked (one or two lines, English).
**Done:** what changed and why; list touched files/areas.
**Verified:** tests run and results; what was tried on the tablet and what only by reading.
**Not done / open:** anything left, unverified, or blocked; questions for the user.
**Next:** the single most useful next step (agent or user).
```

Be exact about "verified": say *tried on the tablet*, *tested by the unit tests*, *by reading the code*, or *not verified*.

<!-- entries below -->

## 2026-11-19 — claude — The workflow becomes the standard for every project
**Request:** Make this method (copied from the WOA project) the standard for every project and every Claude Code session, so that work can go to OpenCode in parallel and credits/tokens are saved.
**Done:** `tools/handoff.py` made project-independent (optional `team/handoff.json`: test command/environment, extra secret patterns, skipped paths, STATUS size limit with a warning; AWS key pattern added) and
copied to the reusable template; new skill `~/.claude/skills/team-handoff/` (SKILL.md, `scaffold.py`, `template/` with AGENTS.md, CLAUDE.md, opencode.json, team/*, tools/handoff.py, a generic test); standing rules for Claude Code in
`~/.claude/CLAUDE.md` and for OpenCode in `~/.config/opencode/AGENTS.md`; a memory note for Claude. Decision D-027. This repository's `team/handoff.json` now carries what was hard-coded.
**Verified:** the scaffold was run on an empty directory and `start`/`end` worked there (the generic tests passed, `end` correctly refused without a log entry); this repository's 258 tests pass with the generalised tool;
a real OpenCode session started in an empty directory answered from the global `AGENTS.md` (the rules, the start command, what to do in a project without `team/`). Not done: retrofitting the other projects (`~/Claude/*`):
by design they get it when the owner brings them up; WOA already has an older copy of the tool (works the same, can be updated with `scaffold.py --update-tool`).
**Not done / open:** the template files outside this repository are not versioned; if the owner wants them in git, make `~/.claude/skills/team-handoff` a repository.
**Next:** unchanged: T-03 (owner brings the tablet back), then T-04/T-07.

## 2026-11-19 — claude — Team workflow for Claude Code + OpenCode
**Request:** From now on Claude Code and OpenCode alternate on this project (the owner sends the next request to one or the other).
The repository must hold everything an agent needs, explained as completely as possible, plus a way to pass on what was changed,
what is left and the shared project memory.
**Done:** Same layout as the owner's WOA project (`~/Claude/woa`), so that both projects work the same way: `AGENTS.md` (rules, read
by OpenCode), `CLAUDE.md` (imports it and `team/STATUS.md`), `opencode.json` (loads `team/STATUS.md`), `team/` (STATUS, LOG, DECISIONS,
CONTEXT, ARCHITECTURE, USER_STEPS, KNOWLEDGE, README), `tools/handoff.py` (start/end/status, lock file `team/.active`, test run,
log check, secret scan) with `tests/test_handoff.py`. The durable content of Claude's private memory for this project (about 60 KB of
dated notes) was sorted into DECISIONS, CONTEXT and KNOWLEDGE, **leaving out everything private** (passwords, PIN, unlock pattern,
addresses, personal photos): the repository is public. Also new: `tools/dev/keyboard-dev.sh` (the keyboard's development loop,
tried from an empty directory: setup, build, export gives back the committed patch byte for byte) and `tools/dev/tablet-env.sh`.
**Verified:** unit tests (all pass, `tests/test_handoff.py` is new); the keyboard script round trip described above; `opencode debug config`
reads `opencode.json`; a real OpenCode session (model "big-pickle", a read-only question) answered with the right start command, reading order, next step
and language rules from these files and changed nothing. Not seen: an OpenCode session doing a whole turn (start, work, end).
**Not done / open:** the tablet is out of reach, so nothing of the earlier open items (T-03 to T-07) moved. The dated memory notes of
Claude stay where they are as history; only the repository is the source of truth from now on.
**Next:** the owner brings the tablet back (`team/USER_STEPS.md` 1). Meanwhile an agent can take T-12 or T-16.

## 2026-11-17 — claude — Night session: keyboard finished, camera sharpening, repairs, beta
**Request:** Work through the night (owner asleep, tablet dark and silent, until 08:59): continue the project, re-check what is done,
fix the rear camera's stall if possible, try Plasma 6.8.3, build repairs and a beta.
**Done:** Keyboard: layout switches also in its settings page, a digits page in the extra row, no clipboard/Settings/Float on the lock
screen, split only in landscape (commits 55d2337, 7f9dc7f, a08645b). libcamera patch 0049 (sharpening 30 ms to 2.7 ms), bench
`tools/dev/sharpen_bench.cpp`, repro `tools/dev/camera_sharp_stall.sh`. Repairs for the pen battery filter and the volume hold. Beta branch
`beta/auto-brightness`. Seven settings pages opened on Plasma 6.8.3. CHANGELOG entries for all of it.
**Verified:** on the tablet with a virtual finger: the keyboard in KWrite, Konsole (Ctrl+C, up arrow), Firefox's address bar, the settings
page and its Split switch, the pages of the settings; the two repairs ran as root with status 0. By the bench: sharpening identical byte for
byte. By tests: 250 unit tests. Not tried: the camera stall itself, the lock-screen behaviour, the digits page.
**Not done / open:** the tablet's battery ran out around 05:00 before the owner woke; the stall fix, the lock screen and the beta need daylight.
**Next:** T-03 and T-04 (owner), T-07 and T-08 (agent).

## 2026-11-16 — claude — On-screen keyboard rebuilt on Plasma's own; PySide6 and guard fixes
**Request:** Keep Plasma's keyboard (size and look), add the extra keys, clipboard, emoji, a floating and a split mode, a menu on holding the
space bar; drop the Python prototype.
**Done:** `patches/plasma-keyboard/0001-overdrive-keyboard.patch`, `ci/build_keyboard.sh`, the `keyboard` stage of the Containerfile. The prototype
`overdrive/osk/` was removed: its package hid the module `overdrive/osk.py` of the lock-screen keyboard guard (`tests/test_launchers.py` now
guards that). Fedora's base image dropped PySide6 with Plasma 6.8.3: the Containerfile installs it by name.
**Verified:** on the tablet with a virtual finger (see `docs/CHANGELOG.md` 2026-11-16 and 2026-11-17 for the list). The CI image build includes the patched RPMs.
**Not done / open:** see the 2026-11-17 entry.
**Next:** see the 2026-11-17 entry.
