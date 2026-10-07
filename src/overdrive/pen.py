"""What the Surface Pen page shows: the digitizer, a leftover fake battery, paired Bluetooth pens with their battery level."""
import glob
import os
import re
import subprocess


def digitizers(devices_text):
    """Names of the pen/touch digitizers listed in /proc/bus/input/devices."""
    return [l.split('"')[1] for l in devices_text.splitlines() if l.startswith("N:") and "ELAN" in l and "UNKNOWN" not in l]


def fake_batteries(names):
    """Power supplies that are neither the charger nor the tablet battery: the pen battery the touchscreen invents."""
    return [n for n in names if n != "ACAD" and not n.startswith("BAT")]


def bluetooth_batteries():
    """Paired Bluetooth devices with a battery service (the Surface Pen has one), straight from BlueZ."""
    def run(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=6).stdout
        except (OSError, subprocess.SubprocessError):
            return ""
    out = []
    for line in run(["bluetoothctl", "devices"]).splitlines():
        parts = line.split(None, 2)
        if len(parts) < 3 or parts[0] != "Device":
            continue
        info = run(["bluetoothctl", "info", parts[1]])
        if "Battery Service" not in info and "Battery Percentage" not in info:
            continue
        m = re.search(r"Battery Percentage:\s*0x[0-9a-fA-F]+\s*\((\d+)\)", info)
        out.append({"name": parts[2], "connected": "Connected: yes" in info, "battery": int(m.group(1)) if m else -1})
    return out


def describe(filter_state):
    try:
        devices = open("/proc/bus/input/devices").read()
    except OSError:
        devices = ""
    supplies = [os.path.basename(p) for p in glob.glob("/sys/class/power_supply/*")]
    return {"digitizer": digitizers(devices), "fakeBattery": fake_batteries(supplies), "bluetooth": bluetooth_batteries(),
            "filter": filter_state}
