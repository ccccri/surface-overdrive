#!/usr/bin/env bash
# Surface Overdrive bootstrap: moves a Fedora Kinoite install onto the Surface Overdrive image with ONE reboot.
#
#   curl -L ccccri.github.io | bash
#
# What it does, in order:
#   1. checks that this is Fedora Kinoite on a Surface Go and that Secure Boot is on;
#   2. asks you to choose a one-time password and registers the module signing certificate with it (MOK);
#   3. switches the system to the image (rpm-ostree rebase), which is downloaded now and used at the next boot;
#   4. you restart: the blue "MOK management" screen appears once, choose "Enroll MOK", type the one-time password;
#   5. the system starts on the new image. Updates come by themselves from then on.
# Nothing is compiled on this machine. Run it as your normal user: it asks for the administrator password where needed.
set -euo pipefail

REPO=${OVERDRIVE_REPO:-ccccri/surface-overdrive}
RAW=https://raw.githubusercontent.com/$REPO/main
rel=${OVERDRIVE_RELEASE:-$(. /etc/os-release && echo "$VERSION_ID")}
image=${OVERDRIVE_IMAGE:-ostree-unverified-registry:ghcr.io/$REPO:$rel}

say() { printf '\n== %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

say "Checking this machine"
[ "$(id -u)" -ne 0 ] || die "run it as your normal user, not as root"
. /etc/os-release
[ "${VARIANT_ID:-}" = kinoite ] || die "this is not Fedora Kinoite (found: ${PRETTY_NAME:-unknown})"
command -v rpm-ostree >/dev/null || die "rpm-ostree is missing"
model=$(cat /sys/class/dmi/id/product_name 2>/dev/null || true)
[ "$model" = "Surface Go" ] || printf 'warning: this is "%s", not a Surface Go (1824). The fixes are made for the Surface Go only.\n' "$model"
if mokutil --sb-state 2>/dev/null | grep -qi 'SecureBoot enabled'; then secure=1; else secure=0; fi
enroll=0
echo "Fedora $rel, Secure Boot $([ $secure = 1 ] && echo on || echo off)"

if [ "$secure" = 1 ]; then
    say "Registering the signing certificate (you will confirm it at the next boot)"
    cert=$(mktemp --suffix=.der)
    trap 'rm -f "$cert"' EXIT
    curl -fsSL "$RAW/ci/mok.der" -o "$cert"
    if mokutil --test-key "$cert" 2>/dev/null | grep -qi 'already enrolled'; then
        echo "The certificate is already enrolled: nothing to do here."
    else
        echo "Choose a one-time password of at least 8 characters. You will type it once, on the blue screen at the next boot."
        sudo mokutil --import "$cert" < /dev/tty
        enroll=1   # stdin is the script when piped from curl
    fi
fi

say "Switching to the image (this downloads about 3 GB the first time)"
sudo rpm-ostree rebase "$image"

say "Done. Restart the tablet to finish."
if [ "$enroll" = 1 ]; then
    cat <<'MSG'
At the restart a blue screen "Perform MOK management" appears:
  Enroll MOK  ->  Continue  ->  Yes  ->  type the one-time password  ->  Reboot
MSG
fi
echo "Restart now with:  systemctl reboot"
