# Source this in an ssh shell on the tablet, to act inside the owner's graphical session (a plain ssh shell has none):
#
#     . tablet-env.sh
#     shot name          # a screenshot of the whole screen: /var/tmp/vis/name.png (spectacle)
#     systemd-run --user --collect --unit myapp some-gui-app     # start a GUI app so that polkit, portals and the
#                                                                # session bus see it as part of the session
#
# Why: GUI tools started from ssh miss the session's environment, and an app started straight from the ssh shell is
# not in the graphical session (a polkit dialog never shows, portals refuse). The user systemd manager knows the
# session's environment, so it is copied from there. Needs the owner to be logged in on the tablet.

for _v in WAYLAND_DISPLAY DISPLAY XAUTHORITY XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS XDG_CURRENT_DESKTOP \
          XDG_SESSION_TYPE KDE_FULL_SESSION KDE_SESSION_VERSION XDG_SESSION_ID XDG_SEAT; do
    _line=$(systemctl --user show-environment 2>/dev/null | grep "^${_v}=" | head -1)
    [ -n "$_line" ] && export "$_v=${_line#*=}"
done
unset _v _line
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}

shot() {
    mkdir -p /var/tmp/vis
    spectacle -b -n -f -o "/var/tmp/vis/$1.png" >/dev/null 2>&1
}
