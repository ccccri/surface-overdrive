#!/usr/bin/env bash
# The development loop of the on-screen keyboard: Plasma's own keyboard (plasma-keyboard) plus our additions, which live
# in the repository as ONE patch, patches/plasma-keyboard/0001-overdrive-keyboard.patch (ci/build_keyboard.sh applies it
# to Fedora's source package when the image is built).
#
# The working tree is a git checkout of KDE's tag, outside the repository ($PK_DIR/src), with our changes staged; the build
# runs in a Fedora container, so the PC needs nothing but podman and git. Typical session:
#
#     tools/dev/keyboard-dev.sh setup            # once: checkout + patch applied + container with the build dependencies
#     $EDITOR ~/Claude/so-build/pk/src/src/qml/main.qml
#     tools/dev/keyboard-dev.sh build            # compiles and stages the result in $PK_DIR/out
#     SURFACE_PW=... tools/dev/keyboard-dev.sh deploy   # to the tablet's test overlay, restarts the keyboard there
#     tools/dev/keyboard-dev.sh export           # writes the checkout's changes back to the patch in the repository
#     git add patches/plasma-keyboard && git commit ...
#
# commands: setup | build | export | deploy | restart-remote | shell | clean
#
# environment (all optional): PK_DIR (default ~/Claude/so-build/pk), PK_TAG (the KDE tag the patch is made against, default
# v6.8.3: change it together with the patch when Fedora ships a newer plasma-keyboard), PK_CONTAINER (default pkdev),
# PK_IMAGE (default fedora:45), SURFACE_HOST (ssh alias of the tablet, default surface).
# SURFACE_PW: the owner's temporary administrator password for the tablet, given in chat; it is only ever passed on, never
# stored anywhere.
#
# Testing the result: the tablet's keyboard is started by KWin only when KWin is told that its setting changed, so
# `restart-remote` does exactly that (see team/KNOWLEDGE.md, "KWin and the keyboard"). Deployments are written to the
# tablet's /usr through `ostree admin unlock`, which is lost at the next reboot, by design.
set -euo pipefail

here=$(cd "$(dirname "$0")/../.." && pwd)
PK_DIR=${PK_DIR:-$HOME/Claude/so-build/pk}
PK_TAG=${PK_TAG:-v6.8.3}
PK_CONTAINER=${PK_CONTAINER:-pkdev}
PK_IMAGE=${PK_IMAGE:-registry.fedoraproject.org/fedora:45}
HOST=${SURFACE_HOST:-surface}
PATCH=$here/patches/plasma-keyboard/0001-overdrive-keyboard.patch
SRC=$PK_DIR/src

have_container() { podman container exists "$PK_CONTAINER"; }

in_container() { podman exec "$PK_CONTAINER" bash -c "$1"; }

root_on_tablet() {          # a command as root on the tablet; the password comes from the environment, never from a file
    : "${SURFACE_PW:?set SURFACE_PW (the owner gives the temporary password in chat)}"
    printf '%s\n' "$SURFACE_PW" | ssh "$HOST" "sudo -S -p '' bash -c $(printf '%q' "$1")"
}

cmd_setup() {
    mkdir -p "$PK_DIR"
    if [ ! -d "$SRC/.git" ]; then
        git clone --depth 1 -b "$PK_TAG" https://invent.kde.org/plasma/plasma-keyboard.git "$SRC"
    fi
    if git -C "$SRC" diff --quiet "$PK_TAG" && git -C "$SRC" diff --cached --quiet "$PK_TAG"; then
        # untouched checkout: our patch goes on, staged (the patch also adds files)
        git -C "$SRC" apply --index "$PATCH"
        echo "patch applied to the checkout"
    else
        echo "the checkout already has changes: left as it is"
    fi
    if ! have_container; then
        podman run -d --name "$PK_CONTAINER" -v "$PK_DIR":/work:Z "$PK_IMAGE" sleep infinity >/dev/null
        in_container 'dnf -y install --setopt=install_weak_deps=False dnf-plugins-core cmake ninja-build gcc-c++ git extra-cmake-modules patch >/dev/null && dnf -y builddep plasma-keyboard >/dev/null && echo "build dependencies installed"'
    else
        podman start "$PK_CONTAINER" >/dev/null
    fi
}

cmd_build() {
    have_container && podman start "$PK_CONTAINER" >/dev/null || { echo "no container: run setup first" >&2; exit 1; }
    in_container 'cd /work && { [ -f build/build.ninja ] || cmake -S src -B build -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_INSTALL_PREFIX=/usr -DKDE_INSTALL_USE_QT_SYS_PATHS=ON -DBUILD_TESTING=OFF >/dev/null; } && cmake --build build 2>&1 | grep -E "error|FAILED|warning: unused" -A4 | head -40; test "${PIPESTATUS[0]}" = 0 && rm -rf out && DESTDIR=/work/out cmake --install build >/dev/null && ls out/usr/bin'
}

cmd_export() {
    git -C "$SRC" add -A
    git -C "$SRC" diff --cached "$PK_TAG" > "$PATCH"
    echo "wrote $PATCH ($(wc -l < "$PATCH") lines): commit it, and run tests/test_keyboard_patch.py"
}

cmd_restart_remote() {      # KWin starts the keyboard again only when told that the setting changed
    ssh "$HOST" 'bash -s' <<'EOF'
. /var/tmp/overdrive-env.sh
kwriteconfig6 --notify --file kwinrc --group Wayland --key InputMethod ""; sleep 1.5
kwriteconfig6 --notify --file kwinrc --group Wayland --key InputMethod /usr/share/applications/org.kde.plasma.keyboard.desktop; sleep 2.5
sed -i '/^InputMethod/d' ~/.config/kwinrc          # the same value is the system default: nothing of ours stays in the file
pgrep -a -x plasma-keyboard
EOF
}

cmd_deploy() {
    [ -d "$PK_DIR/out/usr" ] || { echo "nothing built: run build first" >&2; exit 1; }
    tar cf "$PK_DIR/pk.tar" -C "$PK_DIR/out" --exclude=usr/share/locale usr
    scp -q "$PK_DIR/pk.tar" "$HOST":/var/tmp/pk.tar
    scp -q "$here/tools/dev/tablet-env.sh" "$HOST":/var/tmp/overdrive-env.sh
    # unlock /usr (a no-op error when already unlocked), then install every file next to its place and move it over it:
    # a file in use is never overwritten in place
    root_on_tablet 'ostree admin unlock >/dev/null 2>&1; cd /var/tmp && rm -rf pkdep && mkdir pkdep && tar xf pk.tar -C pkdep && cd pkdep && find usr -type f | while read -r f; do install -D -m "$(stat -c %a "$f")" "$f" "/$f.new" && mv -f "/$f.new" "/$f"; done'
    cmd_restart_remote
}

cmd_shell() { podman exec -it "$PK_CONTAINER" bash; }

cmd_clean() { podman rm -f "$PK_CONTAINER" >/dev/null 2>&1 || true; rm -rf "$PK_DIR/build" "$PK_DIR/out"; echo "container, build and out removed (the checkout stays)"; }

case "${1:-}" in
    setup) cmd_setup ;;
    build) cmd_build ;;
    export) cmd_export ;;
    deploy) cmd_deploy ;;
    restart-remote) cmd_restart_remote ;;
    shell) cmd_shell ;;
    clean) cmd_clean ;;
    *) sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
