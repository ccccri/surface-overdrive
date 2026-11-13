import importlib.util
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("install", ROOT / "installer" / "install.py")
install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install)


class ProgressTest(unittest.TestCase):
    def feed(self, *lines):
        p = install.Progress()
        for line in lines:
            p.feed(line)
        return p

    def test_layers_and_sizes_add_up(self):
        p = self.feed("LOG Pulling manifest: x", "LOG ostree chunk layers already present: 3",
                      "LOG ostree chunk layers needed: 40 (1.6 GB)", "LOG custom layers needed: 12 (1.1 GB)")
        self.assertEqual(p.needed_layers, 52)
        self.assertEqual(p.present_layers, 3)
        self.assertAlmostEqual(p.total, 2.7e9)
        self.assertEqual(p.step, "Downloading the image")

    def test_fetched_layers_count_once_and_raise_the_percentage(self):
        p = self.feed("LOG ostree chunk layers needed: 2 (200 MB)", "LOG Fetching ostree chunk abc (100 MB)...")
        before = p.percent(0)
        p.feed("LOG Fetching ostree chunk abc (100 MB)... done")
        p.feed("LOG Fetching ostree chunk abc (100 MB)... done")
        self.assertEqual(p.fetched, 100e6)
        self.assertGreater(p.percent(0), before)
        self.assertAlmostEqual(p.percent(0), 4 + 82 * 0.5)

    def test_carriage_returns_split_progress_updates(self):
        p = self.feed("LOG Fetching layer a1 (10 MB)...\rFetching layer a1 (10 MB)... done\rFetching layer b2 (5 MiB)...")
        self.assertIn("layer a1", p.done_items)
        self.assertTrue(p.current.startswith("layer b2"))

    def test_network_bytes_move_it_between_layers_but_never_past_the_download(self):
        p = self.feed("LOG layers needed: 1 (1 GB)", "LOG Fetching layer z (1 GB)...")
        self.assertAlmostEqual(p.percent(0.5e9), 4 + 41)
        self.assertLess(p.percent(5e9), 86)

    def test_without_layer_lines_the_download_still_moves(self):
        p = self.feed("LOG Pulling manifest: x", "LOG Importing: x (digest: sha256:1)")
        self.assertGreater(p.percent(1.5e9), 30)

    def test_later_steps_and_the_end(self):
        p = self.feed("LOG layers needed: 1 (1 GB)", "LOG Checking out tree abc...")
        self.assertGreaterEqual(p.percent(0), 86)
        p.feed("LOG Staging deployment...done")
        self.assertGreaterEqual(p.percent(0), 94)
        p.feed("DONE")
        self.assertEqual(p.percent(0), 100)
        self.assertTrue(p.finished)

    def test_real_rpm_ostree_lines(self):
        """The format of rpm-ostree 2026 (from a real install log): "[n/N] Fetching ... (size)...done" per layer, then
        nothing until the deployment is staged."""
        p = self.feed("LOG ostree chunk layers needed: 2 (300 MB)", "LOG custom layers needed: 1 (100 MB)",
                      "LOG [1/3] Fetching ostree chunk 1d628e3a76e28b1c486 (127.8 MB)...done")
        self.assertEqual((p.index, p.count), (1, 3))
        self.assertIn("layer 1 of 3", p.layer_text())
        self.assertAlmostEqual(p.fetched, 127.8e6)
        p.feed("LOG [2/3] Fetching ostree chunk f7ad697fa64a824a610 (172.2 MB)...done")
        p.feed("LOG [3/3] Fetching layer dcf31275c5762ce221e (100 MB)...done")
        self.assertEqual(p.step, "Writing the image to disk")
        self.assertGreaterEqual(p.percent(0), 86)
        self.assertLess(p.percent(0), 94)
        p.feed("LOG Staging deployment...done")
        self.assertGreaterEqual(p.percent(0), 94)

    def test_steps_never_go_back(self):
        p = self.feed("LOG Staging deployment...done", "LOG Pulling manifest: again")
        self.assertEqual(p.step, "Getting it ready for the next start")

    def test_mok_and_failure_lines(self):
        p = self.feed("MOK need")
        self.assertEqual(p.mok, "need")
        p.feed("MOK failed no password")
        self.assertEqual((p.mok, p.mok_why), ("failed", "no password"))
        p.feed("FAIL rpm-ostree rebase ended with status 1")
        self.assertEqual(p.failed, "rpm-ostree rebase ended with status 1")


