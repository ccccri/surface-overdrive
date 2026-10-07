import json
import unittest

from overdrive import health


class FakeSystem:
    def __init__(self, files=None, commands=None, kernel="7.2.8-200.fc44.x86_64"):
        self.files = files or {}
        self.commands = commands or {}
        self.kernel_name = kernel

    def read(self, path):
        return self.files.get(path)

    def exists(self, path):
        return path in self.files

    def readable(self, path):
        return path in self.files

    def glob(self, pattern):
        prefix = pattern.split("*")[0]
        return sorted(p for p in self.files if p.startswith(prefix))

    def run(self, cmd, timeout=8):
        return self.commands.get(tuple(cmd), (127, "not found"))

    def kernel(self):
        return self.kernel_name


MODULES_OK = "".join("%s 4096 0 - Live 0x0 (O)\n" % m for m in health.MODULES)


class ModulesTest(unittest.TestCase):
    def test_all_ours(self):
        c = health.check_modules(FakeSystem({"/proc/modules": MODULES_OK}))
        self.assertEqual(c.status, health.OK)

    def test_stock_module_is_a_failure(self):
        text = MODULES_OK.replace("ov8865 4096 0 - Live 0x0 (O)", "ov8865 4096 0 - Live 0x0")
        c = health.check_modules(FakeSystem({"/proc/modules": text}))
        self.assertEqual(c.status, health.FAIL)
        self.assertIn("ov8865", c.detail)

    def test_missing_module_is_a_warning(self):
        text = "".join(l + "\n" for l in MODULES_OK.splitlines() if not l.startswith("ov5693"))
        c = health.check_modules(FakeSystem({"/proc/modules": text}))
        self.assertEqual(c.status, health.WARN)

    def test_explanations_are_attached(self):
        c = health.check_modules(FakeSystem({"/proc/modules": MODULES_OK}))
        self.assertTrue(c.what and c.how and c.fix)


class KernelMatchTest(unittest.TestCase):
    def test_match_and_mismatch(self):
        record = json.dumps({"kernel": "7.2.8-200.fc44.x86_64"})
        ok = health.check_kernel_match(FakeSystem({health.KMODS_JSON: record}))
        self.assertEqual(ok.status, health.OK)
        bad = health.check_kernel_match(FakeSystem({health.KMODS_JSON: record}, kernel="7.3.0-100.fc44.x86_64"))
        self.assertEqual(bad.status, health.FAIL)

    def test_no_record_is_not_applicable(self):
        self.assertEqual(health.check_kernel_match(FakeSystem()).status, health.NA)


class LibcameraTest(unittest.TestCase):
    CMD = ("rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}", "libcamera")

    def test_patched(self):
        c = health.check_libcamera(FakeSystem(commands={self.CMD: (0, "0.7.1-1.fc44.overdrive1")}))
        self.assertEqual(c.status, health.OK)

    def test_stock_is_a_warning(self):
        c = health.check_libcamera(FakeSystem(commands={self.CMD: (0, "0.7.1-1.fc44")}))
        self.assertEqual(c.status, health.WARN)


class CamerasTest(unittest.TestCase):
    CMD = ("pw-cli", "ls", "Node")

    def test_no_session_is_not_a_failure(self):
        self.assertEqual(health.check_cameras(FakeSystem(commands={self.CMD: (1, "no")})).status, health.NA)

    def test_missing_front(self):
        c = health.check_cameras(FakeSystem(commands={self.CMD: (0, "libcamera_input.__SB_.PCI0.LNK0")}))
        self.assertEqual(c.status, health.FAIL)
        self.assertIn("front", c.detail)


class DevicesTest(unittest.TestCase):
    def test_fake_pen_battery_detected(self):
        files = {"/sys/class/power_supply/hid-0018:04F3:261A.0001-battery-7": ""}
        self.assertEqual(health.check_pen_battery(FakeSystem(files)).status, health.FAIL)
        self.assertEqual(health.check_pen_battery(FakeSystem()).status, health.OK)

    def test_pen_filter_switched_off_is_not_a_problem(self):
        files = {"/etc/udev/rules.d/80-overdrive-stylus.rules": "", "/sys/class/power_supply/hid-x-battery-7": ""}
        self.assertEqual(health.check_pen_battery(FakeSystem(files)).status, health.NA)

    def test_volume_hold_off_by_choice_is_green(self):
        c = health.check_volume_hold(FakeSystem({"/sys/module/intel_hid/parameters/volume_hold": "N\n"}))
        self.assertEqual(c.status, health.OK)
        self.assertIn("off", c.detail)

    def test_nfc_service_not_active(self):
        files = {"/sys/bus/acpi/devices/NXP3001:00": "", "/sys/class/nfc/nfc0": ""}
        cmd = {("systemctl", "is-active", "overdrive-nfcd"): (3, "inactive")}
        self.assertEqual(health.check_nfc(FakeSystem(files, cmd)).status, health.WARN)


class SecureBootTest(unittest.TestCase):
    def test_key_not_enrolled(self):
        cmds = {("mokutil", "--sb-state"): (0, "SecureBoot enabled"),
                ("mokutil", "--test-key", health.MOK_CERT): (0, "x is not enrolled")}
        c = health.check_secure_boot(FakeSystem({health.MOK_CERT: ""}, cmds))
        self.assertEqual(c.status, health.FAIL)

    def test_unreadable_certificate_is_not_reported_as_missing_key(self):
        class Unreadable(FakeSystem):
            def readable(self, path):
                return False
        c = health.check_secure_boot(Unreadable({health.MOK_CERT: ""}, {("mokutil", "--sb-state"): (0, "SecureBoot enabled")}))
        self.assertEqual(c.status, health.WARN)

    def test_secure_boot_off(self):
        c = health.check_secure_boot(FakeSystem(commands={("mokutil", "--sb-state"): (0, "SecureBoot disabled")}))
        self.assertEqual(c.status, health.OK)


class SummaryTest(unittest.TestCase):
    def test_overall_and_json(self):
        checks = [health.Check("a", "g", "t", health.OK), health.Check("b", "g", "t", health.WARN)]
        self.assertEqual(health.overall(checks), health.WARN)
        data = json.loads(health.as_json(checks))
        self.assertEqual(data["overall"], health.WARN)
        self.assertEqual([c["id"] for c in data["checks"]], ["a", "b"])

    def test_run_all_never_raises_on_an_empty_system(self):
        checks = health.run_all(FakeSystem())
        self.assertEqual(len(checks), len(health.CHECKS))


if __name__ == "__main__":
    unittest.main()
