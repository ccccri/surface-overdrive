#!/usr/bin/env bash
# Build the image locally with a throwaway signing key (the real key only exists in CI secrets).
# usage: ci/local-build.sh [fedora release, default 44]
set -euo pipefail
cd "$(dirname "$0")/.."
rel=${1:-44}
eval "$(ci/detect.sh "$rel")"
keydir=build/dev-key
if [ ! -f "$keydir/key.pem" ]; then
    mkdir -p "$keydir"
    openssl req -new -x509 -newkey rsa:2048 -keyout "$keydir/key.pem" -outform DER -out "$keydir/cert.der" -days 3650 -nodes \
        -subj "/CN=Surface Overdrive development key/" \
        -addext "keyUsage=digitalSignature" -addext "extendedKeyUsage=codeSigning" -addext "basicConstraints=critical,CA:FALSE"
    chmod 600 "$keydir/key.pem"
fi
podman build --build-arg "BASE=$BASE" --build-arg "KVER=$KVER" \
    --secret "id=modkey,src=$keydir/key.pem" --secret "id=modcert,src=$keydir/cert.der" \
    -t "localhost/surface-overdrive:$rel" .
