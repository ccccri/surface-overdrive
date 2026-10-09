import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from overdrive import maintenance, userconfig


class Settings(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = os.path.join(self.tmp.name, "config")
        for p in (mock.patch.object(userconfig, "CONFIG", self.config),
                  mock.patch.dict(os.environ, {"XDG_STATE_HOME": os.path.join(self.tmp.name, "state")}),
                  mock.patch.object(maintenance, "_apply_now")):
            p.start()
            self.addCleanup(p.stop)
        self.put("audio.json", json.dumps({"eq": {"sync": True}, "presets": {"eq": {"Mine": {}}}}))
        self.put("camera/ov8865.profile", "gamma 1.45\n")
        self.put("presets/rear/evening.json", json.dumps({"name": "Evening", "profile": {}}))
        self.put("notes.txt", "not a settings file")
        self.file = os.path.join(self.tmp.name, "out.json")

    def put(self, rel, text):
        userconfig.write_atomic(os.path.join(self.config, rel), text)

    def read(self, rel):
        with open(os.path.join(self.config, rel)) as f:
            return f.read()

    def test_round_trip_and_undo(self):
        out = maintenance.export_settings(self.file)
        self.assertEqual(out["result"], "ok")
        self.assertTrue(any("1 profile of yours" in line for line in out["contents"]))
        self.assertNotIn("notes.txt", json.load(open(self.file))["files"])
        self.put("camera/ov8865.profile", "gamma 2.0\n")
        self.put("presets/front/new.json", "{}")
        self.assertEqual(maintenance.import_settings(self.file)["result"], "ok")
        self.assertEqual(self.read("camera/ov8865.profile"), "gamma 1.45\n")
        self.assertFalse(os.path.exists(os.path.join(self.config, "presets/front/new.json")))
        self.assertEqual(self.read("notes.txt"), "not a settings file")          # what is not ours is left alone
        self.assertEqual(maintenance.undo_import()["result"], "ok")
        self.assertEqual(self.read("camera/ov8865.profile"), "gamma 2.0\n")
        self.assertEqual(maintenance.undo_import()["result"], "refused")

    def test_refuses_what_is_not_a_settings_file(self):
        good = {"format": maintenance.FORMAT, "version": maintenance.VERSION, "files": {"audio.json": "{}"}}
        bad = ["{broken", "[]", json.dumps({"format": "other"}), json.dumps(dict(good, version=99)), json.dumps(dict(good, files={})),
               json.dumps(dict(good, files={"../../.bashrc": "x"})), json.dumps(dict(good, files={"/etc/passwd": "x"})),
               json.dumps(dict(good, files={"camera/../../x.profile": "x"})), json.dumps(dict(good, files={"audio.json": "{broken"})),
               json.dumps(dict(good, files={"audio.json": 5})), json.dumps(dict(good, files={"evil.sh": "x"})),
               json.dumps(dict(good, files={"audio.json": "[1, 2]"})), json.dumps(dict(good, files={"ui.json": '"text"'})),
               json.dumps(dict(good, files={"camera/ov8865.profile": "gamma abc"})),
               json.dumps(dict(good, files={"camera/ov8865.profile": "gamma 1.4\n$(reboot)"})),
               json.dumps(dict(good, files={"camera/ov8865.profile": "gamma 1.4\x00"})),
               json.dumps(dict(good, files={"presets/rear/" + "a" * 300 + ".json": "{}"})), json.dumps(good) + "trailing"]
        before = self.read("audio.json")
        for text in bad:
            with open(self.file, "w") as f:
                f.write(text)
            self.assertEqual(maintenance.inspect_settings(self.file)["result"], "refused", text)
            self.assertEqual(maintenance.import_settings(self.file)["result"], "refused", text)
        self.assertEqual(maintenance.import_settings(os.path.join(self.tmp.name, "missing"))["result"], "refused")
        for special in ("/dev/zero", "/dev/null", self.tmp.name):
            self.assertEqual(maintenance.import_settings(special)["result"], "refused")
        self.assertEqual(maintenance.export_settings(self.tmp.name)["result"], "failed")
        self.assertEqual(self.read("audio.json"), before)
        self.assertFalse(os.path.exists(maintenance.backup_path()))


    def test_a_failed_write_changes_nothing(self):
        maintenance.export_settings(self.file)
        self.put("camera/ov8865.profile", "gamma 2.0\n")
        real = userconfig.write_atomic
        def flaky(path, text):
            if path.endswith("evening.json") and "config" in path:
                raise OSError(28, "No space left on device")
            real(path, text)
        with mock.patch.object(userconfig, "write_atomic", side_effect=flaky):
            out = maintenance.import_settings(self.file)
        self.assertEqual(out["result"], "failed")
        self.assertEqual(self.read("camera/ov8865.profile"), "gamma 2.0\n")

    def test_good_camera_profile_lines(self):
        self.assertTrue(maintenance._well_formed("camera/ov8865.profile", "# Written by Surface Control.\ngamma 1.45\ntnr 24 14\nblack 30 34 30 30\nmin_width 2048\n\n"))


class Repairs(unittest.TestCase):
    def test_runs_the_fixed_command_and_checks_again(self):
        ran = []
        check = SimpleNamespace(id="audio", status="ok", detail="fine")
        with mock.patch.object(maintenance.health, "run_all", return_value=[check]):
            out = maintenance.repair("audio", run=lambda cmd, **kw: ran.append(cmd) or SimpleNamespace(returncode=0, stderr=""), settle=0)
            self.assertEqual(out["result"], "ok")
            self.assertEqual(ran, [["systemctl", "--user", "restart", "overdrive-audio-route.service"]])
            out = maintenance.repair("nfc", run=lambda cmd, **kw: ran.append(cmd) or SimpleNamespace(returncode=1, stderr="denied"), settle=0)
            self.assertEqual((out["result"], out["error"]), ("failed", "denied"))
            self.assertEqual(ran[-1][0], "pkexec")
        self.assertEqual(maintenance.repair("secure-boot; rm -rf /")["result"], "refused")


class Images(unittest.TestCase):
    def status(self, deployments):
        return lambda cmd, **kw: SimpleNamespace(returncode=0, stdout=json.dumps({"deployments": deployments}), stderr="")

    def test_states(self):
        out = maintenance.images(run=self.status([{"version": "3", "timestamp": 100}, {"version": "2", "booted": True}, {"version": "1"}]))
        self.assertEqual([i["state"] for i in out["images"]], ["next", "in use", "previous"])
        self.assertFalse(out["can_go_back"])                    # something already waits for the restart
        out = maintenance.images(run=self.status([{"version": "2", "booted": True}, {"version": "1"}]))
        self.assertTrue(out["can_go_back"])
        self.assertFalse(maintenance.images(run=self.status([{"version": "2", "booted": True}]))["can_go_back"])

    def test_going_back_can_be_undone_but_an_update_is_left_alone(self):
        ran = []
        def run_for(deployments):
            def run(cmd, **kw):
                ran.append(cmd)
                return SimpleNamespace(returncode=0, stdout=json.dumps({"deployments": deployments}), stderr="")
            return run
        went_back = [{"version": "1", "timestamp": 100}, {"version": "2", "timestamp": 200, "booted": True}]
        self.assertTrue(maintenance.images(run=run_for(went_back))["images"][0]["went_back"])
        self.assertEqual(maintenance.cancel_next(run=run_for(went_back))["result"], "ok")
        self.assertEqual(ran[-1], ["rpm-ostree", "rollback"])
        update = [{"version": "3", "timestamp": 300}, {"version": "2", "timestamp": 200, "booted": True}]
        self.assertEqual(maintenance.cancel_next(run=run_for(update))["result"], "refused")
        self.assertNotIn(["rpm-ostree", "cleanup", "--pending"], ran)

    def test_unreadable(self):
        out = maintenance.images(run=lambda cmd, **kw: SimpleNamespace(returncode=1, stdout="not json", stderr=""))
        self.assertEqual(out["images"], [])


class Report(unittest.TestCase):
    def test_scrub(self):
        with mock.patch.dict(os.environ, {"USER": "cristian"}):
            text = maintenance._scrub("/home/cristian/x 192.168.0.230 9a:7c:61:c2:b4:ad fd33:6f26:5a00:648:8ae3:7852:d21a:2a66 version 6.7.5")
        self.assertNotIn("cristian", text)
        self.assertNotIn("192.168", text)
        self.assertNotIn("9a:7c", text)
        self.assertNotIn("fd33", text)
        self.assertIn("6.7.5", text)




class Commands(unittest.TestCase):
    def test_the_command_module_loads_and_refuses_nonsense(self):
        from overdrive import ctl
        with mock.patch("sys.stderr"):
            self.assertEqual(ctl.maintenance_command(["settings", "bogus"]), 2)
            self.assertEqual(ctl.maintenance_command(["image", "bogus"]), 2)
