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


def video_bitrate(width, height):
    """H.264 bit rate in kbit/s: 2.5 per thousand pixels a frame, at least 4000 (12000 at 2560x1920)."""
    return max(4000, round(width * height / 1e6 * 2.5) * 1000)


def preview_description(node, width, height):
    # One branch only: with a tee and an appsink for photos next to qml6glsink, the preview froze after four frames
    # (2026-10-27). A photo is a copy of the frame going to the preview at the time of the tap (Camera._on_frame).
    return ("pipewiresrc target-object={node} ! video/x-raw,format=NV12,width={w},height={h} "
            "! queue leaky=downstream max-size-buffers=1 ! glupload name=upload ! glcolorconvert "
            "! qml6glsink name=preview sync=false").format(node=node, w=width, h=height)


def record_description(node, width, height, path, audio=True):
    video = ("pipewiresrc target-object={node} ! video/x-raw,format=NV12,width={w},height={h} ! queue max-size-buffers=8 "
             "! vapostproc ! vah264enc bitrate={rate} ! h264parse name=parse ! queue ! mux. "
             ).format(node=node, w=width, h=height, rate=video_bitrate(width, height))
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


# ---- The app

def main():
    import gi
    gi.require_version("Gst", "1.0")
    gi.require_version("GstApp", "1.0")
    gi.require_version("GstVideo", "1.0")
    from gi.repository import Gst, GstVideo
    from PySide6.QtCore import Property, QObject, QStandardPaths, QTimer, QUrl, Signal, Slot
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
            return self._last_capture.endswith(".mp4")

        key = Property(str, _get_key, notify=changed)
        keys = Property("QVariantList", _get_keys, notify=changed)
        labels = Property("QVariantList", _get_labels, notify=changed)
        size = Property(str, _get_size, notify=changed)
        recording = Property(bool, _get_recording, notify=changed)
        error = Property(str, _get_error, notify=changed)
        mirrored = Property(bool, _get_mirrored, notify=changed)
        lastCapture = Property(str, _get_last, notify=changed)
        lastIsVideo = Property(bool, _get_last_is_video, notify=changed)

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
            path = self._photo_wanted
            if path:
                self._photo_wanted = ""
                sample = Gst.Sample.new(info.get_buffer().copy_deep(), pad.get_current_caps(), None, None)
                threading.Thread(target=self._save_photo, args=(sample, path), daemon=True).start()
            return Gst.PadProbeReturn.OK

        # -- photos
        @Slot()
        def takePhoto(self):
            if self._preview is None:
                return
            path = output_path(folder(QStandardPaths.StandardLocation.PicturesLocation, "Camera"), "photo")
            open(path, "xb").close()     # the name is taken now: the next photo of the same second gets another one
            # the next frame of the preview is copied and encoded (JPEG, up to a second) on a thread of its own
            self._photo_wanted = path

        def _save_photo(self, sample, path):
            try:
                jpeg = GstVideo.video_convert_sample(sample, Gst.Caps.from_string("image/jpeg"), 5 * Gst.SECOND)
                buf = jpeg.get_buffer()
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
                rec = Gst.parse_launch(record_description(cam["node"], *cam["size"], path))
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

    QGuiApplication.setDesktopFileName(APP_ID)
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Camera")
    if not QIcon.themeName() or QIcon.themeName() == "hicolor":
        QIcon.setThemeName("breeze")      # started outside Plasma (no platform theme): the buttons would have no icons
    app.setWindowIcon(QIcon.fromTheme("camera-photo"))
    camera = Camera()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("camera", camera)
    engine.load(QUrl.fromLocalFile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cameraapp.qml")))
    if not engine.rootObjects():
        return 1
    app.aboutToQuit.connect(camera.shutdown)
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
