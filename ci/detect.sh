#!/usr/bin/env bash
# Print the build arguments for one Fedora release: the base image, its digest and the exact kernel it carries.
# The registry now and then answers 503 for a few minutes: try again a few times before giving up.
# usage: ci/detect.sh 44
set -euo pipefail
rel=${1:?usage: detect.sh <fedora release>}
base=quay.io/fedora-ostree-desktops/kinoite:$rel
for attempt in 1 2 3 4 5; do
  if info=$(skopeo inspect --no-tags --retry-times 3 --override-os linux "docker://$base"); then
    break
  fi
  [ "$attempt" = 5 ] && { echo "the registry did not answer for $base" >&2; exit 1; }
  echo "registry not answering (attempt $attempt), again in $((attempt * 60)) s" >&2
  sleep $((attempt * 60))
done
python3 -c 'import json,sys; i=json.load(sys.stdin); print("BASE=%s\nDIGEST=%s\nKVER=%s" % (sys.argv[1], i["Digest"], i["Labels"]["ostree.linux"]))' \
  "$base" <<<"$info"
