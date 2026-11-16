#!/usr/bin/env bash
# Rebuild Fedora's plasma-keyboard (Plasma's on-screen keyboard) with the image's additions: a row of extra keys, the
# clipboard, emoji, the gestures of the space bar, a floating and a split keyboard
# (patches/plasma-keyboard/0001-overdrive-keyboard.patch).
#
# usage: build_keyboard.sh <NVR as installed in the base image, e.g. 6.8.3-1.fc45> <output directory>
#
# Its QML is compiled into the program, so the change is made in the source tree: the SRPM of exactly that version is
# fetched from Koji and prepared with Fedora's own patches, ours is tried on it and becomes one more patch of the spec,
# and rpmbuild produces the packages with a ".overdriveN" release. When the patch does not apply (another version of
# the keyboard), nothing is built (the output directory stays empty) and the image keeps Fedora's keyboard, which
# lacks the additions and nothing else.
set -euo pipefail

nvr=${1:?usage: build_keyboard.sh <version-release> <out dir>}
out=${2:?}
here=$(cd "$(dirname "$0")" && pwd)
patch_file=$here/../patches/plasma-keyboard/0001-overdrive-keyboard.patch
ver=${nvr%%-*}
rel=${nvr#*-}
top=/build-kb
rm -rf "$top"
mkdir -p "$top"/{SOURCES,SPECS,BUILD,RPMS,SRPMS} "$out"

curl -fsSL --retry 4 -o /tmp/kb.src.rpm "https://kojipkgs.fedoraproject.org/packages/plasma-keyboard/$ver/$rel/src/plasma-keyboard-$ver-$rel.src.rpm"
rpm --define "_topdir $top" -i /tmp/kb.src.rpm
spec=$top/SPECS/plasma-keyboard.spec
dnf -y builddep "$spec"

rpmbuild --define "_topdir $top" -bp "$spec" >/dev/null
main=$(find "$top/BUILD" -path '*/src/qml/main.qml' | head -1)
[ -n "$main" ] || { echo "warning: src/qml/main.qml not found in plasma-keyboard $nvr, keeping Fedora's package"; exit 0; }
src=${main%/src/qml/main.qml}
if ! (cd "$src" && patch -p1 --dry-run --force < "$patch_file" >/tmp/kb-patch.log 2>&1); then
    tail -20 /tmp/kb-patch.log
    echo "warning: the keyboard patch does not apply to plasma-keyboard $nvr (Fedora's keyboard is used, without the additions)"
    exit 0
fi
cp "$patch_file" "$top/SOURCES/overdrive-keyboard.patch"

python3 - "$spec" <<'PY'
import re, sys
spec = sys.argv[1]
s = open(spec).read()
s, n = re.subn(r"^(Release:\s*\S+?)(%\{\?dist\})", r"\1\2.overdrive1", s, count=1, flags=re.M)
assert n == 1, "could not find the Release line"
last = list(re.finditer(r"^Patch\d+:.*\n", s, flags=re.M))
if last:
    s = s[:last[-1].end()] + "Patch9000: overdrive-keyboard.patch\n" + s[last[-1].end():]
else:                                   # no patches yet: after the sources
    src = list(re.finditer(r"^Source\d*:.*\n", s, flags=re.M))
    assert src, "no Source lines in the spec"
    s = s[:src[-1].end()] + "Patch9000: overdrive-keyboard.patch\n" + s[src[-1].end():]
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
cp "$top"/RPMS/*/*plasma-keyboard-[0-9]*.rpm "$out"/
ls -la "$out"
