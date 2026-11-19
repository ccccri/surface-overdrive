# AGENTS.md — Surface Overdrive

This file is the shared instruction manual for **every AI agent** working on this repository.
Two agents work on Surface Overdrive as a team, **taking turns** on the owner's requests:

- **Claude Code** (reads `CLAUDE.md`, which imports this file)
- **OpenCode** (reads this file directly, plus the files listed in `opencode.json`)

Everything an agent needs to know lives **inside this repository**. Agent-private memories (Claude's
`~/.claude/...`, OpenCode's session history) are not shared, so never rely on them alone: if something
matters for the project, write it in `team/`. The layout is the same as in the owner's WOA project
(`~/Claude/woa`) on purpose.

---

## 1. Start here (every session, before touching anything)

```sh
cd ~/Claude/surface-overdrive
python3 tools/handoff.py start --agent <claude|opencode>
```

It prints the status, the last handoff note, the commits made since that note and any uncommitted changes, and
marks you as the active agent. Then read, in this order:

1. `team/STATUS.md` — where the project is, the task list (T-NN), what is next, what is unverified.
2. The top entry of `team/LOG.md` — what the previous agent did and left for you.
3. `team/DECISIONS.md` — settled decisions (D-NNN). Do not reopen them without a new reason; supersede, do not edit.
4. `team/CONTEXT.md` — the owner, the hardware, the machines and how to reach them, words, references.
5. `team/KNOWLEDGE.md` — **before touching the tablet, the image, the cameras, the keyboard or a build**: what is known and what has gone wrong.
6. `team/ARCHITECTURE.md` — the code map. `docs/ARCHITECTURE.md` section 0 and `docs/FEATURES.md` for the bigger picture; `docs/CHANGELOG.md` for the history.
7. `team/USER_STEPS.md` — what only the owner can do.

If `start` warns that the other agent is still active or left uncommitted work, **stop and tell the owner** instead of overwriting it.

## 2. Finish here (every session, before answering for the last time)

1. Run the tests: `PYTHONPATH=src python3 -m unittest discover -s tests` (must pass).
2. Update `team/STATUS.md` (task list, "Next step", "Where things stand", "Unverified", **Last updated**).
3. Add a new entry **at the top** of `team/LOG.md` (template inside). Say exactly what was *tried on the tablet*, what was only *tested*, *read* or *not verified*.
4. Add to `team/DECISIONS.md` any decision you or the owner made, with the reason. Add lessons to `team/KNOWLEDGE.md`, durable facts to `team/CONTEXT.md`.
5. If the change is visible to the owner, add it to `docs/CHANGELOG.md` (today's heading, newest first) and, if a feature changed, `docs/FEATURES.md`.
6. Run `python3 tools/handoff.py end --agent <claude|opencode>`; it runs the tests, checks the log and the status, scans for secrets, and releases the lock.
7. Commit (see §6) and push when the work is meant to reach the tablet.

A turn is not finished until the log entry is written: the other agent cannot ask you questions. If you must stop in the middle, still write the entry
(say "unfinished", what state the files are in, and the next command to run) rather than leave nothing.

## 3. Language rules (from the owner, mandatory)

- **Chat with the owner: Italian.**
- **Everything in the repository is English**: code, comments, commit messages, docs, `team/` files, UI strings (American spelling in the UI).
- Refer to the owner as "the owner" or "they": no pronoun was ever given.

## 4. What the project is

Hardware fixes, a system image and System Settings pages for **one Microsoft Surface Go (1824)** running **Fedora Kinoite 45** with Secure Boot on, used as a tablet.
It is the owner's personal project: not for other models or other users (`README.md`). CI builds the image (`ghcr.io/ccccri/surface-overdrive:45`) on every push to
`main` and daily; the tablet follows it with `rpm-ostree upgrade`. It contains: signed patched kernel modules (cameras, NFC, volume buttons), libcamera rebuilt with our patch
series and our own calibration (no Microsoft data), a camera application with hardware video encoding, settings pages (cameras, NFC, sound with boost/equalizer/microphone
suppression, pen, sensors, power, lock screen with PIN/pattern, software update with a health monitor and repairs), Plasma's on-screen keyboard with our additions, and small Plasma patches.

Where to read more: `README.md`, `docs/FEATURES.md` (what exists and what is open), `docs/ARCHITECTURE.md`, `team/ARCHITECTURE.md` (map of the code), `docs/CHANGELOG.md`.
Repo: https://github.com/ccccri/surface-overdrive (**public**), local path `~/Claude/surface-overdrive`.

## 5. Repository map (short; the full one is `team/ARCHITECTURE.md`)

| Path | What |
| --- | --- |
| `AGENTS.md`, `CLAUDE.md`, `opencode.json` | Agent rules, Claude Code entry point, OpenCode config (auto-loads `team/STATUS.md`) |
| `team/` | **Shared project memory**: status, log, decisions, context, knowledge, architecture, owner's steps |
| `tools/handoff.py` | Session start/end helper for the agent handoff |
| `Containerfile`, `.github/workflows/`, `ci/` | The image build and CI; `ci/patch_*.py` edit Plasma sources, `ci/build_*.sh` rebuild RPMs |
| `patches/{kernel,libcamera,pipewire,plasma-keyboard}/` | Our patches to other projects, each explained |
| `src/overdrive/` | The Python runtime: `overdrivectl`, services, health checks, camera app, audio |
| `kcm/` | System Settings pages (C++/QML) |
| `image/rootfs/` | Files shipped as they are (units, udev, launchers, config) |
| `installer/`, `bootstrap.sh` | The first install |
| `tests/` | Unit tests (`unittest`, no pytest, no network, no tablet) |
| `tools/dev/`, `tools/calib/` | Device tools, benches, the keyboard dev loop, camera calibration |
| `docs/` | Human documentation; `CHANGELOG.md` is the daily record |

## 6. Working rules

- **One agent at a time.** The owner alternates requests between agents. Do what the request asks plus the bookkeeping in §2; leave other ideas as tasks in `team/STATUS.md`.
  Do not start sub-agents or long background jobs without need, and stop what you started (containers, test apps on the tablet).
- **Done means checked.** The standard of this project: after you think a task is finished, re-check it, repeat the test, look for the bug you did not think of, and say honestly what was
  *tried on the tablet*, what was only *tested by unit tests*, what was *read* and what is *not verified*. `docs/CHANGELOG.md` uses the same words ("Verified" = tried on the Surface itself).
- **The repository is public. No secrets, no personal data, ever** (D-009, D-025): no passwords (the tablet's temporary sudo password included), PIN, unlock pattern, tokens, keys, private addresses,
  no photos of the owner or their room, no screenshots from the cameras. `tools/handoff.py end` scans for the usual patterns; it does not replace care. If something slipped into a commit, tell the owner at once.
- **The tablet and the PC are the owner's.** Look at what is happening before acting on a device (is the owner using it? is the battery low?). Do not restart, charge, unlock, change security or sleep
  settings, delete the owner's files, grant permissions, accept terms, or create accounts without their yes in chat (D-023). Never type or try the owner's PIN or pattern. Test deployments go to the
  `ostree admin unlock` overlay and vanish at restart: say so. Night work is silent and dark (D-024). Never touch the PC's fans, RGB lighting, webcam or the Flipper.
- **No Microsoft-derived calibration data** (D-003). No Type Cover features (D-007). No tablet mode of our own (D-011).
- **Do not cancel CI runs** (D-010); push the fix instead. Read the CI log for `skipped:`/`warning:` lines after a base update (`team/KNOWLEDGE.md` §3).
- **Tests first-class.** A behaviour change in `src/` or a `ci/patch_*.py` needs a unit test. Tests run with plain `unittest` and need neither the tablet nor the network.
- **Commits:** small, English, imperative subject, task id in it when there is one (`... (T-08)`). Use `git add` for the files you mean (the working tree may hold the owner's or the other agent's unfinished work).
  End the message with a trailer naming the agent and model, e.g. `Co-Authored-By: Claude (<model>) <noreply@anthropic.com>` or `Co-Authored-By: OpenCode (<model>) <noreply@opencode.ai>`.
  Commit and push to `main` are allowed when the work is meant to reach the tablet (CI builds from `main`); experiments and betas go on a branch `beta/<name>`, off by default in the image.
  Never rewrite pushed history (`push --force`, `reset --hard`, rebase of pushed commits).
- **When docs and code disagree, fix the docs** in the same turn.
- **Honesty about what you read.** Facts from the web or from your memory of other software must be checked against the source before they go into a patch; note the source in the commit or the decision.

## 7. Commands

```sh
PYTHONPATH=src python3 -m unittest discover -s tests          # unit tests (about 250, a few seconds)
python3 tools/handoff.py start --agent claude                  # begin a turn
python3 tools/handoff.py end   --agent claude                  # end a turn (checks + unlock)
python3 tools/handoff.py status                                # read-only summary

gh run list -L 5                                               # CI; add `gh run view <id> --log | grep -E "warning: |skipped: |patched: "`
overdrivectl status -v                                         # on the tablet: the health checks with explanations

tools/dev/keyboard-dev.sh setup|build|export|deploy            # the on-screen keyboard's loop (see its header)
ci/build_libcamera.sh <nvr> patches/libcamera /out/rpms        # libcamera with our patches, in a fedora:45 container
. tools/dev/tablet-env.sh                                      # (on the tablet, over ssh) the graphical session's environment and `shot`
```

How to reach the tablet, how to test on it and what not to do: `team/CONTEXT.md` ("Machines and access") and `team/KNOWLEDGE.md` §1-2.

## 8. Code conventions

- Python 3.15 (tablet and PC); standard library only in the runtime unless the image already ships the module (PySide6, GStreamer for the camera app). Modules take their dependencies as arguments so tests can inject fakes.
- Settings pages follow Plasma's look exactly (D-004); backend through `overdrivectl`; long-running readers are one process that ends with the page.
- A patch to another project is **one logical change with a message that says why and gives the measurements**; patchers refuse (skip) rather than guess when the source differs.
- A beta is off by default and enabled by a command; it goes on a `beta/*` branch until the owner has tried it.
- Never log secrets or personal data; NFC tag contents stay out of logs that leave the tablet (D-019).
- Comments say *why*, not what. Keep functions small enough to test.
