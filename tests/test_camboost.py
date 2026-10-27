import json
import unittest

from overdrive import camboost


def node(oid, name, state=None):
    info = {"props": {"node.name": name}}
    if state:
        info["state"] = state
    return {"id": oid, "type": "PipeWire:Interface:Node", "info": info}


def dump(objs):
    return json.dumps(objs, indent=2) + "\n"


class CameraWatchTest(unittest.TestCase):
    def test_running_camera_and_back(self):
        w = camboost.CameraWatch()
        self.assertFalse(w.feed(dump([node(5, "libcamera_input.__SB_.PCI0.LNK1", "suspended"), node(6, "alsa_output.x", "running")])))
        # an update carries only what changed: no props
        self.assertTrue(w.feed(dump([{"id": 5, "type": "PipeWire:Interface:Node", "info": {"state": "running"}}])))
        self.assertFalse(w.feed(dump([{"id": 5, "type": "PipeWire:Interface:Node", "info": {"state": "idle"}}])))

    def test_removed_node_stops_counting(self):
        w = camboost.CameraWatch()
        self.assertTrue(w.feed(dump([node(7, "libcamera_input.__SB_.PCI0.LNK0", "running")])))
        self.assertFalse(w.feed(dump([{"id": 7, "type": "PipeWire:Interface:Node", "info": None}])))

    def test_output_in_pieces(self):
        w = camboost.CameraWatch()
        text = dump([node(5, "libcamera_input.__SB_.PCI0.LNK1", "running")])
        lines = text.splitlines(keepends=True)
        for line in lines[:-1]:
            self.assertFalse(w.feed(line))
        self.assertTrue(w.feed(lines[-1]))


if __name__ == "__main__":
    unittest.main()
