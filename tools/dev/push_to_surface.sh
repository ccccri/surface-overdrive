#!/usr/bin/env bash
# Fast path to a new image on the Surface: build, publish to a local registry on this desktop, let the tablet pull only the layers
# that changed, reboot and log in.
#
# usage: SURFACE_PW=<password> tools/dev/push_to_surface.sh [host, default cri@192.168.0.230]
#
# The tablet reaches the registry through a reverse SSH tunnel (the desktop's firewall stays closed; SELinux on the tablet only lets sshd
# listen on some ports, 50000 works). It needs /etc/containers/registries.conf.d/50-overdrive-dev.conf marking localhost:50000 insecure.
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${SURFACE_PW:?set SURFACE_PW to the password of the account on the Surface}"
host=${1:-cri@192.168.0.230}
opts=(-o BatchMode=yes -o ConnectTimeout=6)
remote() { ssh "${opts[@]}" "$host" "$@"; }
rsudo() { remote "echo '$SURFACE_PW' | sudo -S -p '' $*"; }

echo "== registry"
podman container exists so-registry || podman run -d --name so-registry -p 127.0.0.1:5000:5000 -v so-registry-data:/var/lib/registry quay.io/libpod/registry:2.8 >/dev/null
podman start so-registry >/dev/null 2>&1 || true

echo "== build"
ci/local-build.sh 44 >/tmp/overdrive-build.log 2>&1 || { tail -20 /tmp/overdrive-build.log; exit 1; }
podman push -q --tls-verify=false localhost/surface-overdrive:44 docker://127.0.0.1:5000/surface-overdrive:44

echo "== tunnel"
remote 'curl -s -m 4 http://localhost:50000/v2/ >/dev/null' 2>/dev/null \
    || ssh -f -N "${opts[@]}" -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -R 127.0.0.1:50000:127.0.0.1:5000 "$host"

echo "== pull on the tablet"
if remote 'rpm-ostree status' | grep -q 'registry:localhost:50000'; then
    rsudo 'rpm-ostree upgrade' | tail -3
else
    rsudo 'rpm-ostree rebase ostree-unverified-registry:localhost:50000/surface-overdrive:44' | tail -3
fi

echo "== reboot and login"
rsudo 'systemctl reboot' || true
sleep 25
until remote 'loginctl list-sessions --no-legend | grep -q greeter' 2>/dev/null; do sleep 5; done
sleep 8
scp -q "${opts[@]}" tools/dev/uinput_type.py "$host:/tmp/"
remote "printf '%s\n%s\n' '$SURFACE_PW' '$SURFACE_PW' | sudo -S -p '' python3 /tmp/uinput_type.py --enter --delay 2"
sleep 25
remote 'loginctl list-sessions --no-legend | grep seat0'
remote 'export XDG_RUNTIME_DIR=/run/user/$(id -u); systemctl --user restart wireplumber'
echo "== done"
