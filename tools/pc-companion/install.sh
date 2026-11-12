#!/bin/bash
# install.sh: the PC side of "the Surface as a screen of the PC" (Sunshine from Bazzite: ujust setup-sunshine enable-flatpak).
# Copies the scripts to ~/.local/bin, sets portal capture, adds the "Extended Display" app and the Surface's remote desktop
# to "Desktop", and clears what a session may have left behind before every stream (global prep). Run as the user.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
for f in surface-av surface-screen-start surface-screen-stop surface-screen-restore surface-screen-map surface-screen-osk surface-screen-where surface-screen-is-surface surface-screen-token surface-screen-panel \
         surface-desktop-start surface-desktop-stop sunshine-open surface-screen-tray sunshine-sinks; do
    install -Dm755 "$here/$f" "$HOME/.local/bin/$f"
done
dir=$HOME/.var/app/dev.lizardbyte.app.Sunshine/config/sunshine
conf=$dir/sunshine.conf apps=$dir/apps.json
[ -f "$apps" ] || { echo "Sunshine is not set up (ujust setup-sunshine enable-flatpak)" >&2; exit 1; }
# the XDG portal: KWin 6.8 never gives its own screencast to Flatpak apps, and the flatpak has no KMS capture
sed -i '/^capture *=/d' "$conf"; echo "capture = portal" >> "$conf"
# the Surface's screen when it is there, the first monitor otherwise (Sunshine takes the name when a stream starts)
sed -i '/^output_name *=/d' "$conf"; echo "output_name = Virtual-surface" >> "$conf"
# no NVIDIA card: VA-API straight away (the NVENC and Vulkan tests fail anyway, each after a screen-sharing session)
if [ ! -e /proc/driver/nvidia ]; then
    sed -i '/^encoder *=/d' "$conf"; echo "encoder = vaapi" >> "$conf"
fi
env="--env=SUNSHINE_CLIENT_WIDTH=\${SUNSHINE_CLIENT_WIDTH} --env=SUNSHINE_CLIENT_HEIGHT=\${SUNSHINE_CLIENT_HEIGHT} --env=SUNSHINE_CLIENT_FPS=\${SUNSHINE_CLIENT_FPS}"
session="env WAYLAND_DISPLAY=$WAYLAND_DISPLAY XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS=$DBUS_SESSION_BUS_ADDRESS"
prep() {  # <do command> [<undo command>]: a prep-cmd entry running them on the host, in the session
    jq -n --arg do "sh -c \"flatpak-spawn --host $env $session $HOME/.local/bin/$1\"" \
          --arg undo "${2:+sh -c \"flatpak-spawn --host $session $HOME/.local/bin/$2\"}" '{do: $do, undo: $undo}'
}
# before every app (games, a phone's desktop): what a session of ours left behind (Sunshine stopped mid-session, a crash:
# the monitors off, the virtual screen, output_name) is cleared; nothing is done when there is nothing
sed -i '/^global_prep_cmd *=/d' "$conf"
# and Sunshine's stream sound output made with its readable name for the session, gone after it (sunshine-sinks)
echo "global_prep_cmd = $(jq -c -n --argjson p "$(prep surface-screen-stop)" --argjson s "$(prep "sunshine-sinks session" "sunshine-sinks off")" '[$p, $s]')" >> "$conf"
screen=$(jq -n --argjson p "$(prep "surface-screen-start extend" surface-screen-stop)" \
    '{name: "Extended Display", cmd: "", "auto-detach": true, "wait-all": true, "exit-timeout": 5, elevated: false,
      "exclude-global-prep-cmd": false, "image-path": "", output: "", "prep-cmd": [$p]}')
