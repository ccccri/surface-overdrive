"""overdrive-camera: the camera app of Surface Overdrive.

Preview, photos and videos from the two built-in cameras, through PipeWire. Videos are encoded on the GPU (VA-API H.264,
with RPM Fusion's Intel driver in the image) into MP4 with AAC sound, so recording costs almost no processor time and
the video keeps the real time of every frame. Kamoso encoded Theora in software: about 13 frames a second at
1152x864 on the Surface Go, and its videos then played too fast.

How the picture flows:
  preview  pipewiresrc -> tee -> glupload -> qml6glsink, drawn by the GPU straight into the window (no copy through
                                 Python: the first version copied every frame into a QVideoFrame and the preview lagged)
                              -> appsink holding the last full-size frame, for photos
  video    a second pipewiresrc on the same camera -> vapostproc -> vah264enc -> mp4mux, with the microphone
The camera's size is the first one it offers, which the Cameras page of System Settings chooses ("min_width").
"""
import datetime
import json
import os
import subprocess
import sys
import threading
import time

APP_ID = "org.surfaceoverdrive.Camera"
CAMERAS = (("front", "Front", "libcamera_input.__SB_.PCI0.LNK1"), ("rear", "Rear", "libcamera_input.__SB_.PCI0.LNK0"))
PREVIEW_MAX_WIDTH = 1280
START_TRIES = 15                  # looks for the cameras every 2 s for half a minute
STALL_SECONDS = 5                 # a preview without frames this long is started again
SWITCH_INTERVAL = 1.0             # seconds between two camera switches
JPEG_QUALITY = 92
# Night: frames longer than this are the exposure at its longest (60 ms) in a dim room; shorter ones end it again
NIGHT_ON_INTERVAL = 0.052
NIGHT_OFF_INTERVAL = 0.045
NIGHT_FRAMES = 20                 # a night photo: about 1.2 s of frames at 60 ms, after the skipped ones
NIGHT_SKIP = 6                    # frames still averaged: libcamera reads the profile every 200 ms
FLASH_SETTLE_MS = 700             # the auto exposure's time to take in the white screen before a front flash photo
CAPTURE_SUFFIXES = (".jpg", ".jpeg", ".png", ".mp4", ".mkv", ".webm", ".mov")
MAX_GALLERY = 200


# ---- Pure helpers (tested in tests/test_cameraapp.py)

def cameras_from_dump(dump):
    """{key: {"label", "node", "size": (w, h)}} for the built-in cameras PipeWire has, from the JSON of pw-dump."""
    found = {}
    for obj in dump or []:
        if not str(obj.get("type", "")).endswith("Node"):
            continue
        info = obj.get("info") or {}
        name = (info.get("props") or {}).get("node.name", "")
        for key, label, node in CAMERAS:
            if name != node:
                continue
            sizes = [(f["size"]["width"], f["size"]["height"]) for f in (info.get("params") or {}).get("EnumFormat", [])
                     if isinstance(f, dict) and f.get("format") == "NV12" and isinstance(f.get("size"), dict)]
            if sizes:
                found[key] = {"label": label, "node": node, "size": sizes[0]}
    return found


def preview_size(width, height, max_width=PREVIEW_MAX_WIDTH):
    """The preview size: the camera's, scaled down to at most max_width, both sides even."""
    if width <= max_width:
        return width, height
    w = max_width - max_width % 2
    h = round(height * w / width)
    return w, h - h % 2


# the quality choices of the settings: photo = JPEG quality, video = H.264 kbit/s per megapixel of a frame
PHOTO_QUALITIES = {"standard": 85, "high": 92, "maximum": 98}
VIDEO_QUALITIES = {"standard": 2.5, "high": 5.0, "maximum": 8.0}


def video_bitrate(width, height, quality="standard"):
    """H.264 bit rate in kbit/s: per megapixel of a frame as the quality says (2.5 standard), at least 4000 (12000 at
    2560x1920 standard)."""
    return max(4000, round(width * height / 1e6 * VIDEO_QUALITIES.get(quality, 2.5)) * 1000)


def preview_description(node, width, height):
    # One branch only: with a tee and an appsink for photos next to qml6glsink, the preview froze after four frames
    # (2026-10-27). A photo is a copy of the frame going to the preview at the time of the tap (Camera._on_frame).
    return ("pipewiresrc target-object={node} stream-properties=props,media.type=Video,media.category=Capture,media.role=Camera ! video/x-raw,format=NV12,width={w},height={h} "
            "! queue leaky=downstream max-size-buffers=1 ! glupload name=upload ! glcolorconvert "
            "! qml6glsink name=preview sync=false").format(node=node, w=width, h=height)


