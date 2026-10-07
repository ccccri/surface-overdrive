"""Generic netlink client for the kernel NFC subsystem (family "nfc")."""
import errno
import select
import socket
import struct
import time

NETLINK_GENERIC = 16
NLM_F_REQUEST, NLM_F_ACK, NLM_F_DUMP = 1, 4, 0x300
NLMSG_ERROR, NLMSG_DONE = 2, 3
GENL_ID_CTRL = 0x10
CTRL_CMD_GETFAMILY = 3

CMD = {"DEV_UP": 2, "DEV_DOWN": 3, "START_POLL": 6, "STOP_POLL": 7, "GET_TARGET": 8,
       "TARGETS_FOUND": 9, "DEACTIVATE_TARGET": 30}
ATTR = {"DEVICE_INDEX": 1, "PROTOCOLS": 3, "TARGET_INDEX": 4, "SENS_RES": 5, "SEL_RES": 6,
        "NFCID1": 7, "IM_PROTOCOLS": 13}
PROTO = {"JEWEL": 1, "MIFARE": 2, "FELICA": 3, "ISO14443": 4, "NFC_DEP": 5, "ISO14443_B": 6, "ISO15693": 7}
POLL_PROTOCOLS = sum(1 << PROTO[n] for n in ("MIFARE", "FELICA", "ISO14443", "ISO14443_B"))
PROTO_LABEL = {"MIFARE": "Type 2", "JEWEL": "Type 1", "FELICA": "Type 3 (FeliCa)",
               "ISO14443": "ISO-DEP (Type 4)", "ISO14443_B": "ISO-DEP B", "ISO15693": "ISO 15693",
               "NFC_DEP": "NFC-DEP"}
SLOW_CALL_S = 1.0


def proto_label(protocols):
    """Human name of the first protocol set in the bit mask."""
    for name in ("MIFARE", "JEWEL", "FELICA", "ISO14443", "ISO14443_B", "ISO15693", "NFC_DEP"):
        if protocols & (1 << PROTO[name]):
            return PROTO_LABEL[name]
    return "tag"


def attribute(kind, data):
    length = 4 + len(data)
    return struct.pack("HH", length, kind) + data + b"\0" * ((4 - length % 4) % 4)


def parse_attributes(data):
    out = {}
    while len(data) >= 4:
        length, kind = struct.unpack_from("HH", data)
        if length < 4:
            break
        out[kind & 0x3FFF] = data[4:length]
        data = data[(length + 3) & ~3:]
    return out


def u32(value):
    return struct.pack("I", value)


class NfcNetlink:
    """One netlink socket, subscribed to the NFC multicast group."""

    def __init__(self, log=print):
        self._log = log
        self.sock = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, NETLINK_GENERIC)
        self.sock.bind((0, 0))
        self.seq = 1
        self.events = []                       # multicast events that arrived while a reply was awaited
        self.family = self.group = None
        self._resolve()
        self.sock.setsockopt(270, 1, self.group)   # SOL_NETLINK, NETLINK_ADD_MEMBERSHIP

    @staticmethod
    def _messages(data):
        while len(data) >= 16:
            length, kind, flags, seq, pid = struct.unpack_from("IHHII", data)
            if length < 16:
                break
            yield kind, flags, data[16:length]
            data = data[(length + 3) & ~3:]

    def _send(self, family, cmd, attrs, flags):
        self.seq += 1
        generic = struct.pack("BBH", cmd, 1, 0) + attrs
        self.sock.send(struct.pack("IHHII", 16 + len(generic), family, flags, self.seq, 0) + generic)

    def _resolve(self):
        self._send(GENL_ID_CTRL, CTRL_CMD_GETFAMILY, attribute(2, b"nfc\0"), NLM_F_REQUEST)
        for kind, _flags, body in self._messages(self.sock.recv(65536)):
            if kind == NLMSG_ERROR:
                raise RuntimeError("the kernel has no NFC netlink family")
            attrs = parse_attributes(body[4:])
            self.family = struct.unpack("H", attrs[1])[0]
            for group in parse_attributes(attrs.get(7, b"")).values():
                group_attrs = parse_attributes(group)
                if group_attrs.get(1, b"").rstrip(b"\0") == b"events":
                    self.group = struct.unpack("I", group_attrs[2])[0]

    def call(self, cmd, attrs=b"", dump=False):
        """Send a command; return (errno, [reply attribute dicts]). Events that arrive meanwhile are kept."""
        started = time.monotonic()
        err, replies = self._call(cmd, attrs, dump)
        took = time.monotonic() - started
        if took > SLOW_CALL_S:                   # the kernel blocks on NCI timeouts (5 s, 30 s for RF_DEACTIVATE)
            self._log("slow netlink call cmd=%d took %.1f s (%s)" % (cmd, took, errno.errorcode.get(err, err)))
        return err, replies

    def _call(self, cmd, attrs, dump):
        self._send(self.family, cmd, attrs, NLM_F_REQUEST | (NLM_F_DUMP if dump else NLM_F_ACK))
        replies = []
        while True:
            for kind, _flags, body in self._messages(self.sock.recv(65536)):
                if kind == NLMSG_ERROR:
                    return -struct.unpack_from("i", body)[0], replies
                if kind == NLMSG_DONE:
                    return 0, replies
                if kind == self.family:
                    if body[0] == CMD["TARGETS_FOUND"]:
                        self.events.append("targets")
                    elif body[0] == cmd:
                        replies.append(parse_attributes(body[4:]))

    def wait_targets(self, timeout):
        """Block until the kernel reports targets or the timeout passes. True if targets were found."""
        if self.events:
            self.events.clear()
            return True
        if not select.select([self.sock], [], [], timeout)[0]:
            return False
        for kind, _flags, body in self._messages(self.sock.recv(65536)):
            if kind == self.family and body[0] == CMD["TARGETS_FOUND"]:
                return True
        return False


class Adapter:
    """The first NFC adapter (nfc0)."""

    def __init__(self, netlink, index=0):
        self.nl = netlink
        self.index = index
        self._dev = attribute(ATTR["DEVICE_INDEX"], u32(index))

    def up(self):
        return self.nl.call(CMD["DEV_UP"], self._dev)[0]

    def down(self):
        return self.nl.call(CMD["DEV_DOWN"], self._dev)[0]

    def start_poll(self):
        return self.nl.call(CMD["START_POLL"], self._dev + attribute(ATTR["IM_PROTOCOLS"], u32(POLL_PROTOCOLS)))[0]

    def stop_poll(self):
        return self.nl.call(CMD["STOP_POLL"], self._dev)[0]

    def targets(self):
        _err, replies = self.nl.call(CMD["GET_TARGET"], self._dev, dump=True)
        out = []
        for attrs in replies:
            if ATTR["TARGET_INDEX"] not in attrs:
                continue
            out.append({
                "idx": struct.unpack("I", attrs[ATTR["TARGET_INDEX"]])[0],
                "protos": struct.unpack("I", attrs[ATTR["PROTOCOLS"]])[0] if ATTR["PROTOCOLS"] in attrs else 0,
                "uid": attrs.get(ATTR["NFCID1"], b""),
            })
        return out

    def deactivate(self, target_index):
        return self.nl.call(CMD["DEACTIVATE_TARGET"], self._dev + attribute(ATTR["TARGET_INDEX"], u32(target_index)))[0]

    def release_stale_targets(self):
        """Clear an "active target" left behind by a crashed run, so that polling can start."""
        for target in self.targets():
            self.deactivate(target["idx"])