desktop=$(prep surface-desktop-start surface-desktop-stop)
tmp=$(mktemp)
jq --argjson screen "$screen" --argjson d "$desktop" '
    .apps = ([(.apps // [])[] | select(.name != $screen.name and .name != "Surface Screen")] + [$screen])
    | .apps |= map(if .name == "Desktop" then .["prep-cmd"] = [$d] else . end)' "$apps" > "$tmp" && mv "$tmp" "$apps"
# whatever a session changed comes back also when Sunshine itself stops or restarts mid-session (no "undo" runs then)
mkdir -p "$HOME/.config/systemd/user/app-dev.lizardbyte.app.Sunshine.service.d"
# and the portal token is put back in step with the grant before Sunshine starts (surface-screen-token)
# and Sunshine's sound outputs gone while nothing streams: those it makes as it starts, those left when it stops (sunshine-sinks)
printf '[Service]\nExecStartPre=-%s\nExecStartPost=-%s off wait\nExecStopPost=-%s\nExecStopPost=-%s off\n' \
    "$HOME/.local/bin/surface-screen-token" "$HOME/.local/bin/sunshine-sinks" \
    "$HOME/.local/bin/surface-screen-stop" "$HOME/.local/bin/sunshine-sinks" \
    > "$HOME/.config/systemd/user/app-dev.lizardbyte.app.Sunshine.service.d/50-surface-screen.conf"
# Sunshine in the application menu opens the running one's page instead of starting a second Sunshine (sunshine-open)
src=$(flatpak info -l dev.lizardbyte.app.Sunshine 2>/dev/null)/export/share/applications/dev.lizardbyte.app.Sunshine.desktop
if [ -f "$src" ]; then
    mkdir -p "$HOME/.local/share/applications"
    sed "s|^Exec=.*|Exec=$HOME/.local/bin/sunshine-open|; /^X-Flatpak=/d" "$src" > "$HOME/.local/share/applications/dev.lizardbyte.app.Sunshine.desktop"
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi
# no "Remote Control Started" popup (the owner's choice): every Sunshine start tests the encoders with about eight
# screen-sharing sessions, one popup each; the portal reads this when it starts
kwriteconfig6 --file xdg-desktop-portal-kde.notifyrc --group "Event/remotedesktopstarted" --key Action ""
# the v4l2loopback camera surface-av feeds is "Surface Camera" in PipeWire; WirePlumber reads it when it starts, so it
# is restarted only when the file is new or changed (a restart cuts the PC's sound for a moment)
wp=$HOME/.config/wireplumber/wireplumber.conf.d
mkdir -p "$wp"
if ! cmp -s "$here/wireplumber/60-surface-camera-name.conf" "$wp/60-surface-camera-name.conf"; then
    install -m644 "$here/wireplumber/60-surface-camera-name.conf" "$wp/"
    systemctl --user restart wireplumber
fi
# apps opening the V4L2 device themselves (Chromium, Discord) read the kernel's label, which only root can change; and a
# second device is needed for the rear camera
if ! grep -qs 'Surface Rear Camera' /etc/modprobe.d/98-v4l2loopback.conf; then
    echo "For \"Surface Front Camera\" and \"Surface Rear Camera\" in every app, run once, then reboot:"
    echo "  echo 'options v4l2loopback devices=2 exclusive_caps=1,1 card_label=\"Surface Front Camera,Surface Rear Camera\"' | sudo tee /etc/modprobe.d/98-v4l2loopback.conf"
fi
# the PC's files in the Surface's Dolphin and the Surface's in the PC's (surface-sftp): the Surface already has sshd; the
# PC gets an SFTP server of the user's own, on its Tailscale address only, for the Surface's key only
addr=$(tailscale ip -4 2>/dev/null | head -1)
skey=$(ssh -o BatchMode=yes -o ConnectTimeout=5 surface cat .ssh/id_ed25519.pub 2>/dev/null || true)
if [ -n "$addr" ] && [ -n "$skey" ]; then
    sd=$HOME/.config/surface-sftp
    mkdir -p "$sd" && chmod 700 "$sd"
    [ -f "$sd/host_ed25519" ] || ssh-keygen -q -t ed25519 -N "" -C "surface-sftp@$(hostname)" -f "$sd/host_ed25519"
    printf 'restrict %s\n' "$skey" > "$sd/authorized_keys" && chmod 600 "$sd/authorized_keys"
    sed -e "s|@DIR@|$sd|g" -e "s|@ADDR@|$addr|g" "$here/surface-sftp/sshd_config.in" > "$sd/sshd_config"
    install -Dm644 "$here/surface-sftp/surface-sftp.service" "$HOME/.config/systemd/user/surface-sftp.service"
    systemctl --user daemon-reload
    systemctl --user enable surface-sftp.service >/dev/null 2>&1
    systemctl --user restart surface-sftp.service
    # the Surface: "dsktp" in its ssh config, the PC's host key known, and the place in Dolphin
    hostkey=$(cut -d' ' -f1,2 "$sd/host_ed25519.pub")
    ssh -o BatchMode=yes surface "mkdir -p ~/.ssh && touch ~/.ssh/config ~/.ssh/known_hosts && chmod 600 ~/.ssh/config &&
        { grep -q '^Host dsktp\$' ~/.ssh/config || printf '\nHost dsktp\n    HostName $addr\n    Port 2222\n' >> ~/.ssh/config; } &&
        { grep -v '^\[$addr\]:2222 ' ~/.ssh/known_hosts > ~/.ssh/known_hosts.new; echo '[$addr]:2222 $hostkey' >> ~/.ssh/known_hosts.new; mv ~/.ssh/known_hosts.new ~/.ssh/known_hosts; }" &&
        ssh -o BatchMode=yes surface "python3 - $(printf '%q ' "sftp://dsktp$HOME/" "PC (dsktp)" computer)" < "$here/surface-sftp/add-place"
    python3 "$here/surface-sftp/add-place" "sftp://surface/var/home/$(ssh -o BatchMode=yes surface whoami)/" "Surface" tablet
else
    echo "File sharing skipped: no Tailscale address or the Surface cannot be reached by ssh"
fi
# the KWin script moving windows between the Surface and the monitor (kwin/overdrive_screen_swap)
mkdir -p "$HOME/.local/share/kwin/scripts"
rm -rf "$HOME/.local/share/kwin/scripts/overdrive_screen_swap"
cp -r "$here/kwin/overdrive_screen_swap" "$HOME/.local/share/kwin/scripts/"
kwriteconfig6 --file kwinrc --group Plugins --key overdrive_screen_swapEnabled true
qdbus6 org.kde.KWin /KWin reconfigure >/dev/null 2>&1 || busctl --user call org.kde.KWin /KWin org.kde.KWin reconfigure >/dev/null 2>&1 || true
systemctl --user daemon-reload
# a restart ends an open stream: put off while a client is connected
# (a stream is on UDP: a TCP check alone missed one on 11-11; a session of ours leaves its marks in XDG_RUNTIME_DIR)
if ss -Htn state established '( sport = :47984 or sport = :47989 or sport = :48010 )' 2>/dev/null | grep -q . ||
   ss -Hun '( sport >= :47998 and sport <= :48010 )' 2>/dev/null | grep -q . ||
   [ -e "${XDG_RUNTIME_DIR:-/tmp}/surface-screen.off" ] || [ -e "${XDG_RUNTIME_DIR:-/tmp}/surface-screen.tray" ]; then
    echo "A client is connected: restart Sunshine when it is done (systemctl --user restart app-dev.lizardbyte.app.Sunshine)"
else
    systemctl --user restart app-dev.lizardbyte.app.Sunshine
fi
echo "Extended Display and Desktop ready in Sunshine"