def record_description(node, width, height, path, audio=True, quality="standard"):
    video = ("pipewiresrc target-object={node} stream-properties=props,media.type=Video,media.category=Capture,media.role=Camera ! video/x-raw,format=NV12,width={w},height={h} ! queue max-size-buffers=8 "
             "! vapostproc ! vah264enc bitrate={rate} ! h264parse name=parse ! queue ! mux. "
             ).format(node=node, w=width, h=height, rate=video_bitrate(width, height, quality))
    sound = "pulsesrc ! audioconvert ! audioresample ! audio/x-raw,rate=48000,channels=2 ! fdkaacenc ! queue ! mux. " if audio else ""
    return video + sound + "mp4mux name=mux ! filesink location=\"{}\"".format(path.replace("\"", "\\\""))


def output_path(directory, kind, now=None):
    """A new file name in directory: kind "photo" (.jpg) or "video" (.mp4), named after the time, never an existing one."""
    now = now or datetime.datetime.now()
    stem = now.strftime("%Y-%m-%d_%H-%M-%S")
    ext = ".jpg" if kind == "photo" else ".mp4"
    path = os.path.join(directory, "{}_{}{}".format("IMG" if kind == "photo" else "VID", stem, ext))
    n = 1
    while os.path.exists(path):
        n += 1
        path = os.path.join(directory, "{}_{}-{}{}".format("IMG" if kind == "photo" else "VID", stem, n, ext))
    return path


def pw_dump():
    try:
        out = subprocess.run(["pw-dump"], capture_output=True, text=True, timeout=10, check=False).stdout
        return json.loads(out or "[]")
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


# The top button of the Surface Pen (a Bluetooth keyboard): Meta+F20 for a click, Meta+F19 for a double click, Meta+F18 when
# held. Known by their XKB key codes (evdev + 8): the keyboard map turns F20 into Microphone Mute and F18 into Launch9.
PEN_KEYCODES = {196, 197, 198}


def is_pen_button(keycode, autorepeat=False):
    return keycode in PEN_KEYCODES and not autorepeat


# ---- The app

