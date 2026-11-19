# team/ — shared project memory

Claude Code and OpenCode take turns on this project: the owner sends the next request to one or the other. Neither can see the other's chat or private memory, so
**this folder is the memory of the project**. The rules are in `../AGENTS.md`. The same layout is used in the owner's WOA project (`~/Claude/woa`).

| File | Purpose | When to update |
| --- | --- | --- |
| `STATUS.md` | Where the project stands, next step, task list (T-NN), unverified assumptions, risks | Every turn |
| `LOG.md` | Journal of agent turns, newest first: request, done, verified, open, next | Every turn (new entry at the top) |
| `DECISIONS.md` | Settled decisions (D-NNN) with reasons; the owner's decisions are marked | When you or the owner decide something |
| `CONTEXT.md` | The owner, the hardware, machines and access, words, ideas, references | When you learn something durable about them |
| `KNOWLEDGE.md` | Technical lessons, recipes and traps by subject (devices, builds, cameras, audio, pages, lock screen, KWin) | When something cost you time, or turned out wrong |
| `handoff.json` | Settings of `tools/handoff.py` (test environment, directories the secret scan skips, STATUS size limit) | Rarely |
| `ARCHITECTURE.md` | The code map: what lives where, flows, where to change what | When code layout or behaviour changes |
| `USER_STEPS.md` | Plain steps only the owner can do (update the tablet, try things, publish, decide) | When a step changes or a new one appears |

The older, human-facing documents stay where they are: `../docs/CHANGELOG.md` (the daily record of what changed and what was tried on the Surface),
`../docs/FEATURES.md`, `../docs/ARCHITECTURE.md`, `../docs/TEST-RESULTS.md`.

## The turn

```sh
python3 tools/handoff.py start --agent <claude|opencode>   # status, last log entry, commits and changes since it; takes the lock
# ... work, in small steps, committing as you go ...
python3 tools/handoff.py end   --agent <claude|opencode>   # tests, log and status check, secret scan; releases the lock
git add <your files> && git commit                          # with the agent trailer; push when it is meant to reach the tablet
```

The lock is `team/.active` (git-ignored). If a turn ended without `end` (a crash, the owner closed the session), the next `start` says so and refuses until you pass `--force`
after looking at `git status` and `git diff`: the unfinished work is somebody's, keep it, finish or park it, and say so in your log entry.

## How to write the notes so that the next agent can use them

- **Say what is true, with its evidence**: "tried on the tablet with a virtual finger: X" beats "works". Mark everything that was only read, only unit-tested, or not run.
- **Name the next command**, not just the next idea. An unfinished turn gets an entry too ("unfinished: the tree has an uncommitted change in ..., run ... to continue").
- **Keep IDs**: tasks `T-NN` and decisions `D-NNN` are never reused; mention them in log entries and commit messages (`git log --grep T-08` finds the history).
- **Move lessons to KNOWLEDGE.md**, tasks to STATUS.md, decisions to DECISIONS.md: LOG.md is a journal and gets long, the others are what the next agent actually reads first.
- **Never write a secret** (D-025). The end check scans `team/`, `AGENTS.md`, `CLAUDE.md` and every changed file; a line that must mention such a thing on purpose carries the word `team-allow-secret`.
- Don't paste long logs; put the decisive lines and the command that produced them.

## When the two agents disagree or the owner contradicts a note

The owner's words in chat win over every file here; write the new fact down (a new decision that supersedes the old one). If two notes disagree and you cannot tell which is right,
check the code or the device, fix the note, and say in your log entry what you corrected.
