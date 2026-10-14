#!/usr/bin/env python3
"""Stand in for iio-sensor-proxy, to drive the automatic screen rotation without turning the tablet. Development tool, needs root.

Stop the real service first (systemctl stop iio-sensor-proxy), run this, then write orientations into the control file, one
per line: normal, bottom-up, left-up, right-up, or "wait <seconds>". Example of a quick turn that passes through a side:
    printf 'left-up\\nwait 0.08\\nbottom-up\\n' > /run/fake-sensor
Start the real service again afterwards (systemctl start iio-sensor-proxy).
"""
import os
import threading
import time

from gi.repository import Gio, GLib

CONTROL = "/run/fake-sensor"
XML = """<node><interface name="net.hadess.SensorProxy">
<method name="ClaimAccelerometer"/><method name="ReleaseAccelerometer"/><method name="ClaimLight"/><method name="ReleaseLight"/>
<method name="ClaimProximity"/><method name="ReleaseProximity"/>
<property name="HasAccelerometer" type="b" access="read"/><property name="AccelerometerOrientation" type="s" access="read"/>
<property name="AccelerometerTilt" type="s" access="read"/><property name="HasAmbientLight" type="b" access="read"/>
<property name="LightLevel" type="d" access="read"/><property name="LightLevelUnit" type="s" access="read"/>
<property name="HasProximity" type="b" access="read"/><property name="ProximityNear" type="b" access="read"/>
</interface></node>"""
state = {"orientation": "normal"}
PROPS = {"HasAccelerometer": lambda: GLib.Variant("b", True), "AccelerometerOrientation": lambda: GLib.Variant("s", state["orientation"]),
         "AccelerometerTilt": lambda: GLib.Variant("s", "vertical"), "HasAmbientLight": lambda: GLib.Variant("b", False),
         "LightLevel": lambda: GLib.Variant("d", 0.0), "LightLevelUnit": lambda: GLib.Variant("s", "lux"),
         "HasProximity": lambda: GLib.Variant("b", False), "ProximityNear": lambda: GLib.Variant("b", False)}
bus = Gio.bus_get_sync(Gio.BusType.SYSTEM)
node = Gio.DBusNodeInfo.new_for_xml(XML)


def call(conn, sender, path, iface, method, params, inv):
    inv.return_value(None)


def get(conn, sender, path, iface, prop):
    return PROPS[prop]()


bus.register_object("/net/hadess/SensorProxy", node.interfaces[0], call, get, None)
Gio.bus_own_name_on_connection(bus, "net.hadess.SensorProxy", Gio.BusNameOwnerFlags.NONE, None, None)


def emit(orientation):
    state["orientation"] = orientation
    bus.emit_signal(None, "/net/hadess/SensorProxy", "org.freedesktop.DBus.Properties", "PropertiesChanged",
                    GLib.Variant("(sa{sv}as)", ("net.hadess.SensorProxy", {"AccelerometerOrientation": GLib.Variant("s", orientation)}, [])))
    print(time.strftime("%H:%M:%S"), "%.3f" % (time.time() % 1), orientation, flush=True)


def reader():
    if os.path.exists(CONTROL):
        os.remove(CONTROL)
    os.mkfifo(CONTROL, 0o600)
    while True:
        with open(CONTROL) as f:
            for line in f:
                words = line.split()
                if words and words[0] == "wait":
                    time.sleep(float(words[1]))
                elif words and words[0] in ("normal", "bottom-up", "left-up", "right-up"):
                    GLib.idle_add(emit, words[0])


threading.Thread(target=reader, daemon=True).start()
GLib.MainLoop().run()