def main():
    import gi
    gi.require_version("Gst", "1.0")
    gi.require_version("GstApp", "1.0")
    gi.require_version("GstVideo", "1.0")
    from gi.repository import Gst, GstVideo
    from PySide6.QtCore import QEvent, Property, QObject, QStandardPaths, QTimer, QUrl, Signal, Slot
    from PySide6.QtDBus import QDBusConnection, QDBusMessage
    from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
    import ctypes
    import shiboken6

    Gst.init(None)
    # qml6glsink draws with OpenGL inside the Qt Quick scene, which has to use OpenGL too; the element must exist before the
    # QML file that uses its item type is loaded (it registers the type)
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)
    Gst.ElementFactory.make("qml6glsink")
    _gobject = ctypes.CDLL("libgobject-2.0.so.0")
    _gobject.g_object_set.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p]
    ctypes.pythonapi.PyCapsule_GetPointer.restype = ctypes.c_void_p
    ctypes.pythonapi.PyCapsule_GetPointer.argtypes = [ctypes.py_object, ctypes.c_char_p]

    def set_widget(sink, item):
        """sink.widget = item: PyGObject cannot pass a Qt item as the gpointer the property takes."""
        _gobject.g_object_set(ctypes.pythonapi.PyCapsule_GetPointer(sink.__gpointer__, None), b"widget",
                              shiboken6.getCppPointer(item)[0], None)

    def folder(location, sub):
        base = QStandardPaths.writableLocation(location) or os.path.expanduser("~")
        path = os.path.join(base, sub) if sub else base
        os.makedirs(path, exist_ok=True)
        return path

    class Camera(QObject):
        changed = Signal()
        message = Signal(str)
        settingsChanged = Signal()
        capturesChanged = Signal()
        penButton = Signal()                # the top button of the Surface Pen: a press of the shutter
        _sizeApplied = Signal()             # from the thread that restarted the camera service
        _darkSeen = Signal(bool)            # from GStreamer's thread: the frames say dark / not dark
        _burstStep = Signal(float)          # from GStreamer's thread: share of the night frames collected

        def __init__(self):
            super().__init__()
            self._sink = None
            self._cameras = {}
            self._key = ""
            self._preview = None
            self._recorder = None
            self._recording_since = None
            self._recorded = ""
            self._error = ""
            self._last_capture = ""
            self._photo_wanted = ""
            self._tries = 0
            self._stopping = False
            self._frames = 0
            self._last_switch = 0.0
            self._last_frame = 0.0
            self._stalls = 0
            self._bus_timer = QTimer(self, interval=100, timeout=self._poll)
            self._bus_timer.start()
            self._applying_size = False
            self._sizeApplied.connect(self._size_applied)
            # night mode: on by itself when the frames get long (the dark), the user can turn it off for now
            self._intervals = []
            self._last_pts = None
            self._dark = False
            self._night_off = False
            self._burst = None            # {"path", "frames", "info"} while a night photo collects its frames
            self._progress = 0.0
            self._busy = ""
            self._darkSeen.connect(self._dark_seen)
            self._burstStep.connect(self._burst_step)
            # the screen as a light: a warm frame the window draws round the picture, with the backlight at its brightest
            self._light = False
            self._flash_mode = "auto"     # front photos in the dark: the frame lights the face for the shot
            self._audio = True            # videos with sound
            self._boosts = 0              # light and flash both want the backlight up: up while either does
            self._brightness_before = None
            # always the best: the owner wants no quality choice (2026-11-03)
            self._photo_quality = "maximum"
            self._video_quality = "maximum"

        # -- properties for QML
        def _get_key(self):
            return self._key

        def _get_labels(self):
            return [self._cameras[k]["label"] for k, _, _ in CAMERAS if k in self._cameras]

        def _get_keys(self):
            return [k for k, _, _ in CAMERAS if k in self._cameras]

        def _get_size(self):
            cam = self._cameras.get(self._key)
            return "{} x {}".format(*cam["size"]) if cam else ""

        def _get_recording(self):
            return self._recorder is not None

        def _get_error(self):
            return self._error

        def _get_mirrored(self):
            return self._key == "front"

        def _get_last(self):
            return QUrl.fromLocalFile(self._last_capture).toString() if self._last_capture else ""

        def _get_last_is_video(self):
            return self._last_capture.lower().endswith((".mp4", ".mkv", ".webm", ".mov"))

        # -- night mode, the light, flash
        def _get_dark(self):
            return self._dark

        def _get_night(self):
            return self._dark and not self._night_off

        def _get_progress(self):
            return self._progress

        def _get_busy(self):
            return self._busy

        def _get_light(self):
            return self._light

        def _get_flash_mode(self):
            return self._flash_mode

        dark = Property(bool, _get_dark, notify=changed)
        night = Property(bool, _get_night, notify=changed)
        progress = Property(float, _get_progress, notify=changed)
        busy = Property(str, _get_busy, notify=changed)
        light = Property(bool, _get_light, notify=changed)

        def _get_audio(self):
            return self._audio

        audio = Property(bool, _get_audio, notify=changed)

        @Slot(bool)
        def setAudio(self, on):
            if self._recorder is None and on != self._audio:
                self._audio = bool(on)
                self.changed.emit()
        flashMode = Property(str, _get_flash_mode, notify=changed)

        @Slot()
        def toggleNight(self):
            self._night_off = not self._night_off
            self.changed.emit()

        @Slot()
        def cycleFlash(self):
            self._flash_mode = {"auto": "on", "on": "off", "off": "auto"}[self._flash_mode]
            self.changed.emit()

        @Slot(result=bool)
        def flashWanted(self):
            """Whether this photo gets the screen as a flash: front camera, the light off, and on or in the dark."""
            if self._key != "front" or self._light or self._flash_mode == "off":
                return False
            return self._flash_mode == "on" or self._dark

        def _dark_seen(self, dark):
            if dark != self._dark:
                self._dark = dark
                self.changed.emit()

        @Slot()
        def toggleLight(self):
            self._light = not self._light
            self._boost(self._light)
            self.changed.emit()

        def _boost(self, up):
            """The backlight at its brightest while the light or a flash wants it, back where it was afterwards."""
            self._boosts = max(0, self._boosts + (1 if up else -1))
            try:
                if up and self._boosts == 1:
                    self._brightness_before = int(self._brightness("brightness"))
                    self._brightness("setBrightnessSilent", int(self._brightness("brightnessMax")))
                elif not up and self._boosts == 0 and self._brightness_before is not None:
                    self._brightness("setBrightnessSilent", self._brightness_before)
                    self._brightness_before = None
            except (TypeError, ValueError):
                pass

        def _brightness(self, method, *args):
            msg = QDBusMessage.createMethodCall("org.kde.Solid.PowerManagement",
                                                "/org/kde/Solid/PowerManagement/Actions/BrightnessControl",
                                                "org.kde.Solid.PowerManagement.Actions.BrightnessControl", method)
            if args:
                msg.setArguments(list(args))
            values = QDBusConnection.sessionBus().call(msg).arguments()
            return values[0] if values else None

        @Slot()
        def flashOn(self):
            """The backlight up for a flash photo (the window shows its light frame meanwhile)."""
            self._boost(True)

        @Slot()
        def flashOff(self):
            self._boost(False)

        key = Property(str, _get_key, notify=changed)
        keys = Property("QVariantList", _get_keys, notify=changed)
        labels = Property("QVariantList", _get_labels, notify=changed)
        size = Property(str, _get_size, notify=changed)
        recording = Property(bool, _get_recording, notify=changed)
        error = Property(str, _get_error, notify=changed)
        mirrored = Property(bool, _get_mirrored, notify=changed)
        lastCapture = Property(str, _get_last, notify=changed)
        lastIsVideo = Property(bool, _get_last_is_video, notify=changed)

        # -- settings of the camera in use: the same ones as the Cameras page of System Settings (overdrive.camera),
        # written to the live profile that the patched libcamera reads while it runs
        def _get_settings(self):
            from overdrive import camera as cs
            if self._key not in cs.SENSORS:
                return "{}"
            try:
                return json.dumps({"controls": cs.controls(self._key), "values": cs.settings(self._key),
                                   "sizes": [{"minWidth": w, "text": t, "desc": d} for w, t, d in cs.SIZES[self._key]]})
            except (OSError, ValueError, KeyError):
                return "{}"

        def _get_applying(self):
            return self._applying_size

        settings = Property(str, _get_settings, notify=settingsChanged)

        def _get_photo_quality(self):
            return self._photo_quality

        def _get_video_quality(self):
            return self._video_quality

        photoQuality = Property(str, _get_photo_quality, notify=settingsChanged)
        videoQuality = Property(str, _get_video_quality, notify=settingsChanged)

        @Slot(str, str)
        def setQuality(self, kind, value):
            """kind "photo" or "video"; remembered for the next start."""
            from overdrive import camera as cs
            if kind == "photo" and value in PHOTO_QUALITIES:
                self._photo_quality = value
            elif kind == "video" and value in VIDEO_QUALITIES:
                self._video_quality = value
            else:
                return
            cs.set_ui_setting("cameraApp_" + kind + "Quality", value)
            self.settingsChanged.emit()
        applyingSize = Property(bool, _get_applying, notify=settingsChanged)

        @Slot(str, "QVariant")
        def setSetting(self, key, value):
            """One setting of the camera in use. A new picture size restarts the camera service (the sizes are read when
            the camera nodes are made): the preview stops, the restart runs on a thread, the preview starts again."""
            from overdrive import camera as cs
            if self._key not in cs.SENSORS or self._recorder is not None:
                return
            cam = self._key
            if key == "minWidth":
                self._applying_size = True
                self._stop_preview()
                self._error = "Changing the picture size..."
                self.changed.emit()
                self.settingsChanged.emit()

                def work():
                    try:
                        cs.set_setting(cam, key, value)
                    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
                        self.message.emit("The size could not be changed: {}".format(exc))
                    self._sizeApplied.emit()
                threading.Thread(target=work, daemon=True).start()
                return
            try:
                cs.set_setting(cam, key, value)
            except (OSError, ValueError, KeyError) as exc:
                self.message.emit("The setting could not be changed: {}".format(exc))
            self.settingsChanged.emit()

        def _size_applied(self):
            self._applying_size = False
            self.presetsChanged.emit()
            self._error = ""
            self._tries = 0
            self.settingsChanged.emit()
            self.start()

        # -- the photo presets of the Embedded Cameras page (whole profiles saved under a name)
        presetsChanged = Signal()

        def _get_presets(self):
            from overdrive import camera as cs
            if self._key not in cs.SENSORS:
                return "[]"
            try:
                return json.dumps(cs.list_presets(self._key))
            except (OSError, ValueError):
                return "[]"

        presets = Property(str, _get_presets, notify=presetsChanged)

        @Slot()
        def refreshPresets(self):
            self.presetsChanged.emit()

        @Slot(str)
        def applyPreset(self, pid):
            """A preset as the current profile ("" for the tuning defaults, the size kept). A preset with another picture
            size restarts the camera service: done on a thread, the preview starts again afterwards."""
            from overdrive import camera as cs
            if self._key not in cs.SENSORS or self._recorder is not None or self._applying_size:
                return
            cam = self._key
            if not pid:
                cs.reset_all(cam, keep_size=True)
                self.presetsChanged.emit()
                self.settingsChanged.emit()
                return
            try:
                size_changes = cs._preset_profile(cam, pid).get("min_width") != cs.read_profile(cam).get("min_width")
            except (ValueError, OSError):
                return
            if not size_changes:
                cs.apply_preset(cam, pid)
                self.presetsChanged.emit()
                self.settingsChanged.emit()
                return
            self._applying_size = True
            self._stop_preview()
            self._error = "Changing the picture size..."
            self.changed.emit()

            def work():
                try:
                    cs.apply_preset(cam, pid)
                except (OSError, ValueError, subprocess.SubprocessError) as exc:
                    self.message.emit("The preset could not be applied: {}".format(exc))
                self._sizeApplied.emit()
            threading.Thread(target=work, daemon=True).start()

        @Slot()
        def openCameraSettings(self):
            """The Embedded Cameras page of System Settings, where presets are made."""
            subprocess.Popen(["systemsettings", "kcm_overdrive_cameras"], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)

        @Slot()
        def resetSettings(self):
            from overdrive import camera as cs
            if self._key in cs.SENSORS:
                cs.reset_all(self._key, keep_size=True)
                self.settingsChanged.emit()

        # -- the photos and videos taken, newest first, for the gallery of the app
        def _get_captures(self):
            items = []
            for d in (folder(QStandardPaths.StandardLocation.PicturesLocation, "Camera"),
                      folder(QStandardPaths.StandardLocation.MoviesLocation, "")):
                try:
                    names = os.listdir(d)
                except OSError:
                    continue
                for name in names:
                    if name.lower().endswith(CAPTURE_SUFFIXES) and not name.endswith(".part"):
                        path = os.path.join(d, name)
                        try:
                            items.append((os.path.getmtime(path), path))
                        except OSError:
                            pass
            items.sort(reverse=True)
            return [path for _, path in items[:MAX_GALLERY]]

        captures = Property("QVariantList", _get_captures, notify=capturesChanged)

        @Slot(str)
        def trash(self, path):
            """Into the trash, not deleted: a wrong tap can be undone from Dolphin."""
            if path in self._get_captures():
                subprocess.run(["gio", "trash", path], check=False, timeout=10)
                if path == self._last_capture:
                    rest = self._get_captures()
                    self._last_capture = rest[0] if rest else ""
                    self.changed.emit()
                self.capturesChanged.emit()

        @Slot(str)
        def openExternally(self, path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

        @Slot()
        def openLast(self):
            if self._last_capture:
                QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_capture))

        @Slot(QObject)
        def setSink(self, sink):
            self._sink = sink

        @Slot()
        def start(self):
            """Find the cameras and start the preview. When there are none yet (the camera service still starting, or
            started before the login gave it the devices: it does not look again by itself), look again every two
            seconds, restart the camera service once after four, and give up with a message after half a minute."""
            self._cameras = cameras_from_dump(pw_dump())
            if not self._cameras:
                self._tries += 1
                if self._tries == 2:
                    from overdrive import camera as camera_settings
                    subprocess.Popen(["systemctl", "--user", "restart", camera_settings.camera_service()],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if self._tries <= START_TRIES:
                    self._error = "Looking for the cameras..."
                    QTimer.singleShot(2000, self.start)
                else:
                    self._error = ("No camera found. Try again from Settings > Embedded Cameras (Repair), or restart the "
                                   "tablet.")
                self.changed.emit()
                return
            self._tries = 0
            self.select(self._key if self._key in self._cameras else ("front" if "front" in self._cameras else self._get_keys()[0]))

        @Slot()
        def retry(self):
            if self._recorder is None and self._preview is None:
                self._tries = 0
                self.start()

        @Slot(str)
        def select(self, key):
            if self._recorder is not None or key not in self._cameras:
                return
            self._stop_preview()
            self._key = key
            self._error = ""
            cam = self._cameras[key]
            try:
                self._preview = Gst.parse_launch(preview_description(cam["node"], *cam["size"]))
            except Exception as exc:          # noqa: BLE001 - GLib errors have no common base worth naming
                self._error = "Cannot start the camera: {}".format(exc)
                self.changed.emit()
                return
            if self._sink is not None:
                set_widget(self._preview.get_by_name("preview"), self._sink)
            # frames counted where they enter the GPU, for the watchdog (_watch_frames)
            self._preview.get_by_name("upload").get_static_pad("sink").add_probe(Gst.PadProbeType.BUFFER, self._on_frame)
            self._last_frame = time.monotonic() + 3      # the first frame takes a moment
            self._preview.set_state(Gst.State.PLAYING)
            self.changed.emit()
            self.settingsChanged.emit()

        @Slot()
        def next(self):
            # one switch a second at most: starting and stopping a camera in a burst of taps once left it running
            # without frames until the camera service restarted
            now = time.monotonic()
            if now - self._last_switch < SWITCH_INTERVAL:
                return
            self._last_switch = now
            keys = self._get_keys()
            if len(keys) > 1:
                self.select(keys[(keys.index(self._key) + 1) % len(keys)] if self._key in keys else keys[0])

        def _stop_preview(self):
            if self._preview is not None:
                self._preview.set_state(Gst.State.NULL)
                self._preview = None

        # -- preview frames, from GStreamer's streaming thread
        def _on_frame(self, pad, info):
            self._last_frame = time.monotonic()
            buf = info.get_buffer()
            # the length of the frames: the dark (the exposure at its longest) makes them long
            if buf.pts != Gst.CLOCK_TIME_NONE:
                if self._last_pts is not None and buf.pts > self._last_pts:
                    self._intervals = (self._intervals + [(buf.pts - self._last_pts) / 1e9])[-15:]
                    if len(self._intervals) >= 8:
                        median = sorted(self._intervals)[len(self._intervals) // 2]
                        dark = median > (NIGHT_OFF_INTERVAL if self._dark else NIGHT_ON_INTERVAL)
                        if dark != self._dark:
                            self._darkSeen.emit(dark)
                self._last_pts = buf.pts
            burst = self._burst
            if burst is not None:
                ok, mapping = buf.map(Gst.MapFlags.READ)
                if ok:
                    try:
                        if burst["skip"] > 0:
                            burst["skip"] -= 1
                        else:
                            burst["frames"].append(bytes(mapping.data))
                    finally:
                        buf.unmap(mapping)
                    if burst["info"] is None:
                        burst["info"] = GstVideo.VideoInfo.new_from_caps(pad.get_current_caps())
                if len(burst["frames"]) >= NIGHT_FRAMES:
                    self._burst = None
                    self._pause_tnr(False)
                    threading.Thread(target=self._save_night, args=(burst,), daemon=True).start()
                self._burstStep.emit(len(burst["frames"]) / NIGHT_FRAMES)
                return Gst.PadProbeReturn.OK
            path = self._photo_wanted
            if path:
                self._photo_wanted = ""
                sample = Gst.Sample.new(buf.copy_deep(), pad.get_current_caps(), None, None)
                threading.Thread(target=self._save_photo, args=(sample, path), daemon=True).start()
            return Gst.PadProbeReturn.OK

        def _burst_step(self, share):
            self._progress = share
            if share >= 1:
                self._busy = "Processing..."
            self.changed.emit()

        # -- photos
        @Slot()
        def takePhoto(self):
            if self._preview is None:
                return
            path = output_path(folder(QStandardPaths.StandardLocation.PicturesLocation, "Camera"), "photo")
            open(path, "xb").close()     # the name is taken now: the next photo of the same second gets another one
            if self._dark and not self._night_off:
                # a night photo: the next NIGHT_FRAMES frames, aligned and merged (nightmerge) on a thread of its own
                self._progress = 0.0
                self._busy = "Hold still"
                self.changed.emit()
                # libcamera's temporal average held back for the burst: raw frames merge into far less grain
                self._pause_tnr(True)
                self._burst = {"path": path, "frames": [], "info": None, "skip": NIGHT_SKIP}
                return
            # the next frame of the preview is copied and encoded (JPEG, up to a second) on a thread of its own
            self._photo_wanted = path

        @staticmethod
        def _encode_jpeg(sample, quality):
            """The frame as a JPEG of this quality (jpegenc; video_convert_sample has no quality setting)."""
            pipe = Gst.parse_launch("appsrc name=src ! videoconvert ! jpegenc quality={} ! appsink name=out sync=false".format(int(quality)))
            src, out = pipe.get_by_name("src"), pipe.get_by_name("out")
            src.set_property("caps", sample.get_caps())
            pipe.set_state(Gst.State.PLAYING)
            src.emit("push-buffer", sample.get_buffer())
            src.emit("end-of-stream")
            result = out.emit("try-pull-sample", 5 * Gst.SECOND)
            pipe.set_state(Gst.State.NULL)
            if result is None:
                raise OSError("the picture could not be encoded")
            return result.get_buffer()

        def _save_photo(self, sample, path):
            try:
                buf = self._encode_jpeg(sample, PHOTO_QUALITIES.get(self._photo_quality, JPEG_QUALITY))
                ok, mapping = buf.map(Gst.MapFlags.READ)
                if not ok:
                    raise OSError("cannot read the encoded picture")
                try:
                    with open(path + ".part", "wb") as f:
                        f.write(bytes(mapping.data))
                    os.replace(path + ".part", path)
                finally:
                    buf.unmap(mapping)
            except Exception as exc:          # noqa: BLE001 - GLib and OS errors alike end in a message
                for leftover in (path, path + ".part"):
                    try:
                        os.remove(leftover)
                    except OSError:
                        pass
                self.message.emit("The photo could not be saved: {}".format(exc))
                return
            self._last_capture = path
            self.changed.emit()
            self.capturesChanged.emit()

        def _pause_tnr(self, on):
            from overdrive import camera as cs
            if self._key not in cs.SENSORS:
                return
            try:
                cs.set_tnr_pause(self._key, time.time() + 3.0 if on else None)
            except OSError:
                pass

        def _save_night(self, burst):
            """The night frames merged into one photo. Frames come with the stride of the camera: made tight first."""
            path = burst["path"]
            try:
                import numpy as np
                from overdrive import nightmerge
                vi = burst["info"]
                w, h = vi.width, vi.height
                stride_y, stride_uv, off_uv = vi.stride[0], vi.stride[1], vi.offset[1]
                tight = []
                for data in burst["frames"]:
                    a = np.frombuffer(data, np.uint8)
                    y = a[:stride_y * h].reshape(h, stride_y)[:, :w]
                    uv = a[off_uv:off_uv + stride_uv * (h // 2)].reshape(h // 2, stride_uv)[:, :w]
                    tight.append(np.concatenate([y.reshape(-1), uv.reshape(-1)]))
                merged = nightmerge.merge(tight, w, h)
                caps = Gst.Caps.from_string("video/x-raw,format=NV12,width={},height={},framerate=0/1".format(w, h))
                sample = Gst.Sample.new(Gst.Buffer.new_wrapped(merged.tobytes()), caps, None, None)
            except Exception as exc:          # noqa: BLE001 - numpy or GStreamer: the photo is lost, say so
                self._night_done(path, None, "The night photo could not be made: {}".format(exc))
                return
            self._night_done(path, sample, "")

        def _night_done(self, path, sample, error):
            self._busy = ""
            self._progress = 0.0
            if sample is None:
                try:
                    os.remove(path)
                except OSError:
                    pass
                self.message.emit(error)
                self.changed.emit()
                return
            self._save_photo(sample, path)

        # -- videos
        @Slot()
        def toggleRecording(self):
            if self._recorder is None:
                self._start_recording()
            elif not self._stopping:
                self._stop_recording()

        def _start_recording(self):
            cam = self._cameras.get(self._key)
            if cam is None:
                return
            path = output_path(folder(QStandardPaths.StandardLocation.MoviesLocation, ""), "video")
            try:
                rec = Gst.parse_launch(record_description(cam["node"], *cam["size"], path, audio=self._audio,
                                                          quality=self._video_quality))
            except Exception as exc:          # noqa: BLE001
                self.message.emit("Cannot record: {}".format(exc))
                return
            self._recorder, self._recorded = rec, path
            self._stopping = False
            self._frames = 0
            # count the encoded frames (on GStreamer's thread): stopping before the first one has nothing to save
            parse = rec.get_by_name("parse")
            if parse is not None:
                def counted(pad, info):
                    self._frames += 1
                    return Gst.PadProbeReturn.OK
                parse.get_static_pad("src").add_probe(Gst.PadProbeType.BUFFER, counted)
            self._recording_since = datetime.datetime.now()
            rec.set_state(Gst.State.PLAYING)
            self.changed.emit()

        def _stop_recording(self):
            """End of a recording. EOS goes out on a thread of its own: sent to a camera source that has not delivered a
            frame yet it blocks, and on the window's thread that froze the app ("Not Responding"). A recording that never
            got a frame is thrown away, and one that does not finish within ten seconds is closed anyway."""
            rec = self._recorder
            self._stopping = True
            self.changed.emit()
            if self._frames == 0:
                self._finish_recording("Nothing recorded yet", discard=True)
                return
            self.message.emit("Saving the video...")
            threading.Thread(target=rec.send_event, args=(Gst.Event.new_eos(),), daemon=True).start()
            QTimer.singleShot(10000, lambda: self._recorder is rec and
                              self._finish_recording("The video took too long to save; it may be incomplete"))

        @Slot(result=str)
        def elapsed(self):
            if self._recording_since is None:
                return ""
            s = int((datetime.datetime.now() - self._recording_since).total_seconds())
            return "{:d}:{:02d}".format(s // 60, s % 60)

        def _finish_recording(self, note, discard=False):
            self._recorder.set_state(Gst.State.NULL)
            self._recorder = None
            self._recording_since = None
            self._stopping = False
            if discard:
                try:
                    os.remove(self._recorded)
                except OSError:
                    pass
            self.message.emit(note)
            self.changed.emit()
            self._last_frame = time.monotonic() + 3      # the preview gets its time again before the watchdog judges it
            if self._preview is None:
                QTimer.singleShot(500, self.retry)       # it had stopped during the recording: start it again

        def _watch_frames(self):
            """A preview without frames for STALL_SECONDS: start it again; the second time in a row, restart the camera
            service too (seen once after a burst of camera switches: the camera ran, no frame came)."""
            now = time.monotonic()
            if self._recorder is not None:
                return      # a recording owns the camera now; the preview is looked after again once it ends
            if self._preview is None or now - self._last_frame < STALL_SECONDS:
                if self._preview is not None and self._last_frame <= now:
                    self._stalls = 0                         # frames come: a later stall starts counting again
                return
            self._stalls += 1
            if self._stalls >= 2:
                from overdrive import camera as camera_settings
                subprocess.Popen(["systemctl", "--user", "restart", camera_settings.camera_service()],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self._stalls = 0
            key = self._key
            self._stop_preview()
            self._last_frame = time.monotonic() + 4      # time for the camera to come back before judging again
            QTimer.singleShot(1500, lambda: self._preview is None and self._recorder is None and self.select(key))

        def _poll(self):
            self._watch_frames()
            for pipe, is_rec in ((self._recorder, True), (self._preview, False)):
                if pipe is None:
                    continue
                bus = pipe.get_bus()
                while True:
                    msg = bus.pop_filtered(Gst.MessageType.EOS | Gst.MessageType.ERROR)
                    if msg is None:
                        break
                    if msg.type == Gst.MessageType.EOS and is_rec:
                        self._last_capture = self._recorded
                        self._finish_recording("Video saved")
                        self.capturesChanged.emit()
                        break
                    if msg.type == Gst.MessageType.ERROR:
                        err, _ = msg.parse_error()
                        if is_rec:
                            self._finish_recording("Recording stopped: {}".format(err.message))
                        else:
                            # the camera service restarted under us (a size changed in Settings, a repair): look again
                            self._error = "The camera stopped ({}). Starting it again...".format(err.message)
                            self._stop_preview()
                            self.changed.emit()
                            QTimer.singleShot(2000, self.retry)
                        break

        @Slot()
        def openFolder(self):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder(QStandardPaths.StandardLocation.PicturesLocation, "Camera")))

        @Slot()
        def openVideos(self):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder(QStandardPaths.StandardLocation.MoviesLocation, "")))

        @Slot()
        def shutdown(self):
            """Closing the window while recording keeps the video: EOS (on a thread, see _stop_recording) and up to
            five seconds for the file to be finished."""
            rec = self._recorder
            if rec is not None:
                if self._frames and not self._stopping:
                    threading.Thread(target=rec.send_event, args=(Gst.Event.new_eos(),), daemon=True).start()
                if self._frames:
                    rec.get_bus().timed_pop_filtered(5 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR)
                    self._finish_recording("")
                else:
                    self._finish_recording("", discard=True)
            self._stop_preview()
            if self._burst is not None:
                self._pause_tnr(False)
            # the backlight back where it was, whatever was lit
            if self._boosts:
                self._boosts = 1
                self._boost(False)

    QGuiApplication.setDesktopFileName(APP_ID)
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Camera")
    if not QIcon.themeName() or QIcon.themeName() == "hicolor":
        QIcon.setThemeName("breeze")      # started outside Plasma (no platform theme): the buttons would have no icons
    app.setWindowIcon(QIcon.fromTheme("camera-photo"))
    camera = Camera()
    previous = camera._get_captures()
    if previous:
        camera._last_capture = previous[0]
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("camera", camera)
    engine.rootContext().setContextProperty("backend", camera)   # the name camera_ui uses (its own "camera" is another)
    # the window is Plasma Camera's (camera_ui/, its QML on stand-ins for its C++ backend), in KDE's style
    from PySide6.QtQuickControls2 import QQuickStyle
    if not QQuickStyle.name():
        QQuickStyle.setStyle("org.kde.desktop")
    engine.load(QUrl.fromLocalFile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "camera_ui", "main.qml")))
    if not engine.rootObjects():
        return 1
    app.aboutToQuit.connect(camera.shutdown)

    class PenKeys(QObject):
        """The pen's button as the shutter while the app has the keyboard (KWin hands it to the active window)."""
        def eventFilter(self, obj, event):
            if event.type() in (QEvent.KeyPress, QEvent.ShortcutOverride) and is_pen_button(
                    event.nativeScanCode(), event.isAutoRepeat()):
                if event.type() == QEvent.KeyPress:
                    camera.penButton.emit()
                event.accept()
                return True
            if event.type() == QEvent.KeyRelease and event.nativeScanCode() in PEN_KEYCODES:
                return True
            return False
    pen_keys = PenKeys()
    app.installEventFilter(pen_keys)
    # the camera starts once the window has drawn its first frame: qml6glsink shares the window's OpenGL context, and
    # started before there was one it stopped after a few frames (the preview froze and the watchdog restarted it)
    window = engine.rootObjects()[0]
    started = []

    def first_frame():
        if not started:
            started.append(True)
            QTimer.singleShot(0, camera.start)
    window.frameSwapped.connect(first_frame)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
