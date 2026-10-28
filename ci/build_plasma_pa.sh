#!/usr/bin/env bash
# Rebuild Fedora's plasma-pa (Plasma's sound controls) without "Raise maximum volume" (ci/patch_plasma_pa.py).
#
# usage: build_plasma_pa.sh <NVR as installed in the base image, e.g. 6.7.5-1.fc44> <output directory>
#
# Its QML is compiled into its plugins, so the change is made in the source tree: the SRPM of exactly that version is fetched from
# Koji and prepared with Fedora's own patches, ci/patch_plasma_pa.py edits it, the difference becomes one more patch of the spec,
# and rpmbuild produces the package with a ".overdriveN" release. When the sources have a layout the patch was not written for,
# nothing is built (the output directory stays empty) and the image keeps Fedora's package, switch included.
set -euo pipefail

nvr=${1:?usage: build_plasma_pa.sh <version-release> <out dir>}
out=${2:?}
here=$(cd "$(dirname "$0")" && pwd)
ver=${nvr%%-*}
rel=${nvr#*-}
top=/build-pa
rm -rf "$top"
mkdir -p "$top"/{SOURCES,SPECS,BUILD,RPMS,SRPMS} "$out"

curl -fsSL --retry 4 -o /tmp/pa.src.rpm "https://kojipkgs.fedoraproject.org/packages/plasma-pa/$ver/$rel/src/plasma-pa-$ver-$rel.src.rpm"
rpm --define "_topdir $top" -i /tmp/pa.src.rpm
spec=$top/SPECS/plasma-pa.spec
dnf -y builddep "$spec"

rpmbuild --define "_topdir $top" -bp "$spec" >/dev/null
main=$(find "$top/BUILD" -path '*/applet/main.qml' | head -1)
[ -n "$main" ] || { echo "warning: applet/main.qml not found in plasma-pa $nvr, keeping Fedora's package"; exit 0; }
src=${main%/applet/main.qml}
rm -rf /tmp/pa && mkdir -p /tmp/pa
cp -r "$src" /tmp/pa/a
cp -r "$src" /tmp/pa/b
python3 "$here/patch_plasma_pa.py" /tmp/pa/b | tee /tmp/pa/log
if ! grep -q '^patched' /tmp/pa/log; then
    echo "warning: plasma-pa keeps its \"Raise maximum volume\" (Fedora's package is used)"
    exit 0
fi
(cd /tmp/pa && diff -ruN a b) > "$top/SOURCES/overdrive-no-raised-maximum.patch" || true
test -s "$top/SOURCES/overdrive-no-raised-maximum.patch"

python3 - "$spec" <<'PY'
import re, sys
spec = sys.argv[1]
s = open(spec).read()
s, n = re.subn(r"^(Release:\s*\S+?)(%\{\?dist\})", r"\1\2.overdrive1", s, count=1, flags=re.M)
assert n == 1, "could not find the Release line"
last = list(re.finditer(r"^Patch\d+:.*\n", s, flags=re.M))
if last:
    s = s[:last[-1].end()] + "Patch9000: overdrive-no-raised-maximum.patch\n" + s[last[-1].end():]
else:                                   # no patches yet: after the sources
    src = list(re.finditer(r"^Source\d*:.*\n", s, flags=re.M))
    assert src, "no Source lines in the spec"
    s = s[:src[-1].end()] + "Patch9000: overdrive-no-raised-maximum.patch\n" + s[src[-1].end():]
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
cp "$top"/RPMS/*/plasma-pa-[0-9]*.rpm "$out"/
ls -la "$out"
