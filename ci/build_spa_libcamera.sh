#!/usr/bin/env bash
# Rebuild PipeWire's libcamera plugin (libspa-libcamera.so) of the exact PipeWire in the base image, with our patches.
#
# usage: build_spa_libcamera.sh <PipeWire version-release, e.g. 1.6.9-1.fc44> <patch dir> <dir of our libcamera RPMs> <out dir>
#
# Only the plugin is built (the rest of PipeWire is untouched): Fedora's SRPM is unpacked with its own patches applied, ours
# go on top, and meson builds that one target against our libcamera. The plugin lands in <out dir> at its place in /usr.
set -euo pipefail

nvr=${1:?usage: build_spa_libcamera.sh <version-release> <patch dir> <libcamera rpms> <out dir>}
patches=${2:?}
rpms=${3:?}
out=${4:?}
ver=${nvr%%-*}
rel=${nvr#*-}
top=/build-pw
rm -rf "$top"
mkdir -p "$top"/{SOURCES,SPECS,BUILD,RPMS,SRPMS} "$out"

dnf -y install --setopt=install_weak_deps=False meson ninja-build gcc gcc-c++ pkgconf-pkg-config rpm-build curl patch
dnf -y install --setopt=install_weak_deps=False "$rpms"/libcamera-[0-9]*.rpm "$rpms"/libcamera-devel-[0-9]*.rpm

curl -fsSL -o /tmp/pipewire.src.rpm "https://kojipkgs.fedoraproject.org/packages/pipewire/$ver/$rel/src/pipewire-$ver-$rel.src.rpm"
rpm --define "_topdir $top" -i /tmp/pipewire.src.rpm
dnf -y install --setopt=install_weak_deps=False dnf-plugins-core
# the build dependencies of Fedora's package: meson checks for some of them even when the feature they serve is off
dnf -y builddep "$top/SPECS/pipewire.spec" >/dev/null
rpmbuild --define "_topdir $top" --nodeps -bp "$top/SPECS/pipewire.spec" >/dev/null
src=$(ls -d "$top"/BUILD/pipewire-*/ 2>/dev/null | head -1)
[ -f "$src/meson.build" ] || src=$(dirname "$(ls "$top"/BUILD/*/pipewire-*/meson.build | head -1)")
for p in $(ls "$patches"/*.patch | sort); do
    patch -d "$src" -p1 < "$p"
done

meson setup "$top/out" "$src" -Dauto_features=disabled -Dspa-plugins=enabled -Dlibcamera=enabled \
    -Dsession-managers=[] -Dexamples=disabled -Dtests=disabled -Dman=disabled -Ddocs=disabled
ninja -C "$top/out" spa/plugins/libcamera/libspa-libcamera.so
install -D -m 755 "$top/out/spa/plugins/libcamera/libspa-libcamera.so" "$out/usr/lib64/spa-0.2/libcamera/libspa-libcamera.so"
strip --strip-unneeded "$out/usr/lib64/spa-0.2/libcamera/libspa-libcamera.so"
ls -la "$out/usr/lib64/spa-0.2/libcamera/"
