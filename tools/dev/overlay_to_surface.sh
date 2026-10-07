#!/usr/bin/env bash
# Try the files of the image on the Surface without building and installing a new image.
#
# usage: SURFACE_PW=<password> tools/dev/overlay_to_surface.sh [host, default cri@192.168.0.230]
#
# `rpm-ostree usroverlay` makes /usr writable until the next reboot. The files of image/rootfs and the Python package in src/ are copied to
# the places the image puts them, units are reloaded and the Overdrive services restarted. After a reboot the overlay is gone, so the real
# test is always an image built from the same tree.
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${SURFACE_PW:?set SURFACE_PW to the password of the account on the Surface}"
host=${1:-cri@192.168.0.230}
opts=(-o BatchMode=yes -o ConnectTimeout=6)
stamp=$(date +%H%M%S)

mkdir -p build
tar --owner=0 --group=0 -C image/rootfs -cf build/overlay.tar usr etc
tar --owner=0 --group=0 --transform 's#^#usr/lib/overdrive/python/#' -C src -rf build/overlay.tar overdrive --exclude='__pycache__'
scp -q "${opts[@]}" build/overlay.tar "$host:/tmp/overlay-$stamp.tar"

ssh "${opts[@]}" "$host" "SURFACE_PW='$SURFACE_PW' bash -s" <<REMOTE
set -e
run() { echo "\$SURFACE_PW" | sudo -S -p '' "\$@"; }
# usroverlay fails when it is already active: that is fine
run rpm-ostree usroverlay 2>&1 | tail -1 || true
run sh -c "tar -C / -xmf /tmp/overlay-$stamp.tar --no-same-owner --no-overwrite-dir && restorecon -R /usr/libexec/overdrive /usr/lib/overdrive /usr/lib/systemd /usr/share/libcamera 2>/dev/null; rm -f /tmp/overlay-$stamp.tar"
run systemctl daemon-reload
for unit in \$(ls /usr/lib/systemd/system/multi-user.target.wants 2>/dev/null | grep '^overdrive-'); do run systemctl restart "\$unit" || true; done
export XDG_RUNTIME_DIR=/run/user/\$(id -u)
systemctl --user daemon-reload
for unit in \$(ls /usr/lib/systemd/user/graphical-session.target.wants 2>/dev/null | grep '^overdrive-'); do systemctl --user restart "\$unit" || true; done
echo "overlay applied"
REMOTE
