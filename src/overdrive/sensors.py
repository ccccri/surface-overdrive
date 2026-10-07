"""Facts the Sensors and NFC pages show: battery, light sensor, accelerometer and gyroscope, NFC service state, device identity.

Everything is read from sysfs and needs no privileges.
"""
import glob
import math
import os
import subprocess


def read(path, default=""):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def number(path, default=None):
    try:
        return float(read(path))
    except ValueError:
        return default


def iio_device(name):
    """sysfs directory of the IIO device with this name, or None."""
    for d in glob.glob("/sys/bus/iio/devices/iio:device*"):
        if read(d + "/name") == name:
            return d
    return None


def battery():
    for b in sorted(glob.glob("/sys/class/power_supply/BAT*")):
        cap, full, design = number(b + "/capacity"), number(b + "/charge_full"), number(b + "/charge_full_design")
        now, cur, volt = number(b + "/charge_now"), number(b + "/current_now"), number(b + "/voltage_now")
        status = read(b + "/status", "Unknown")
        out = {"percent": min(cap, 100) if cap is not None else None, "status": status,
               "cycles": int(number(b + "/cycle_count", 0)), "health": round(100 * full / design) if full and design else None,
               "maker": read(b + "/manufacturer"), "model": read(b + "/model_name"),
               "design_mah": round((design or 0) / 1000), "full_mah": round((full or 0) / 1000)}
        if cur is not None and volt is not None:
            out["watts"] = round(cur * volt / 1e12, 1)
        if cur and now is not None and full is not None and cur > 0:
            hours = (full - now) / cur if status == "Charging" else now / cur
            if hours > 0:
                out["hours"] = round(hours, 1)
        return out
    return None


def light():
    d = iio_device("als")
    if not d:
        return None
    raw, scale = number(d + "/in_illuminance_raw"), number(d + "/in_illuminance_scale", 1)
    return None if raw is None else round(raw * scale, 1)


def motion():
    """Acceleration (m/s^2) and angular speed (deg/s) of the tablet, or None when the sensors are missing."""
    a, g = iio_device("accel_3d"), iio_device("gyro_3d")
    if not a:
        return None
    sa = number(a + "/in_accel_scale", 1)
    acc = [number("%s/in_accel_%s_raw" % (a, ax)) for ax in "xyz"]
    if None in acc:
        return None
    out = {"accel": [round(v * sa, 2) for v in acc]}
    if g:
        sg = number(g + "/in_anglvel_scale", 1)
        gyr = [number("%s/in_anglvel_%s_raw" % (g, ax)) for ax in "xyz"]
        if None not in gyr:
            out["gyro"] = [round(math.degrees(v * sg), 1) for v in gyr]
    return out


def device():
    out = {"model": (read("/sys/class/dmi/id/sys_vendor") + " " + read("/sys/class/dmi/id/product_name")).strip(),
           "firmware": read("/sys/class/dmi/id/bios_version"), "firmware_date": read("/sys/class/dmi/id/bios_date"),
           "kernel": os.uname().release}
    try:
        out["cpu"] = next(l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name"))
        out["memory_gb"] = round(int(next(l.split()[1] for l in open("/proc/meminfo") if l.startswith("MemTotal"))) / 1048576, 1)
    except (OSError, StopIteration, ValueError):
        pass
    return out


def describe():
    return {"battery": battery(), "lux": light(), "motion": motion(), "device": device()}


def unit_state(unit, user=False):
    cmd = ["systemctl"] + (["--user"] if user else []) + ["is-active", unit]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def nfc_info():
    return {"device": os.path.isdir("/sys/class/nfc/nfc0"), "daemon": unit_state("overdrive-nfcd"),
            "notifier": unit_state("overdrive-nfc-notify", True)}


def set_rate(hz):
    """Faster sensor updates while the live view is open (the hub default is 10 Hz). Needs the udev rule; ignored without it."""
    for name, attr in (("accel_3d", "in_accel_sampling_frequency"), ("gyro_3d", "in_anglvel_sampling_frequency")):
        d = iio_device(name)
        if d:
            try:
                with open("%s/%s" % (d, attr), "w") as f:
                    f.write(str(int(hz)))
            except OSError:
                pass
