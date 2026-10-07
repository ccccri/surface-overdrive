#!/usr/bin/env bash
# Install a locally built image on the Surface the way a user would, then log in by typing the password.
#
# usage: SURFACE_PW=<password> tools/dev/deploy_to_surface.sh [host, default cri@192.168.0.230]
# Needs build/surface-overdrive-44.tar (see ci/local-build.sh and `podman save --format oci-archive`) and an SSH key on the tablet.
# The password is read from the environment and is never written to a file.
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${SURFACE_PW:?set SURFACE_PW to the password of the account on the Surface}"
host=${1:-cri@192.168.0.230}
ssh_opts=(-o BatchMode=yes -o ConnectTimeout=6)
remote() { ssh "${ssh_opts[@]}" "$host" "$@"; }
rsudo() { remote "echo '$SURFACE_PW' | sudo -S -p '' $*"; }

archive=build/surface-overdrive-44.tar
[ -f "$archive" ] || { echo "$archive not found" >&2; exit 1; }
tag=$(date +%H%M)

echo "== keeping the tablet awake and freeing space"
remote 'nohup systemd-inhibit --what=sleep:idle --who="Surface Overdrive" --why="deploy" sleep 7200 >/dev/null 2>&1 &'
rsudo 'rm -f /var/tmp/surface-overdrive-*.tar'

echo "== copying $archive"
scp -q "${ssh_opts[@]}" "$archive" "$host:/var/tmp/surface-overdrive-$tag.tar"
sum_local=$(sha256sum "$archive" | cut -d' ' -f1)
sum_remote=$(remote "sha256sum /var/tmp/surface-overdrive-$tag.tar" | cut -d' ' -f1)
[ "$sum_local" = "$sum_remote" ] || { echo "checksum mismatch" >&2; exit 1; }

echo "== rebase (rpm-ostree cannot read the archive from the home directory: /var/tmp)"
rsudo "rpm-ostree rebase ostree-unverified-image:oci-archive:/var/tmp/surface-overdrive-$tag.tar" | tail -2
rsudo 'systemctl reboot' || true

echo "== waiting for the login screen"
sleep 25
until remote 'loginctl list-sessions --no-legend | grep -q greeter' 2>/dev/null; do sleep 5; done
sleep 8
scp -q "${ssh_opts[@]}" tools/dev/uinput_type.py "$host:/tmp/"
echo "== typing the password on the login screen"
remote "printf '%s\n%s\n' '$SURFACE_PW' '$SURFACE_PW' | sudo -S -p '' python3 /tmp/uinput_type.py --enter --delay 1.5"
sleep 25
remote 'loginctl list-sessions --no-legend | grep seat0'
# WirePlumber must start after the graphical login, otherwise it finds no cameras (see docs/TEST-RESULTS.md, test 1)
remote 'export XDG_RUNTIME_DIR=/run/user/$(id -u); systemctl --user restart wireplumber'
echo "== done"
