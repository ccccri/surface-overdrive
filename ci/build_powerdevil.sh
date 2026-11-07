#!/usr/bin/env bash
# Rebuild Fedora's powerdevil with the Brightness & Color popup scrolling vertically only (ci/patch_powerdevil.py).
#
# usage: build_powerdevil.sh <NVR as installed in the base image, e.g. 6.8.2-1.fc45> <output directory>
#
# Its QML is compiled into its plugins, so the change is made in the source tree: the SRPM of exactly that version is fetched from
# Koji and prepared with Fedora's own patches, ci/patch_powerdevil.py edits it, the difference becomes one more patch of the spec,
# and rpmbuild produces the package with a ".overdriveN" release. When the sources have a layout the patch was not written for,
# nothing is built (the output directory stays empty) and the image keeps Fedora's package, switch included.
set -euo pipefail

nvr=${1:?usage: build_powerdevil.sh <version-release> <out dir>}
out=${2:?}
here=$(cd "$(dirname "$0")" && pwd)
ver=${nvr%%-*}
rel=${nvr#*-}
top=/build-pd
rm -rf "$top"
mkdir -p "$top"/{SOURCES,SPECS,BUILD,RPMS,SRPMS} "$out"

curl -fsSL --retry 4 -o /tmp/pd.src.rpm "https://kojipkgs.fedoraproject.org/packages/powerdevil/$ver/$rel/src/powerdevil-$ver-$rel.src.rpm"
rpm --define "_topdir $top" -i /tmp/pd.src.rpm
spec=$top/SPECS/powerdevil.spec
dnf -y builddep "$spec"

rpmbuild --define "_topdir $top" -bp "$spec" >/dev/null
main=$(find "$top/BUILD" -path '*/applets/brightness/PopupDialog.qml' | head -1)
[ -n "$main" ] || { echo "warning: applets/brightness/PopupDialog.qml not found in powerdevil $nvr, keeping Fedora's package"; exit 0; }
src=${main%/applets/brightness/PopupDialog.qml}
rm -rf /tmp/pd && mkdir -p /tmp/pd
cp -r "$src" /tmp/pd/a
cp -r "$src" /tmp/pd/b
python3 "$here/patch_powerdevil.py" /tmp/pd/b | tee /tmp/pd/log
if ! grep -q '^patched' /tmp/pd/log; then
    echo "warning: powerdevil keeps its sideways-scrolling brightness popup (Fedora's package is used)"
    exit 0
fi
(cd /tmp/pd && diff -ruN a b) > "$top/SOURCES/overdrive-brightness-popup-scroll.patch" || true
test -s "$top/SOURCES/overdrive-brightness-popup-scroll.patch"

python3 - "$spec" <<'PY'
import re, sys
spec = sys.argv[1]
s = open(spec).read()
s, n = re.subn(r"^(Release:\s*\S+?)(%\{\?dist\})", r"\1\2.overdrive1", s, count=1, flags=re.M)
assert n == 1, "could not find the Release line"
last = list(re.finditer(r"^Patch\d+:.*\n", s, flags=re.M))
if last:
    s = s[:last[-1].end()] + "Patch9000: overdrive-brightness-popup-scroll.patch\n" + s[last[-1].end():]
else:                                   # no patches yet: after the sources
    src = list(re.finditer(r"^Source\d*:.*\n", s, flags=re.M))
    assert src, "no Source lines in the spec"
    s = s[:src[-1].end()] + "Patch9000: overdrive-brightness-popup-scroll.patch\n" + s[src[-1].end():]
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
cp "$top"/RPMS/*/powerdevil-[0-9]*.rpm "$out"/
ls -la "$out"
