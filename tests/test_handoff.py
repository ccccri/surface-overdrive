"""The agents' handoff tool (tools/handoff.py): what it reads from the notes and what it refuses to let into a public repository."""
import importlib.util
import os
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
spec = importlib.util.spec_from_file_location("handoff", os.path.join(ROOT, "tools", "handoff.py"))
handoff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handoff)


class Entries(unittest.TestCase):
    def test_entry_header(self):
        date, agent, title = handoff.parse_entry_header("## 2026-11-19 — claude — Team workflow")
        self.assertEqual((date, agent, title), ("2026-11-19", "claude", "Team workflow"))
        self.assertEqual(handoff.parse_entry_header("## not an entry"), (None, None, None))

    def test_the_real_notes_are_readable(self):
        """The files the tool reads exist in the shape it expects: a top log entry, a 'Last updated' line, a 'Next step' section."""
        header, entry = handoff.top_log_entry()
        date, agent, _ = handoff.parse_entry_header(header)
        self.assertTrue(date and agent in handoff.AGENTS, header)
        self.assertIn("**Request:**", entry)
        updated, by = handoff.last_updated()
        self.assertTrue(updated and by in handoff.AGENTS)
        self.assertTrue(handoff.status_section("Next step"))

    def test_task_and_decision_ids_are_not_reused(self):
        import re
        status = handoff.read(handoff.STATUS)
        tasks = re.findall(r"^\s*- \[[ x~!]\] (T-\d+)", status, flags=re.M)
        self.assertEqual(len(tasks), len(set(tasks)), "a task id appears twice")
        decisions = re.findall(r"^\*\*(D-\d+) ", handoff.read(os.path.join(handoff.TEAM, "DECISIONS.md")), flags=re.M)
        self.assertEqual(len(decisions), len(set(decisions)), "a decision id appears twice")
        self.assertEqual(decisions, sorted(decisions))


class Secrets(unittest.TestCase):
    def hits(self, text):
        return handoff.scan_text("x.md", text)

    def test_what_must_not_get_in(self):
        for line in (
            "echo 'hunter2hunter2' | sudo -S true",
            "password: Tr0ub4dor3",
            "PIN = 482913",
            "the token=abc123def456",
            "ghp_" + "a" * 36,
            "-----BEGIN OPENSSH PRIVATE KEY-----",
            "Authorization: Bearer abcdefghijklmnop",
            "a synthetic key " + "Ab1" * 12,          # invented for this test: capitals, small letters and digits, 36 long
        ):
            self.assertTrue(self.hits(line), line)

    def test_what_may(self):
        for line in (
            "The temporary password is never written down.",
            "password: never",
            "PIN: ask the owner",
            "commit 6318421fa0bd03fb4d2c1c4be6dd3e49cfe6f301 and 0039-ipu3-hardware-temporal-denoise-in-still-scenes.patch",
            "sudo -S -p '' bash -c 'ls'",
            "echo password 1234 team-allow-secret",
        ):
            self.assertFalse(self.hits(line), line)

    def test_notes_of_the_repository_are_clean(self):
        notes = ["AGENTS.md", "CLAUDE.md"] + sorted("team/" + n for n in os.listdir(handoff.TEAM) if n.endswith(".md"))
        self.assertEqual(handoff.scan_secrets(notes), [])


class Setup(unittest.TestCase):
    def test_lock_file_is_ignored_by_git(self):
        with open(os.path.join(ROOT, ".gitignore")) as f:
            self.assertIn("team/.active", f.read().split())

    def test_agent_files_exist_and_point_at_the_notes(self):
        for name in ("AGENTS.md", "CLAUDE.md", "opencode.json"):
            self.assertTrue(os.path.exists(os.path.join(ROOT, name)), name)
        with open(os.path.join(ROOT, "CLAUDE.md")) as f:
            claude = f.read()
        self.assertIn("@AGENTS.md", claude)
        self.assertIn("@team/STATUS.md", claude)
        import json
        with open(os.path.join(ROOT, "opencode.json")) as f:
            self.assertIn("team/STATUS.md", json.load(f)["instructions"])


if __name__ == "__main__":
    unittest.main()
