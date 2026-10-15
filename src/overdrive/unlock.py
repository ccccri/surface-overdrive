"""Unlock with a PIN or a pattern, next to the password.

A tablet without its keyboard cover is unlocked many times a day with the on-screen keyboard: a short PIN on a keypad, or a pattern
drawn over nine dots, is quicker. The password keeps working everywhere; the PIN or pattern is accepted only where the screen is
unlocked or a session starts (the lock screen and the login screen), never by sudo, polkit or the keyring.

How it fits together:
  - the choice of the user is kept in STORE/<user>/: `secret` (scrypt hash of the code, root:<user group> 0640), an empty picture
    `pin.svg` or `pattern.svg` that the lock and login screens look for to know which pad to show (with `pin-length-<n>.svg`,
    so that the keypad tries the PIN at its last digit), and `state/` (tries, block);
  - the PAM services of the lock screen ("kde") and of the login screen ("plasmalogin") ask CHECK first (pam_exec, see
    ci/patch_pam.py): when the typed text is the code the user is in, otherwise PAM goes on with the password as before;
  - after MAX_TRIES wrong codes the pad is off until the password is used once: the lock screen then shows the password field.
    The session clears the block when it starts and at every unlock (overdrive-osk-guard watches the lock state already).
  - the code is set or removed through polkit (`unlock` helper), after the password of the user: the only way to write STORE.

The lock screen runs as the user, the login screen as root: both read the secret, the state directory is writable by the group of
the user. Anyone with the rights of the user can change all this anyway, the point is that nobody at the screen can.
"""
import hashlib
import hmac
import json
import os
import pwd
import secrets
import shutil
import sys

STORE = "/var/lib/surface-overdrive/unlock"
KINDS = ("pin", "pattern")
MAX_TRIES = 5
# scrypt cost: about a tenth of a second on the Pentium 4415Y, small next to PAM's two-second delay after a wrong try
SCRYPT = {"n": 1 << 14, "r": 8, "p": 1}
MARKER = '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>\n'
LONGEST = 64                                     # longer text is a password, not a code: never hashed


def valid(kind, code):
    """A PIN is 4 to 12 digits; a pattern is 4 to 9 of the dots 1-9 (left to right, top to bottom), each at most once."""
    if not isinstance(code, str) or not code.isascii():
        return False
    if kind == "pin":
        return code.isdigit() and 4 <= len(code) <= 12
    if kind == "pattern":
        return 4 <= len(code) <= 9 and all(c in "123456789" for c in code) and len(set(code)) == len(code)
    return False


def _user_dir(user, store):
    if not user or "/" in user or user in (".", ".."):
        raise ValueError("bad user name")
    return os.path.join(store, user)


def _digest(code, salt, cost):
    return hashlib.scrypt(code.encode(), salt=salt, n=cost["n"], r=cost["r"], p=cost["p"], maxmem=64 << 20, dklen=32)


def _write(path, text, mode, uid=None, gid=None):
    tmp = path + ".new"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, mode)
    try:
        os.write(fd, text.encode())
        os.fchmod(fd, mode)
        if uid is not None and os.geteuid() == 0:
            os.fchown(fd, uid, gid)
    finally:
        os.close(fd)
    os.replace(tmp, path)


def _length_marks(d):
    try:
        return [n for n in os.listdir(d) if n.startswith("pin-length-") and n.endswith(".svg")]
    except OSError:
        return []


def status(user, store=STORE):
    """{"kind": "pin"|"pattern"|"", "blocked": bool, "length": digits of the PIN or 0}. Readable by anyone: it is what the lock
    and login screens show. The length lets the keypad try the PIN as soon as the last digit is typed, with no Enter (the
    screen shows one dot per digit anyway)."""
    d = _user_dir(user, store)
    kind = next((k for k in KINDS if os.path.isfile(os.path.join(d, k + ".svg"))), "")
    length = 0
    if kind == "pin":
        for name in _length_marks(d):
            digits = name[len("pin-length-"):-len(".svg")]
            if digits.isdigit():
                length = int(digits)
    return {"kind": kind, "blocked": bool(kind) and os.path.isfile(os.path.join(d, "state", "blocked.svg")), "length": length}


