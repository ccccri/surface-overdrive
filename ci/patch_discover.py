#!/usr/bin/env python3
"""Discover no longer shows "Update Issue" for its own second firmware metadata download, in its source tree.

At start Discover checks for updates twice in a row, and its fwupd backend refreshes the LVFS remote both times. fwupd's
client refuses a second download of the same file within 1.5 s ("attempted previous download of
https://cdn.fwupd.org/downloads/firmware.xml.zst.jcat from plasma-discover just 847ms ago", FWUPD_ERROR_NOT_REACHABLE) and
Discover showed that refusal as an error at every start, although the first download had worked (seen on the tablet,
2026-11-10, Discover 6.8.2 with fwupd 2.1.9). That refusal is now ignored; other errors, a real network failure among
them, are still shown.

When the file has a layout this was not written for, nothing is changed and the build goes on with Fedora's package. The
same when it already knows about that refusal (Discover's own fix): then this patch (with ci/build_discover.sh and its
stage in the Containerfile) can go.

usage: patch_discover.py <source tree>
"""
import sys
from pathlib import Path

REL = "libdiscover/backends/FwupdBackend/FwupdBackend.cpp"
OLD = """    const bool successful = fwupd_client_refresh_remote_finish(helper->client, res, &error);
    if (!successful)
        helper->handleError(error);
"""
NEW = """    const bool successful = fwupd_client_refresh_remote_finish(helper->client, res, &error);
    // Surface Overdrive: fwupd refuses a second download of the same metadata within 1.5 s, and Discover refreshes
    // twice at start: that refusal is no error for the user (the first download went through).
    if (!successful && g_error_matches(error, FWUPD_ERROR, FWUPD_ERROR_NOT_REACHABLE)
        && QByteArray(error->message).contains("attempted previous download"))
        return;
    if (!successful)
        helper->handleError(error);
"""


def patch(root):
    path = Path(root) / REL
    if not path.exists():
        print("skipped: %s not found" % REL)
        return False
    text = path.read_text()
    if "attempted previous download" in text:
        print("skipped: %s already knows fwupd's repeated download (fixed by Discover, Fedora's package is fine)" % REL)
        return False
    if text.count(OLD) != 1:
        print("skipped: %s has another layout" % REL)
        return False
    path.write_text(text.replace(OLD, NEW))
    print("patched: no Update Issue for fwupd's repeated metadata download")
    return True


if __name__ == "__main__":
    patch(sys.argv[1])
