#!/bin/bash
# Drive System Settings on the Surface from this desktop, to test the pages without a person at the tablet. Development tool.
#
# usage: SURFACE_PW=<password> tools/dev/ui.sh <command> ...
#   build                      compile the pages (tools/dev/build_kcm.sh) and copy them to ~/so-test on the tablet
#   open "<page id and args>"  restart System Settings on a page, with the pages from ~/so-test
#   shot <file.png>            screenshot of the tablet into a local file
#   mouse "<cmd>;<cmd>..."     commands for uinput_mouse.py (click X Y, drag X1 Y1 X2 Y2, wait S), screen pixels 1800x1200
#   touch "<cmd>;<cmd>..."     commands for uinput_touch.py (tap, hold, swipe, wait)
#   type "<text>" [--enter]    type with uinput_type.py
#   log [lines]                QML warnings and errors since the last open
#   cores                      crash records of System Settings since the last open
set -euo pipefail
cd "$(dirname "$0")/../.."
H=${SURFACE_HOST:-cri@192.168.0.96}
E='export WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus;'
pw() { : "${SURFACE_PW:?set SURFACE_PW to the password of the account on the Surface}"; }
tools() { ssh "$H" 'test -f /tmp/uinput_mouse.py' || scp -q tools/dev/uinput_*.py "$H:/tmp/"; }
input() { pw; tools; ssh "$H" "$E (echo '$SURFACE_PW'; echo '$2' | tr ';' '\n'; echo 'wait ${3:-1}') | sudo -k -S -p '' python3 /tmp/uinput_$1.py 1800 1200 >/dev/null; pgrep -x systemsettings >/dev/null || echo 'System Settings is NOT RUNNING'"; }
case ${1:-} in
build) tools/dev/build_kcm.sh | grep -v '^kcm_.*\.so$' || true
       ssh "$H" 'mkdir -p ~/so-test/plasma/kcms/systemsettings'
       rsync -a build/kcm-dev/bin/plasma/kcms/systemsettings/ "$H:so-test/plasma/kcms/systemsettings/" ;;
open)  ssh "$H" "$E loginctl unlock-session \$(loginctl list-sessions --no-legend | awk '/seat0/{print \$1; exit}'); pkill -x systemsettings; sleep 0.7; date +%s > /tmp/ui.start; systemd-run --user --quiet --collect --unit=ovd-ui-\$RANDOM -E QT_PLUGIN_PATH=\$HOME/so-test systemsettings $2; sleep ${3:-7}; pgrep -x systemsettings >/dev/null || echo 'System Settings is NOT RUNNING'" ;;
shot)  ssh "$H" "$E spectacle -b -n -f -o /tmp/ui-shot.png 2>/dev/null"; scp -q "$H:/tmp/ui-shot.png" "$2" ;;
mouse|touch) input "$1" "$2" "${3:-1}" ;;
type)  pw; tools; ssh "$H" "$E (echo '$SURFACE_PW'; echo '$2') | sudo -k -S -p '' python3 /tmp/uinput_type.py ${3:-} >/dev/null 2>&1" ;;
log)   ssh "$H" "$E journalctl --user --since @\$(cat /tmp/ui.start) --no-pager -o cat | grep -a -E 'qml|TypeError|ReferenceError|Surface Control|Binding loop' | cut -c1-240 | sort | uniq -c | sort -rn | head -${2:-12}" || true ;;
cores) ssh "$H" "coredumpctl list --since @\$(cat /tmp/ui.start) --no-pager 2>/dev/null | grep systemsettings || echo 'no crash records'" ;;
*) sed -n '2,14p' "$0"; exit 2 ;;
esac
