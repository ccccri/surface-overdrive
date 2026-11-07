#!/bin/bash
# install.sh: the PC side of "the Surface as a screen of the PC" (Sunshine from Bazzite: ujust setup-sunshine enable-flatpak).
# Copies the scripts to ~/.local/bin, sets portal capture and adds the "Surface Screen" app to Sunshine. Run as the user.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
install -Dm755 "$here/surface-screen-start" "$HOME/.local/bin/surface-screen-start"
install -Dm755 "$here/surface-screen-stop" "$HOME/.local/bin/surface-screen-stop"
dir=$HOME/.var/app/dev.lizardbyte.app.Sunshine/config/sunshine
conf=$dir/sunshine.conf apps=$dir/apps.json
[ -f "$apps" ] || { echo "Sunshine is not set up (ujust setup-sunshine enable-flatpak)" >&2; exit 1; }
# the XDG portal: KWin 6.8 never gives its own screencast to Flatpak apps, and the flatpak has no KMS capture
sed -i '/^capture *=/d' "$conf"; echo "capture = portal" >> "$conf"
env="--env=SUNSHINE_CLIENT_WIDTH=\${SUNSHINE_CLIENT_WIDTH} --env=SUNSHINE_CLIENT_HEIGHT=\${SUNSHINE_CLIENT_HEIGHT} --env=SUNSHINE_CLIENT_FPS=\${SUNSHINE_CLIENT_FPS}"
host="flatpak-spawn --host env WAYLAND_DISPLAY=$WAYLAND_DISPLAY XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS=$DBUS_SESSION_BUS_ADDRESS"
app=$(jq -n --arg do "sh -c \"flatpak-spawn --host $env env WAYLAND_DISPLAY=$WAYLAND_DISPLAY XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS=$DBUS_SESSION_BUS_ADDRESS $HOME/.local/bin/surface-screen-start\"" \
             --arg undo "sh -c \"$host $HOME/.local/bin/surface-screen-stop\"" \
    '{name: "Surface Screen", cmd: "", "auto-detach": true, "wait-all": true, "exit-timeout": 5, elevated: false,
      "exclude-global-prep-cmd": false, "image-path": "", output: "", "prep-cmd": [{do: $do, undo: $undo}]}')
tmp=$(mktemp)
jq --argjson app "$app" '.apps = ([(.apps // [])[] | select(.name != $app.name)] + [$app])' "$apps" > "$tmp" && mv "$tmp" "$apps"
systemctl --user restart app-dev.lizardbyte.app.Sunshine
echo "Surface Screen ready in Sunshine"
