"""Reading an NFC Forum Type 2 tag (NTAG, MIFARE Ultralight) through a raw NFC socket."""
import ctypes
import errno
import os
import socket
import struct

from .ndef import parse_ndef, tlv_ndef
from .netlink import PROTO

AF_NFC = 39
NFC_SOCKPROTO_RAW = 0
# Give up reading a tag after this long. It must be longer than the kernel's own NCI data timeout (3 s): closing the socket and
# sending RF_DEACTIVATE while a data exchange is still in flight makes the controller never answer, and the kernel then waits 30 s
# (NCI_RF_DEACTIVATE_TIMEOUT) with the whole NFC stack blocked.
RAW_TIMEOUT_S = 3.3

_libc = ctypes.CDLL(None, use_errno=True)


def _connect(sock, device_index, target_index, protocol):
    # struct sockaddr_nfc { sa_family_t (u16); u32 dev_idx; u32 target_idx; u32 nfc_protocol; }
    address = struct.pack("HxxIII", AF_NFC, device_index, target_index, protocol)
    if _libc.connect(sock.fileno(), address, len(address)) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))


def _read_pages(sock, page):
    """READ command: 16 bytes = pages page..page+3. The kernel prepends a status byte (0 = ok)."""
    sock.send(bytes([0x30, page]))
    response = sock.recv(64)
    if len(response) < 17 or response[0] != 0:
        raise OSError(errno.EIO, "read failed")
    return response[1:17]


def _read_ndef_message(sock):
    """The raw NDEF message of a Type 2 tag, b"" if it holds none."""
    capability = _read_pages(sock, 3)[:4]
    if capability[0] != 0xE1:
        return b""                               # not NFC Forum formatted
    limit = capability[2] * 8                    # size of the data area in bytes
    data = b""
    page = 4
    while len(data) < limit and page < 4 + limit // 4 + 4:
        data += _read_pages(sock, page)
        page += 4
        message = tlv_ndef(data)
        if message is not None:
            return message
    return b""


def read_tag(adapter, target, log=print):
    """Activate the tag, read its NDEF records and always release it.

    Returns the record list, or None for a tag that is not Type 2 or that could not be read (only the UID is then known).
    """
    if not target["protos"] & (1 << PROTO["MIFARE"]):
        return None
    sock = socket.socket(AF_NFC, socket.SOCK_SEQPACKET, NFC_SOCKPROTO_RAW)
    sock.settimeout(RAW_TIMEOUT_S)
    activated = False
    try:
        _connect(sock, adapter.index, target["idx"], PROTO["MIFARE"])
        activated = True
        return parse_ndef(_read_ndef_message(sock))
    except (OSError, socket.timeout, IndexError, struct.error) as exc:
        log("read failed: %s" % exc)
        return None
    finally:
        sock.close()
        if activated:                            # without this the kernel refuses to poll again
            adapter.deactivate(target["idx"])
