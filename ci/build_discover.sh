#!/usr/bin/env bash
# Rebuild Fedora's plasma-discover without the "Update Issue" for its own repeated firmware metadata download
# (ci/patch_discover.py).
#
# usage: build_discover.sh <NVR as installed in the base image, e.g. 6.8.2-1.fc45> <output directory>
#
# The fwupd backend is a C++ plugin, so the change is made in the source tree: the SRPM of exactly that version is fetched
# from Koji and prepared with Fedora's own patches, ci/patch_discover.py edits it, the difference becomes one more patch of
# the spec, and rpmbuild produces the packages with a ".overdriveN" release. When the sources have a layout the patch was
# not written for, nothing is built (the output directory stays empty) and the image keeps Fedora's package.
set -euo pipefail

nvr=${1:?usage: build_discover.sh <version-release> <out dir>}
out=${2:?}
here=$(cd "$(dirname "$0")" && pwd)
ver=${nvr%%-*}
rel=${nvr#*-}
top=/build-discover
rm -rf "$top"
mkdir -p "$top"/{SOURCES,SPECS,BUILD,RPMS,SRPMS} "$out"

curl -fsSL --retry 4 -o /tmp/discover.src.rpm "https://kojipkgs.fedoraproject.org/packages/plasma-discover/$ver/$rel/src/plasma-discover-$ver-$rel.src.rpm"
rpm --define "_topdir $top" -i /tmp/discover.src.rpm
spec=$top/SPECS/plasma-discover.spec
dnf -y builddep "$spec"

rpmbuild --define "_topdir $top" -bp "$spec" >/dev/null
main=$(find "$top/BUILD" -path '*/libdiscover/backends/FwupdBackend/FwupdBackend.cpp' | head -1)
[ -n "$main" ] || { echo "warning: FwupdBackend.cpp not found in plasma-discover $nvr, keeping Fedora's package"; exit 0; }
src=${main%/libdiscover/backends/FwupdBackend/FwupdBackend.cpp}
rm -rf /tmp/dc && mkdir -p /tmp/dc/a/libdiscover/backends /tmp/dc/b/libdiscover/backends
cp -r "$src/libdiscover/backends/FwupdBackend" /tmp/dc/a/libdiscover/backends/
cp -r "$src/libdiscover/backends/FwupdBackend" /tmp/dc/b/libdiscover/backends/
python3 "$here/patch_discover.py" /tmp/dc/b | tee /tmp/dc/log
if ! grep -q '^patched' /tmp/dc/log; then
    echo "warning: Discover keeps its Update Issue for fwupd's repeated download (Fedora's package is used)"
    exit 0
fi
(cd /tmp/dc && diff -ruN a b) > "$top/SOURCES/overdrive-fwupd-repeated-download.patch" || true
test -s "$top/SOURCES/overdrive-fwupd-repeated-download.patch"

python3 - "$spec" <<'PY'
import re, sys
spec = sys.argv[1]
s = open(spec).read()
s, n = re.subn(r"^(Release:\s*\S+?)(%\{\?dist\})", r"\1\2.overdrive1", s, count=1, flags=re.M)
assert n == 1, "could not find the Release line"
last = list(re.finditer(r"^Patch\d+:.*\n", s, flags=re.M))
if last:
    s = s[:last[-1].end()] + "Patch9000: overdrive-fwupd-repeated-download.patch\n" + s[last[-1].end():]
else:                                   # no patches yet: after the sources
    src = list(re.finditer(r"^Source\d*:.*\n", s, flags=re.M))
    assert src, "no Source lines in the spec"
    s = s[:src[-1].end()] + "Patch9000: overdrive-fwupd-repeated-download.patch\n" + s[src[-1].end():]
# applied by %autosetup, with -p1 (the paths of the patch start with a/ and b/); a plain %setup gets it applied after it
if re.search(r"^%autosetup", s, flags=re.M):
    if not re.search(r"^%autosetup.*-p\d", s, flags=re.M):
        s = re.sub(r"^(%autosetup.*)$", r"\1 -p1", s, count=1, flags=re.M)
    else:
        assert re.search(r"^%autosetup.*-p1", s, flags=re.M), "%autosetup with another patch level"
else:
    s, n = re.subn(r"^(%setup.*\n)", r"\1%patch -P9000 -p1\n", s, count=1, flags=re.M)
    assert n == 1, "no %autosetup nor %setup in the spec"
open(spec, "w").write(s)
PY

jobs=${OVERDRIVE_JOBS:-$(( ($(nproc) + 1) / 2 ))}
rpmbuild --define "_topdir $top" --define "_smp_build_ncpus $jobs" --nocheck -bb "$spec"
# every subpackage but the debug ones: they require one another at exactly this version-release
find "$top/RPMS" -name 'plasma-discover*.rpm' ! -name '*-debuginfo-*' ! -name '*-debugsource-*' -exec cp {} "$out"/ \;
ls -la "$out"