@unittest.skipUnless(shutil.which("unshare") and subprocess.run(["unshare", "-r", "true"]).returncode == 0,
                     "needs user namespaces (unshare -r) to run root-step.sh as a pretend root")
class RootStepTest(unittest.TestCase):
    """root-step.sh with a pretend mokutil and rpm-ostree on PATH, run as root of a user namespace."""

    def run_step(self, enrolled, password="", sb=True, rebase_status=0):
        with tempfile.TemporaryDirectory() as d:
            bin_ = Path(d, "bin")
            bin_.mkdir()
            state = Path(d, "state")
            state.write_text(enrolled)
            Path(bin_, "mokutil").write_text(textwrap.dedent("""\
                #!/bin/bash
                state=%s
                case "$1" in
                  --sb-state) echo "SecureBoot %s";;
                  --test-key)
                    case "$(cat $state)" in
                      yes) echo "$2 is already enrolled";;
                      queued) echo "$2 is already in the enrollment request";;
                      *) echo "$2 is not enrolled";;
                    esac;;
                  --import)
                    read -r a; read -r b
                    [ "$a" = "$b" ] && [ ${#a} -ge 8 ] && echo queued > $state && echo "$a" > %s/pw;;
                esac
                """ % (state, "enabled" if sb else "disabled", d)))
            Path(bin_, "rpm-ostree").write_text(
                "#!/bin/bash\necho \"Pulling manifest: $2\"\necho 'Staging deployment...done'\nexit %d\n" % rebase_status)
            for f in bin_.iterdir():
                f.chmod(0o755)
            env = dict(os.environ, PATH="%s:%s" % (bin_, os.environ["PATH"]))
            out = subprocess.run(["unshare", "-r", "bash", str(ROOT / "installer" / "root-step.sh"), "cert.der", "img:1"],
                                 input=password + "\n", capture_output=True, text=True, env=env, timeout=30)
            pw = Path(d, "pw").read_text().strip() if Path(d, "pw").exists() else None
            return out.returncode, out.stdout.splitlines(), pw

    def test_already_enrolled_asks_nothing(self):
        code, lines, pw = self.run_step("yes")
        self.assertEqual(code, 0)
        self.assertEqual(lines[0], "MOK enrolled")
        self.assertIn("LOG Pulling manifest: img:1", lines)
        self.assertEqual(lines[-1], "DONE")
        self.assertIsNone(pw)

    def test_not_enrolled_asks_and_queues_with_the_password(self):
        code, lines, pw = self.run_step("no", "onetime123")
        self.assertEqual(code, 0)
        self.assertEqual(lines[:2], ["MOK need", "MOK queued"])
        self.assertEqual(pw, "onetime123")
        self.assertEqual(lines[-1], "DONE")

    def test_already_queued_asks_nothing(self):
        code, lines, _ = self.run_step("queued")
        self.assertEqual(lines[0], "MOK queued")
        self.assertEqual(code, 0)

    def test_no_password_stops_before_the_switch(self):
        code, lines, _ = self.run_step("no", "")
        self.assertNotEqual(code, 0)
        self.assertIn("MOK need", lines)
        self.assertTrue(lines[-1].startswith("FAIL"))
        self.assertFalse(any(line.startswith("LOG") for line in lines))

    def test_secure_boot_off_skips_the_key(self):
        code, lines, _ = self.run_step("no", sb=False)
        self.assertEqual((code, lines[0], lines[-1]), (0, "MOK off", "DONE"))

    def test_a_failed_rebase_is_reported(self):
        code, lines, _ = self.run_step("yes", rebase_status=1)
        self.assertEqual(code, 1)
        self.assertEqual(lines[-1], "FAIL rpm-ostree rebase ended with status 1")


if __name__ == "__main__":
    unittest.main()
