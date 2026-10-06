#!/usr/bin/env bash
# Print the build arguments for one Fedora release: the base image and the exact kernel it carries.
# usage: ci/detect.sh 44
set -euo pipefail
rel=${1:?usage: detect.sh <fedora release>}
base=quay.io/fedora-ostree-desktops/kinoite:$rel
kver=$(skopeo inspect --override-os linux "docker://$base" | python3 -c 'import json,sys; print(json.load(sys.stdin)["Labels"]["ostree.linux"])')
printf 'BASE=%s\nKVER=%s\n' "$base" "$kver"
