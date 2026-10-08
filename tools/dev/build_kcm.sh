#!/bin/bash
# Compile the System Settings pages alone, in the container that has the KDE headers of the base image (tag it once as
# localhost/so-kcm-dev from the "kcm" stage of the Containerfile). The plugins land in build/kcm-dev/bin. Development tool.
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p build/kcm-dev
podman run --rm -v "$PWD/kcm:/src/kcm:ro,z" -v "$PWD/build/kcm-dev:/build:z" localhost/so-kcm-dev sh -c \
    'cmake -Wno-dev -S /src/kcm -B /build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr -DKDE_INSTALL_USE_QT_SYS_PATHS=ON >/build/configure.log 2>&1 \
     && cmake --build /build 2>&1 | grep -E "error|FAILED|warning: " | grep -v "^/usr/sbin/c++" ; ls /build/bin/plasma/kcms/systemsettings/'
