#!/usr/bin/env bash
# The administrator part of the Surface Overdrive install, run once through pkexec (one password window) or sudo by
# installer/install.py. It talks to the installer over stdout, one line per event:
#   MOK enrolled | MOK need | MOK queued | MOK failed <why> | MOK off      the module signing certificate
#   LOG <text>                                                             rpm-ostree's own output, as it comes
#   DONE | FAIL <why>                                                      the end
# When the certificate is not enrolled yet it prints "MOK need" and reads the one-time password, one line, on stdin.
#
# usage: root-step.sh <certificate.der> <image reference>
set -uo pipefail
cert=${1:?usage: root-step.sh <cert> <image>}
image=${2:?}
[ "$(id -u)" = 0 ] || { echo "FAIL not run as the administrator"; exit 1; }

if mokutil --sb-state 2>/dev/null | grep -qi 'SecureBoot enabled'; then
    # as the administrator: MokListRT is readable by root only (as a user the test failed and the key was asked again)
    test=$(mokutil --test-key "$cert" 2>&1)
    if grep -qi 'already enrolled' <<<"$test"; then
        echo "MOK enrolled"
    elif grep -qi 'already in the enrollment request' <<<"$test"; then
        echo "MOK queued"
    else
        echo "MOK need"
        IFS= read -r pw || pw=""
        if [ "${#pw}" -lt 8 ]; then
            echo "MOK failed no password of at least 8 characters"
        elif out=$(printf '%s\n%s\n' "$pw" "$pw" | mokutil --import "$cert" 2>&1) &&
             mokutil --test-key "$cert" 2>&1 | grep -qi -E 'already in the enrollment request|already enrolled'; then
            echo "MOK queued"
        else
            echo "MOK failed $(tr '\n' ' ' <<<"$out" | cut -c1-200)"
        fi
        unset pw
        # without the certificate the image's kernel modules would not load: stop before switching
        mokutil --test-key "$cert" 2>&1 | grep -qi -E 'already in the enrollment request|already enrolled' ||
            { echo "FAIL the certificate could not be registered"; exit 1; }
    fi
else
    echo "MOK off"
fi

# the switch to the image; every line of rpm-ostree goes to the installer
rpm-ostree rebase "$image" 2>&1 | while IFS= read -r line; do printf 'LOG %s\n' "$line"; done
status=${PIPESTATUS[0]}
if [ "$status" = 0 ]; then echo "DONE"; else echo "FAIL rpm-ostree rebase ended with status $status"; fi
exit "$status"