def set_code(user, kind, code, store=STORE):
    """Keep the hash of a new PIN or pattern for user (root only), replacing the previous one and clearing the tries."""
    if kind not in KINDS or not valid(kind, code):
        raise ValueError("a %s must be %s" % (kind, "4 to 12 digits" if kind == "pin" else "at least 4 dots"))
    gid = pwd.getpwnam(user).pw_gid
    d = _user_dir(user, store)
    os.makedirs(store, 0o755, exist_ok=True)
    os.makedirs(d, 0o755, exist_ok=True)
    os.chmod(d, 0o755)
    state = os.path.join(d, "state")
    os.makedirs(state, 0o775, exist_ok=True)
    if os.geteuid() == 0:
        os.chown(d, 0, 0)
        os.chown(state, 0, gid)
    os.chmod(state, 0o775)
    salt = secrets.token_bytes(16)
    record = dict(SCRYPT, kind=kind, salt=salt.hex(), hash=_digest(code, salt, SCRYPT).hex())
    _write(os.path.join(d, "secret"), json.dumps(record) + "\n", 0o640, 0, gid)
    _write(os.path.join(d, kind + ".svg"), MARKER, 0o644, 0, 0)
    for other in KINDS:
        if other != kind:
            _remove(os.path.join(d, other + ".svg"))
    for name in _length_marks(d):
        _remove(os.path.join(d, name))
    if kind == "pin":
        _write(os.path.join(d, "pin-length-%d.svg" % len(code)), MARKER, 0o644, 0, 0)
    passed(user, store)
    return status(user, store)


def clear(user, store=STORE):
    """Back to the password only (root only)."""
    d = _user_dir(user, store)
    if os.path.isdir(d):
        shutil.rmtree(d)
    return status(user, store)


def _remove(path):
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def passed(user, store=STORE):
    """The user is in (password or code): forget the wrong tries and lift the block."""
    state = os.path.join(_user_dir(user, store), "state")
    for name in ("tries", "blocked.svg"):
        _remove(os.path.join(state, name))


def _failed(state, gid):
    path = os.path.join(state, "tries")
    try:
        with open(path) as f:
            tries = int(f.read().strip() or 0)
    except (OSError, ValueError):
        tries = 0
    tries += 1
    _write(path, "%d\n" % tries, 0o660, 0, gid)
    if tries >= MAX_TRIES:
        _write(os.path.join(state, "blocked.svg"), MARKER, 0o644, 0, gid)
    return tries


def check(user, token, store=STORE):
    """True when token is the code of user. None when the user has no code. A wrong code counts towards the block; text that
    cannot be a code (a password with letters, say) is not a try and does not count."""
    d = _user_dir(user, store)
    try:
        with open(os.path.join(d, "secret")) as f:
            record = json.load(f)
        salt = bytes.fromhex(record["salt"])
        expected = bytes.fromhex(record["hash"])
        kind = record["kind"]
        cost = {k: int(record[k]) for k in ("n", "r", "p")}
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if status(user, store)["blocked"] or len(token) > LONGEST or not valid(kind, token):
        return False
    if hmac.compare_digest(_digest(token, salt, cost), expected):
        passed(user, store)
        return True
    try:
        _failed(os.path.join(d, "state"), pwd.getpwnam(user).pw_gid)
    except OSError:
        pass
    return False


def pam_main():
    """pam_exec ... expose_authtok: the typed text arrives on stdin, the user in PAM_USER. Exit 0 lets the user in."""
    user = os.environ.get("PAM_USER", "")
    try:
        if os.getuid() != 0 and pwd.getpwuid(os.getuid()).pw_name != user:
            return 1                             # the lock screen of one user cannot try the code of another
        token = sys.stdin.buffer.read(4096).rstrip(b"\0").decode("utf-8", "replace")
        return 0 if check(user, token) else 1
    except (OSError, ValueError, KeyError):
        return 1


def helper_main(argv=None):
    """Run by pkexec: `unlock set pin|pattern` (the code on stdin) or `unlock clear`, for the user who asked."""
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        user = pwd.getpwuid(int(os.environ["PKEXEC_UID"])).pw_name
    except (KeyError, ValueError):
        print("error: run through pkexec", file=sys.stderr)
        return 2
    try:
        if argv[:1] == ["set"] and len(argv) == 2:
            out = set_code(user, argv[1], sys.stdin.read(4096).strip())
        elif argv == ["clear"]:
            out = clear(user)
        else:
            print("usage: unlock set pin|pattern < code | unlock clear", file=sys.stderr)
            return 2
    except (OSError, ValueError, KeyError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    print(json.dumps(out))
    return 0
