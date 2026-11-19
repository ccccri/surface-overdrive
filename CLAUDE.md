# CLAUDE.md

Claude Code entry point. The shared rules for all agents (Claude Code and OpenCode) are in
`AGENTS.md`; the shared project memory is in `team/`. Follow them exactly.

@AGENTS.md
@team/STATUS.md

## Claude Code specifics

- Begin each turn with `python3 tools/handoff.py start --agent claude` and end it with
  `python3 tools/handoff.py end --agent claude` (see AGENTS.md §1-§2).
- Claude's private memory (`~/.claude/projects/-var-home-cri/memory/surface-forge-project.md` and
  `surface-forge-working-rules.md`) is **history**: the repository is the source of truth from 2026-11-19. Write
  project knowledge in `team/`, never only in private memory. Memory may still hold things that are not project
  knowledge (how the owner likes to work with Claude).
- Commit trailer: the one your harness asks for (`Co-Authored-By: Claude <model> <noreply@anthropic.com>` and the
  session line); the handoff tool prints the generic form.
- Temporary files go in the scratchpad directory of the session, not in `/tmp` and not in the repository. The scratchpad
  is wiped by a reboot: anything worth keeping goes into `tools/` or `team/`.
- The tablet's temporary password is read from the conversation by a helper that lives in the scratchpad and prints nothing:
  never put it, or the helper, in the repository (D-025).
- Language: chat in Italian, repository in English (D-005).
