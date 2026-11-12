#!/usr/bin/env bash
# Rebuild Plasma's task manager applet (org.kde.plasma.taskmanager.so) of the exact plasma-desktop in the base image, with
# "Force Quit" in its context menu (ci/patch_taskmanager.py).
#
# usage: build_taskmanager.sh <plasma-desktop version-release, e.g. 6.8.2-1.fc45> <out dir>
#
# The applet's QML is compiled into it, so the change is made in the source tree: Fedora's SRPM of exactly that version is
# prepared with Fedora's own patches, ours goes on top, and only the applet's target is built. It lands in <out dir> at its
# place in /usr. When the patch does not fit, nothing is built (the out dir stays empty) and the image keeps Fedora's applet.
set -euo pipefail

nvr=${1:?usage: build_taskmanager.sh <version-release> <out dir>}
out=${2:?}
here=$(cd "$(dirname "$0")" && pwd)
ver=${nvr%%-*}
rel=${nvr#*-}
top=/build-tm
rm -rf "$top"
mkdir -p "$top"/{SOURCES,SPECS,BUILD,RPMS,SRPMS} "$out"

dnf -y install --setopt=install_weak_deps=False rpm-build dnf-plugins-core curl python3 cmake ninja-build >/dev/null
curl -fsSL --retry 4 -o /tmp/pdesk.src.rpm "https://kojipkgs.fedoraproject.org/packages/plasma-desktop/$ver/$rel/src/plasma-desktop-$ver-$rel.src.rpm"
rpm --define "_topdir $top" -i /tmp/pdesk.src.rpm
spec=$top/SPECS/plasma-desktop.spec
dnf -y builddep "$spec" >/dev/null
rpmbuild --define "_topdir $top" --nodeps -bp "$spec" >/dev/null
menu=$(find "$top/BUILD" -path '*/applets/taskmanager/qml/ContextMenu.qml' | head -1)
[ -n "$menu" ] || { echo "warning: the task manager's ContextMenu.qml not found in plasma-desktop $nvr, keeping Fedora's applet"; exit 0; }
src=${menu%/applets/taskmanager/qml/ContextMenu.qml}
python3 "$here/patch_taskmanager.py" "$src" | tee /tmp/tm.log
grep -q '^patched' /tmp/tm.log || { echo "warning: no Force Quit in the task manager (Fedora's applet is used)"; exit 0; }

cmake -S "$src" -B /build-tm-cmake -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_INSTALL_PREFIX=/usr \
    -DKDE_INSTALL_USE_QT_SYS_PATHS=ON -DBUILD_TESTING=OFF >/dev/null
ninja -C /build-tm-cmake org.kde.plasma.taskmanager
so=$(find /build-tm-cmake -name 'org.kde.plasma.taskmanager.so' | head -1)
[ -n "$so" ] || { echo "error: org.kde.plasma.taskmanager.so was not produced" >&2; exit 1; }
strip --strip-debug "$so"
install -Dm755 "$so" "$out/usr/lib64/qt6/plugins/plasma/applets/org.kde.plasma.taskmanager.so"
ls -la "$out/usr/lib64/qt6/plugins/plasma/applets/"
