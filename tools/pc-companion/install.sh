#!/bin/bash
# install.sh: the PC side of "the Surface as a screen of the PC" (Sunshine from Bazzite: ujust setup-sunshine enable-flatpak).
# Copies the scripts to ~/.local/bin, sets portal capture and adds the "Surface Screen" app to Sunshine. Run as the user.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
for f in surface-screen-start surface-screen-stop surface-screen-restore surface-screen-map surface-screen-where surface-screen-osk \
         surface-desktop-start surface-desktop-stop; do
    install -Dm755 "$here/$f" "$HOME/.local/bin/$f"
done
dir=$HOME/.var/app/dev.lizardbyte.app.Sunshine/config/sunshine
conf=$dir/sunshine.conf apps=$dir/apps.json
[ -f "$apps" ] || { echo "Sunshine is not set up (ujust setup-sunshine enable-flatpak)" >&2; exit 1; }
# the XDG portal: KWin 6.8 never gives its own screencast to Flatpak apps, and the flatpak has no KMS capture
sed -i '/^capture *=/d' "$conf"; echo "capture = portal" >> "$conf"
env="--env=SUNSHINE_CLIENT_WIDTH=\${SUNSHINE_CLIENT_WIDTH} --env=SUNSHINE_CLIENT_HEIGHT=\${SUNSHINE_CLIENT_HEIGHT} --env=SUNSHINE_CLIENT_FPS=\${SUNSHINE_CLIENT_FPS}"
session="env WAYLAND_DISPLAY=$WAYLAND_DISPLAY XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS=$DBUS_SESSION_BUS_ADDRESS"
prep() {  # <do script> <undo script>: a prep-cmd entry running them on the host, in the session
    jq -n --arg do "sh -c \"flatpak-spawn --host $env $session $HOME/.local/bin/$1\"" \
          --arg undo "sh -c \"flatpak-spawn --host $session $HOME/.local/bin/$2\"" '{do: $do, undo: $undo}'
}
screen=$(jq -n --argjson p "$(prep surface-screen-start surface-screen-stop)" \
    '{name: "Surface Screen", cmd: "", "auto-detach": true, "wait-all": true, "exit-timeout": 5, elevated: false,
      "exclude-global-prep-cmd": false, "image-path": "", output: "", "prep-cmd": [$p]}')
desktop=$(prep surface-desktop-start surface-desktop-stop)
tmp=$(mktemp)
jq --argjson screen "$screen" --argjson d "$desktop" '
    .apps = ([(.apps // [])[] | select(.name != $screen.name)] + [$screen])
    | .apps |= map(if .name == "Desktop" then .["prep-cmd"] = [$d] else . end)' "$apps" > "$tmp" && mv "$tmp" "$apps"
# whatever a session changed comes back also when Sunshine itself stops or restarts mid-session (no "undo" runs then)
mkdir -p "$HOME/.config/systemd/user/app-dev.lizardbyte.app.Sunshine.service.d"
printf '[Service]\nExecStopPost=-%s\n' "$HOME/.local/bin/surface-screen-stop" \
    > "$HOME/.config/systemd/user/app-dev.lizardbyte.app.Sunshine.service.d/50-surface-screen.conf"
systemctl --user daemon-reload
systemctl --user restart app-dev.lizardbyte.app.Sunshine
echo "Surface Screen ready in Sunshine"
