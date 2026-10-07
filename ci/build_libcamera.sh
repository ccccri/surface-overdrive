#!/usr/bin/env bash
# Rebuild Fedora's libcamera package with our patch series applied.
#
# usage: build_libcamera.sh <NVR as installed in the base image, e.g. 0.7.1-1.fc44> <patch directory> <output directory>
#
# The SRPM of exactly that version is fetched from Koji, the patches in <patch directory> are added to the spec in file name order
# (the spec uses %autosetup, so every PatchN line is applied), the release gets a ".overdriveN" suffix so that the rebuilt package
# is newer than Fedora's, and rpmbuild produces the binary packages.
set -euo pipefail

nvr=${1:?usage: build_libcamera.sh <version-release> <patch dir> <out dir>}
patches=${2:?}
out=${3:?}
ver=${nvr%%-*}
rel=${nvr#*-}
top=/build
rm -rf "$top"
mkdir -p "$top"/{SOURCES,SPECS,BUILD,RPMS,SRPMS} "$out"

curl -fsSL -o /tmp/libcamera.src.rpm "https://kojipkgs.fedoraproject.org/packages/libcamera/$ver/$rel/src/libcamera-$ver-$rel.src.rpm"
rpm --define "_topdir $top" -i /tmp/libcamera.src.rpm
spec=$top/SPECS/libcamera.spec

i=1000
add_lines=""
for p in $(ls "$patches"/*.patch | sort); do
    cp "$p" "$top/SOURCES/"
    add_lines+="Patch$i: $(basename "$p")"$'\n'
    i=$((i + 1))
done
[ -n "$add_lines" ] || { echo "no patches found in $patches" >&2; exit 1; }

# add our patches after Fedora's own, mark the release, and skip the unit tests (they are not packaged)
python3 - "$spec" "$add_lines" <<'EOF'
import re, sys
spec, add = sys.argv[1], sys.argv[2]
s = open(spec).read()
s, n = re.subn(r"^(Patch0*1:.*\n)", lambda m: m.group(1) + add, s, count=1, flags=re.M)
assert n == 1, "could not find Fedora's Patch line in the spec"
s, n = re.subn(r"^(Release:\s*\S+?)(%\{\?dist\})", r"\1\2.overdrive1", s, count=1, flags=re.M)
assert n == 1, "could not find the Release line"
s = s.replace("-Dtest=true", "-Dtest=false")
open(spec, "w").write(s)
EOF

dnf -y builddep "$spec"
# Not declared in Fedora's spec but needed by meson here (libcamera's backtrace support looks for libdw); Koji's buildroot happens to have it.
dnf -y install --setopt=install_weak_deps=False elfutils-devel
rpmbuild --define "_topdir $top" -bb "$spec"
cp "$top"/RPMS/*/*.rpm "$out"/
ls -la "$out"
