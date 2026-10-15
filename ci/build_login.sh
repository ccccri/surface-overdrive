#!/usr/bin/env bash
# Rebuild Fedora's plasma-login-manager with the PIN and pattern pad on the login screen.
#
# usage: build_login.sh <NVR as installed in the base image, e.g. 6.7.5-1.fc44> <output directory>
#
# The QML of the login screen is compiled into the greeter, so unlike the lock screen it cannot be edited in the image: the SRPM of
# exactly that version is fetched from Koji and prepared with Fedora's own patches, ci/patch_unlock_pad.py edits Login.qml of that
# tree, the difference becomes one more patch of the spec, and rpmbuild produces the packages with a ".overdriveN" release.
# When Login.qml has a layout the patch was not written for, nothing is built (the output directory stays empty) and the image
# keeps Fedora's package: the login screen then has the password field only, as before.
set -euo pipefail

nvr=${1:?usage: build_login.sh <version-release> <out dir>}
out=${2:?}
here=$(cd "$(dirname "$0")" && pwd)
ver=${nvr%%-*}
rel=${nvr#*-}
top=/build
rm -rf "$top"
mkdir -p "$top"/{SOURCES,SPECS,BUILD,RPMS,SRPMS} "$out"

curl -fsSL -o /tmp/login.src.rpm "https://kojipkgs.fedoraproject.org/packages/plasma-login-manager/$ver/$rel/src/plasma-login-manager-$ver-$rel.src.rpm"
rpm --define "_topdir $top" -i /tmp/login.src.rpm
spec=$top/SPECS/plasma-login-manager.spec
dnf -y builddep "$spec"

# Fedora's tree with Fedora's patches, to make ours against
rpmbuild --define "_topdir $top" -bp "$spec" >/dev/null
qml=$(find "$top/BUILD" -path '*/src/frontend/greeter/qml/Login.qml' | head -1)
[ -n "$qml" ] || { echo "warning: Login.qml not found in plasma-login-manager $nvr, keeping Fedora's package"; exit 0; }
rel_path=src/frontend/greeter/qml/Login.qml
rm -rf /tmp/pad && mkdir -p "/tmp/pad/a/${rel_path%/*}" "/tmp/pad/b/${rel_path%/*}"
cp "$qml" "/tmp/pad/a/$rel_path"
cp "$qml" "/tmp/pad/b/$rel_path"
python3 "$here/patch_unlock_pad.py" login "/tmp/pad/b/$rel_path" | tee /tmp/pad/log
if ! grep -q '^patched' /tmp/pad/log; then
    echo "warning: the login screen keeps the password field only (Fedora's package is used)"
    exit 0
fi
(cd /tmp/pad && diff -u "a/$rel_path" "b/$rel_path") > "$top/SOURCES/overdrive-unlock-pad.patch" || true
test -s "$top/SOURCES/overdrive-unlock-pad.patch"

python3 - "$spec" <<'EOF'
import re, sys
spec = sys.argv[1]
s = open(spec).read()
last = list(re.finditer(r"^Patch\d+:.*\n", s, flags=re.M))
assert last, "no Patch lines in the spec"
s = s[:last[-1].end()] + "Patch9000: overdrive-unlock-pad.patch\n" + s[last[-1].end():]
s, n = re.subn(r"^(Release:\s*\S+?)(%\{\?dist\})", r"\1\2.overdrive1", s, count=1, flags=re.M)
assert n == 1, "could not find the Release line"
open(spec, "w").write(s)
EOF

# half of the processors unless told otherwise (see build_kmods.py)
jobs=${OVERDRIVE_JOBS:-$(( ($(nproc) + 1) / 2 ))}
rpmbuild --define "_topdir $top" --define "_smp_build_ncpus $jobs" --nocheck -bb "$spec"
cp "$top"/RPMS/*/plasma-login-manager-[0-9]*.rpm "$out"/
ls -la "$out"
