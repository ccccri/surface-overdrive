"""NFC Forum Type 2 tag data: the TLV container and NDEF records. Pure functions, no I/O."""
import struct

URI_PREFIX = [
    "", "http://www.", "https://www.", "http://", "https://", "tel:", "mailto:",
    "ftp://anonymous:anonymous@", "ftp://ftp.", "ftps://", "sftp://", "smb://", "nfs://",
    "ftp://", "dav://", "news:", "telnet://", "imap:", "rtsp://", "urn:", "pop:", "sip:",
    "sips:", "tftp:", "btspp://", "btl2cap://", "btgoep://", "tcpobex://", "irdaobex://",
    "file://", "urn:epc:id:", "urn:epc:tag:", "urn:epc:pat:", "urn:epc:raw:", "urn:epc:",
    "urn:nfc:",
]


def tlv_ndef(data):
    """Find the NDEF TLV (0x03) in the data area of a tag.

    Returns the NDEF message when it is complete, b"" if the tag says it holds none,
    and None if more data has to be read first.
    """
    i = 0
    while i < len(data):
        tag = data[i]
        if tag == 0x00:                      # NULL TLV: padding
            i += 1
            continue
        if tag == 0xFE:                      # terminator
            return b""
        if i + 1 >= len(data):
            return None
        length = data[i + 1]
        header = 2
        if length == 0xFF:                   # three-byte length
            if i + 3 >= len(data):
                return None
            length = struct.unpack(">H", data[i + 2:i + 4])[0]
            header = 4
        if tag == 0x03:
            end = i + header + length
            return data[i + header:end] if len(data) >= end else None
        i += header + length
    return None


def parse_ndef(message, depth=0):
    """Turn an NDEF message into a list of {"kind": ..., "value": ...} records."""
    out = []
    i = 0
    while i < len(message):
        flags = message[i]
        tnf = flags & 0x07
        short = bool(flags & 0x10)
        has_id = bool(flags & 0x08)
        i += 1
        if i >= len(message):
            break
        type_len = message[i]
        i += 1
        if short:
            payload_len = message[i]
            i += 1
        else:
            payload_len = struct.unpack(">I", message[i:i + 4])[0]
            i += 4
        id_len = 0
        if has_id:
            id_len = message[i]
            i += 1
        rtype = message[i:i + type_len]
        i += type_len + id_len
        payload = message[i:i + payload_len]
        i += payload_len

        if tnf == 1 and rtype == b"U" and payload:
            prefix = URI_PREFIX[payload[0]] if payload[0] < len(URI_PREFIX) else ""
            out.append({"kind": "uri", "value": prefix + payload[1:].decode("utf-8", "replace")})
        elif tnf == 1 and rtype == b"T" and payload:
            lang_len = payload[0] & 0x3F
            encoding = "utf-16" if payload[0] & 0x80 else "utf-8"
            out.append({"kind": "text", "lang": payload[1:1 + lang_len].decode("ascii", "replace"),
                        "value": payload[1 + lang_len:].decode(encoding, "replace")})
        elif tnf == 1 and rtype == b"Sp" and depth < 3:
            out.append({"kind": "smartposter", "value": parse_ndef(payload, depth + 1)})
        elif tnf == 2:
            out.append({"kind": "mime", "value": rtype.decode("ascii", "replace"), "size": len(payload)})
        elif tnf == 4:
            out.append({"kind": "external", "value": rtype.decode("ascii", "replace")})
        else:
            out.append({"kind": "other", "value": "TNF %d %s" % (tnf, rtype.decode("ascii", "replace"))})
        if flags & 0x40:                     # message end
            break
    return out
