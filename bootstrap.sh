#!/usr/bin/env bash
# Surface Overdrive bootstrap: moves a Fedora Kinoite install onto the Surface Overdrive image with ONE reboot.
#
#   curl -L ccccri.github.io | bash
#
# What happens:
#   1. this script checks that this is Fedora Kinoite (on a Surface Go) and fetches the installer (installer/install.py,
#      installer/root-step.sh) and the module signing certificate;
#   2. the installer's screen shows the machine and asks for the administrator password once, in a window (pkexec; in
#      the terminal with sudo when there is no desktop);
#   3. as the administrator (root-step.sh): when Secure Boot is on and the certificate is not enrolled yet, a window asks
#      for a one-time password and the certificate is queued for enrolment (MOK); then the system switches to the image
#      (rpm-ostree rebase), downloaded now and used at the next start. The screen follows it with a little show and the
#      numbers (percentage, layer, amounts, speed, time left); rpm-ostree's whole output is in ~/surface-overdrive-install.log;
#   4. you restart: only if the certificate was queued, the blue "MOK management" screen appears once (Enroll MOK, type
#      the one-time password);
#   5. the system starts on the new image. Updates come by themselves from then on.
# Nothing is compiled on this machine. Run it as your normal user.
set -euo pipefail

REPO=${OVERDRIVE_REPO:-ccccri/surface-overdrive}
REF=${OVERDRIVE_REF:-main}
RAW=https://raw.githubusercontent.com/$REPO/$REF
# the Fedora release the image is built for (CI builds this one only); an older Kinoite moves up with the rebase
rel=${OVERDRIVE_RELEASE:-45}
image=${OVERDRIVE_IMAGE:-ostree-unverified-registry:ghcr.io/$REPO:$rel}

die() { printf 'error: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -ne 0 ] || die "run it as your normal user, not as root"
. /etc/os-release
[ "${VARIANT_ID:-}" = kinoite ] || die "this is not Fedora Kinoite (found: ${PRETTY_NAME:-unknown})"
command -v rpm-ostree >/dev/null || die "rpm-ostree is missing"
command -v python3 >/dev/null || die "python3 is missing"
model=$(cat /sys/class/dmi/id/product_name 2>/dev/null || true)
if [ "$model" != "Surface Go" ]; then
    printf 'warning: this is "%s", not a Surface Go (1824). The fixes are made for the Surface Go only.\n' "$model"
    printf 'Go on anyway? [y/N] '
    read -r answer
    [ "$answer" = y ] || [ "$answer" = Y ] || exit 1
fi

dir=$(mktemp -d)
trap 'rm -rf "$dir"' EXIT
printf 'Fetching the installer...\n'
for f in installer/install.py installer/root-step.sh ci/mok.der; do
    curl -fsSL --retry 3 "$RAW/$f" -o "$dir/$(basename "$f")" || die "could not download $f (is the network up?)"
done
python3 "$dir/install.py" --cert "$dir/mok.der" --helper "$dir/root-step.sh" --image "$image"
